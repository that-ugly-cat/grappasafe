"""
Position forwarding to third-party systems.

Users can opt in, per target, to have their own positions forwarded to another
tracking system (Vedetta and anything else accepting the same contract). The
forwarding happens here, on the server, and never on the phone: the transport
that keeps running with the screen off is the native sender, which only talks
to /api/gps, and a second radio wake-up every few seconds would cost battery
for no reason.

Two rules govern this module:

  1. It never affects the emergency path. Enqueuing is non-blocking, the queue
     is bounded, and no failure ever propagates back to the caller. A third
     party being down must not slow a single GPS point down.
  2. It forwards positions only. Medical data, emergency contacts and the
     emergency lifecycle stay inside GrappaSafe.
"""

import threading
import time
from collections import deque
from datetime import datetime, timezone

import httpx

import db as _db

# Contract version sent to the receiver, so a change of shape stays readable
# from the other side.
PAYLOAD_VERSION = 1

_HTTP_TIMEOUT_S = 5.0
_QUEUE_CAP = 2000          # ~2 min of traffic for 100 pilots at 15s; then the oldest go
_TARGETS_TTL_S = 60.0      # per-user target cache, same pattern as EmConfig
_RESULT_MIN_SEC = 60.0     # do not rewrite last_ok_at on every single point

_queue: deque = deque(maxlen=_QUEUE_CAP)
_wakeup = threading.Event()

_targets_cache: dict = {}   # user_id -> (expires_at_monotonic, [target, ...])
_cache_lock = threading.Lock()

_last_sent: dict = {}       # target_id -> monotonic of the last delivery attempt
_last_result: dict = {}     # target_id -> (ok, monotonic of the last DB write)


def enqueue(user_id, point) -> None:
    """Queue one position for forwarding. Called from the GPS ingest path, so
    it must stay cheap and must never raise: the caller is on its way to the
    emergency machine."""
    try:
        if not _has_targets(user_id):
            return
        _queue.append((user_id, point))
        _wakeup.set()
    except Exception:
        pass


def invalidate(user_id) -> None:
    """Drop the cached targets of a user, after they edit their own."""
    with _cache_lock:
        _targets_cache.pop(user_id, None)


def build_point(ts, lat, lon, alt_m, speed_kmh, vspeed_ms, activity, state,
                accel_g=None, accuracy_m=None) -> dict:
    """The forwarded payload. Altitude is AMSL, like every other source: the
    receiver computes AGL with its own terrain data.

    accel_g is the peak acceleration the app measured since its previous fix.
    It is the one signal a phone has and a radio beacon does not, and it is what
    lets a receiver run an impact net on app-tracked pilots; accuracy_m lets it
    keep a bad fix out of an immobility check. Both are None for anything that
    does not report them."""
    return {
        "v":          PAYLOAD_VERSION,
        "source":     "grappasafe",
        "ts":         ts,
        "lat":        lat,
        "lon":        lon,
        "alt_m":      alt_m,
        "speed_kmh":  speed_kmh,
        "vspeed_ms":  vspeed_ms,
        "activity":   activity,
        "state":      state,
        "accel_g":    accel_g,
        "accuracy_m": accuracy_m,
    }


def _get_targets(user_id):
    now = time.monotonic()
    with _cache_lock:
        hit = _targets_cache.get(user_id)
        if hit and hit[0] > now:
            return hit[1]
    try:
        targets = _db.get_enabled_forward_targets(user_id)
    except Exception:
        targets = []
    with _cache_lock:
        _targets_cache[user_id] = (now + _TARGETS_TTL_S, targets)
    return targets


def _has_targets(user_id) -> bool:
    return bool(_get_targets(user_id))


def _record(target_id, ok, error=None) -> None:
    """Persist the outcome, but only when it changes or once a minute: one UPDATE
    per point per target would be pointless write amplification."""
    prev = _last_result.get(target_id)
    now  = time.monotonic()
    if prev and prev[0] == ok and (now - prev[1]) < _RESULT_MIN_SEC:
        return
    _last_result[target_id] = (ok, now)
    try:
        _db.set_forward_result(target_id, ok, error)
    except Exception:
        pass


def _deliver(client, target, point) -> None:
    tid = target["id"]

    # Rate floor per target: a pilot with the GPS at 5s must not hammer the
    # receiver, which is typically happy with one point every 15s.
    interval = float(target.get("min_interval_s") or 0)
    last     = _last_sent.get(tid)
    now      = time.monotonic()
    if last is not None and interval > 0 and (now - last) < interval:
        return
    _last_sent[tid] = now

    body = dict(point)
    headers = {"Content-Type": "application/json"}
    token = target.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        # Also in the body: some receivers read the token from there.
        body["token"] = token

    try:
        r = client.post(target["url"], json=body, headers=headers, timeout=_HTTP_TIMEOUT_S)
        if r.status_code >= 400:
            _record(tid, False, f"HTTP {r.status_code}: {r.text[:120]}")
        else:
            _record(tid, True)
    except Exception as e:
        _record(tid, False, f"{type(e).__name__}: {e}")


def forward_worker(stop_flag) -> None:
    """Drains the queue. One thread is enough: the sends are short and the
    volume is a handful of points per second at worst."""
    with httpx.Client(timeout=_HTTP_TIMEOUT_S) as client:
        while not stop_flag.is_set():
            if not _queue:
                _wakeup.wait(2)
                _wakeup.clear()
                continue
            try:
                user_id, point = _queue.popleft()
            except IndexError:
                continue
            for target in _get_targets(user_id):
                if stop_flag.is_set():
                    break
                try:
                    _deliver(client, target, point)
                except Exception:
                    pass


def send_test(target) -> tuple:
    """A handshake, to check a target from the app right after saving it.
    Carries no position on purpose: a receiver that ignores the `test` flag and
    parses it anyway must fail validation, not plant a fake pin on its map.
    Returns (ok, message)."""
    body = {
        "v":      PAYLOAD_VERSION,
        "source": "grappasafe",
        "test":   True,
        "ts":     datetime.now(timezone.utc).isoformat(),
    }
    headers = {"Content-Type": "application/json"}
    if target.get("token"):
        headers["Authorization"] = f"Bearer {target['token']}"
        body["token"] = target["token"]
    try:
        r = httpx.post(target["url"], json=body, headers=headers, timeout=_HTTP_TIMEOUT_S)
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}: {r.text[:160]}"
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
