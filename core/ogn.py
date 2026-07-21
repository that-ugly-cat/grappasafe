"""
OGN worker.

Reads the OGN APRS feed and keeps the beacons inside the monitoring area.
The connection logic is the same as Vedetta's, adapted to filter by a
geographic area instead of a watchlist.
"""

import math
import socket as _socket
import threading
from datetime import datetime, timezone
from time import sleep as _sleep

from ogn.client import AprsClient
from ogn.client.client import create_aprs_login
from ogn.parser import parse

import db as _db
from core.config import APRS_USER, APRS_PASS, AREA_LAT, AREA_LON, AREA_RADIUS_KM
from core.notify import notify_emergency
from core.state_machine import OgnTracker, update_ogn_sm, FlightState
from core.emergency import EmergencyTrigger, ogn_kind, rule_active
from core.terrain import compute_agl


def _bget(beacon, key):
    """Read a field from a parsed beacon. Current ogn-parser returns a dict;
    older versions returned an object with attributes."""
    if isinstance(beacon, dict):
        return beacon.get(key)
    return getattr(beacon, key, None)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R  = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def in_area(lat, lon) -> bool:
    if lat is None or lon is None:
        return False
    return haversine_km(AREA_LAT, AREA_LON, lat, lon) <= AREA_RADIUS_KM


class AuthAprsClient(AprsClient):
    """AprsClient with explicit authentication."""

    def __init__(self, aprs_user, aprs_pass, aprs_filter=""):
        super().__init__(aprs_user=aprs_user, aprs_filter=aprs_filter)
        self._aprs_pass = aprs_pass

    def connect(self, retries=3, wait_period=15, socket_timeout=10):
        while retries > 0:
            retries -= 1
            try:
                self.sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                self.sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_KEEPALIVE, 1)
                self.sock.settimeout(socket_timeout)
                port = (self.settings.APRS_SERVER_PORT_CLIENT_DEFINED_FILTERS
                        if self.aprs_filter
                        else self.settings.APRS_SERVER_PORT_FULL_FEED)
                self.sock.connect((self.settings.APRS_SERVER_HOST, port))
                login = create_aprs_login(
                    self.aprs_user, self._aprs_pass,
                    self.settings.APRS_APP_NAME, self.settings.APRS_APP_VER,
                    self.aprs_filter,
                )
                self.sock.send(login.encode())
                self.sock_file = self.sock.makefile("rb")
                self.sock.settimeout(None)
                self._kill = False
                break
            except (_socket.error, ConnectionError) as e:
                print(f"  [OGN] {type(e).__name__}: {e}")
                if retries > 0:
                    print(f"  [OGN] retry in {wait_period}s ({retries} left)...")
                    _sleep(wait_period)
                else:
                    print("  [OGN] connection failed.")
                    self._kill = True


# ── Global state ──────────────────────────────────────────────────────────────

# ogn_id -> OgnTracker
_ogn_trackers: dict[str, OgnTracker] = {}
_trackers_lock = threading.Lock()

# Local config cache, reloaded every 60s by the signal-lost checker
_ogn_cfg = None
_ogn_cfg_lock = threading.Lock()


def _get_ogn_cfg():
    """Config with a local 60s cache. Thread-safe."""
    global _ogn_cfg
    with _ogn_cfg_lock:
        if _ogn_cfg is None:
            _ogn_cfg = _db.load_em_config()
        return _ogn_cfg


def _reload_ogn_cfg():
    global _ogn_cfg
    with _ogn_cfg_lock:
        _ogn_cfg = _db.load_em_config()


def get_ogn_trackers() -> dict:
    return _ogn_trackers


# ── Main worker ───────────────────────────────────────────────────────────────

def ogn_worker(stop_flag) -> None:
    """Main OGN thread. Uses the APRS geographic filter r/lat/lon/radius."""
    aprs_filter = f"r/{AREA_LAT}/{AREA_LON}/{AREA_RADIUS_KM}"

    # Side thread: keeps the OGN config cache fresh (60s).
    def _config_reloader():
        while not stop_flag.is_set():
            stop_flag.wait(60)
            _reload_ogn_cfg()

    threading.Thread(target=_config_reloader, daemon=True).start()

    while not stop_flag.is_set():
        client = AuthAprsClient(aprs_user=APRS_USER, aprs_pass=APRS_PASS, aprs_filter=aprs_filter)
        client.connect()

        if client._kill:
            print("  [OGN] connection failed — retry in 60s")
            stop_flag.wait(60)
            continue

        print(f"  [OGN] connected - area {AREA_RADIUS_KM}km around {AREA_LAT},{AREA_LON}")

        def stopper(c=client):
            stop_flag.wait()
            try:
                c.disconnect()
            except Exception:
                pass

        threading.Thread(target=stopper, daemon=True).start()

        def on_raw(raw: str):
            if not raw or raw.startswith("#"):
                return
            try:
                beacon = parse(raw)
            except Exception:
                return

            lat = _bget(beacon, "latitude")
            lon = _bget(beacon, "longitude")
            if not in_area(lat, lon):
                return

            ogn_id       = _bget(beacon, "address") or _bget(beacon, "name") or raw[:10]
            display_name = _bget(beacon, "name") or ogn_id
            alt_m        = _bget(beacon, "altitude")
            speed_kmh    = _bget(beacon, "ground_speed")
            vspeed_ms    = _bget(beacon, "climb_rate")
            course_deg    = _bget(beacon, "track")
            aircraft_type = _bget(beacon, "aircraft_type")
            ts            = datetime.now(timezone.utc).isoformat()

            beacon_id = _db.write_ogn_beacon(
                ogn_id=ogn_id, display_name=display_name, ts=ts,
                lat=lat, lon=lon, alt_m=alt_m,
                speed_kmh=speed_kmh, vspeed_ms=vspeed_ms, course_deg=course_deg,
                aircraft_type=aircraft_type,
            )

            beacon_dict = dict(ts=ts, lat=lat, lon=lon, alt_m=alt_m,
                               speed_kmh=speed_kmh or 0, vspeed_ms=vspeed_ms or 0)

            # The DB beacon keeps AMSL; the SM gets AGL
            sm_beacon = dict(beacon_dict)
            if alt_m is not None:
                sm_beacon["alt_m"] = compute_agl(lat, lon, alt_m)

            with _trackers_lock:
                if ogn_id not in _ogn_trackers:
                    _ogn_trackers[ogn_id] = OgnTracker(ogn_id=ogn_id, display_name=display_name)
                tracker = _ogn_trackers[ogn_id]
                old_state = tracker.state

            cfg = _get_ogn_cfg()
            changed = update_ogn_sm(tracker, sm_beacon, cfg)
            _db.update_ogn_state(ogn_id, tracker.state)

            # OGN reserve-chute rule: DESCENDING_FAST -> LANDED. OGN can't confirm
            # post-landing immobility (beacons usually stop), so it fires on the
            # transition, gated by the rule being enabled for this aircraft type.
            if changed and old_state == FlightState.DESCENDING_FAST and tracker.state == FlightState.LANDED:
                kind = ogn_kind(aircraft_type)
                if rule_active(_db.load_em_rules(), "AUTO_CHUTE", kind):
                    owner = _db.get_device_owner_id(ogn_id)
                    if owner and _db.get_open_emergency_for_user(owner):
                        # Same pilot already has an open emergency (e.g. via the app).
                        print(f"  [OGN] chute deduped (already open): {display_name}")
                    else:
                        eid = _db.create_emergency(
                            trigger=EmergencyTrigger.AUTO_CHUTE.value,
                            lat=lat, lon=lon, alt_m=alt_m,
                            ogn_beacon_id=beacon_id, user_id=owner,
                            note=f"OGN: {display_name}",
                        )
                        notify_emergency(eid)
                        print(f"  [OGN] AUTO_CHUTE: {display_name} ({kind})")
                else:
                    print(f"  [OGN] chute landing ignored: {display_name} ({kind})")
            else:
                print(f"  [OGN] {display_name}: {tracker.state} "
                      f"alt={alt_m}m speed={speed_kmh}km/h vspeed={vspeed_ms}m/s")

        try:
            client.run(callback=on_raw, autoreconnect=False)
        except Exception as e:
            print(f"  [OGN] disconnected: {e}")

        if not stop_flag.is_set():
            print("  [OGN] reconnecting in 10s...")
            stop_flag.wait(10)
