"""
Kinematic state machine.

Describes what an entity is physically doing. It holds no emergency logic:
the state machine describes, the emergency manager decides.

Transitions are confirmed over time (seconds), not per tick. If GPS goes
silent for longer than cfg.max_gap_s the streak timestamps are cleared,
since silence means we can't trust the last known condition.

Flight (PARAGLIDER, HANGGLIDER):
    GROUND -> AIRBORNE -> LANDED

Ground (CYCLIST, CLIMBER, HIKER, RUNNER, OTHER_ON_GROUND):
    MOVING <-> STATIONARY
    IMPACT (transient, one tick, overrides any state)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.emergency import EmConfig

FLIGHT_ACTIVITIES = {"PARAGLIDER", "HANGGLIDER"}
GROUND_ACTIVITIES = {"CYCLIST", "CLIMBER", "HIKER", "RUNNER", "OTHER_ON_GROUND"}


class FlightState(str, Enum):
    GROUND          = "GROUND"
    AIRBORNE        = "AIRBORNE"
    LANDED          = "LANDED"


class GroundState(str, Enum):
    MOVING      = "MOVING"
    STATIONARY  = "STATIONARY"
    IMPACT      = "IMPACT"     # transient: one tick, then MOVING or STATIONARY


@dataclass
class SessionTracker:
    session_id:  int
    user_id:     int
    attivita:    str
    state:       str           # may also hold "EMERGENCY", written by app.py not by the SM
    last_seen:   Optional[datetime] = None

    # Flight streak timestamps: set when a condition first becomes true,
    # cleared when it breaks or when the transition fires.
    takeoff_since:    Optional[datetime] = None
    landing_since:    Optional[datetime] = None

    # Ground streak timestamp.
    stationary_since: Optional[datetime] = None

    def is_flight(self) -> bool:
        return self.attivita in FLIGHT_ACTIVITIES

    def is_ground(self) -> bool:
        return self.attivita in GROUND_ACTIVITIES


@dataclass
class OgnTracker:
    ogn_id:          str
    display_name:    str
    state:           str = FlightState.GROUND
    last_seen:       Optional[datetime] = None
    takeoff_since:   Optional[datetime] = None
    landing_since:   Optional[datetime] = None
    linked_user_id:  Optional[int] = None

    # Reserve-chute watch (OGN, no accelerometer). Managed by ogn_chute_step in
    # core/emergency.py; the SM never reads or writes these.
    chute_watch:        bool               = False  # armed: sustained reserve-rate descent
    chute_fired:        bool               = False  # emergency already opened, don't re-fire
    chute_arm_since:    Optional[datetime] = None   # arming streak start
    chute_recover_since: Optional[datetime] = None  # recovery-to-flight streak start
    chute_last_agl:     Optional[float]    = None   # last AGL while watching (Path 2 floor)
    chute_last_lat:     Optional[float]    = None   # last position, for the SIGNAL_LOST record
    chute_last_lon:     Optional[float]    = None
    chute_last_alt_amsl: Optional[float]   = None
    chute_kind:         Optional[str]      = None   # PARAGLIDER | HANGGLIDER (for rule scope)
    chute_recent:       list               = field(default_factory=list)  # (ts, lat, lon)


def _reset_streaks(tracker) -> None:
    """Clear all streak timestamps after a GPS gap."""
    for attr in ("takeoff_since", "landing_since", "stationary_since"):
        if hasattr(tracker, attr):
            setattr(tracker, attr, None)


def update_sm(tracker: SessionTracker, point: dict, cfg: "EmConfig") -> bool:
    """Feed a GPS point into the state machine. Returns True if the state changed."""
    now = _parse_ts(point.get("ts"))

    # Drop the streaks if GPS was silent for too long: a stale condition
    # should not be allowed to fire a transition.
    if tracker.last_seen is not None:
        gap = (now - tracker.last_seen).total_seconds()
        if gap > cfg.max_gap_s:
            _reset_streaks(tracker)

    tracker.last_seen = now
    old_state = tracker.state

    # During an open emergency the SM keeps updating internally, but app.py
    # keeps the DB state at EMERGENCY.
    if tracker.is_flight():
        _update_flight(tracker, point, cfg, now)
    elif tracker.is_ground():
        _update_ground(tracker, point, cfg, now)

    return tracker.state != old_state


def update_ogn_sm(tracker: OgnTracker, beacon: dict, cfg: "EmConfig") -> bool:
    """Feed an OGN beacon into the flight SM. Returns True if the state changed."""
    now = _parse_ts(beacon.get("ts"))

    if tracker.last_seen is not None:
        gap = (now - tracker.last_seen).total_seconds()
        if gap > cfg.max_gap_s:
            _reset_streaks(tracker)

    tracker.last_seen = now
    old_state = tracker.state

    _update_flight_generic(
        state=tracker.state,
        set_state=lambda s: setattr(tracker, "state", s),
        get_since=lambda k: getattr(tracker, k),
        set_since=lambda k, v: setattr(tracker, k, v),
        now=now,
        alt_m=beacon.get("alt_m") or 0.0,
        speed_kmh=beacon.get("speed_kmh") or 0.0,
        cfg=cfg,
    )
    return tracker.state != old_state


def _update_flight(tracker: SessionTracker, point: dict, cfg: "EmConfig", now: datetime):
    _update_flight_generic(
        state=tracker.state,
        set_state=lambda s: setattr(tracker, "state", s),
        get_since=lambda k: getattr(tracker, k),
        set_since=lambda k, v: setattr(tracker, k, v),
        now=now,
        alt_m=point.get("alt_m") or 0.0,
        speed_kmh=point.get("speed_kmh") or 0.0,
        cfg=cfg,
    )


def _update_flight_generic(state, set_state, get_since, set_since, now,
                            alt_m, speed_kmh, cfg):
    """Flight logic shared by SessionTracker and OgnTracker."""

    # GROUND or LANDED both re-detect takeoff: LANDED is NOT terminal. An OGN
    # device lands and relaunches (it has no "session end"), and a low, slow pass
    # can trip a false LANDED — either way it must recover to AIRBORNE.
    if state in (FlightState.GROUND, FlightState.LANDED):
        # Well above the ground is unambiguous: go airborne immediately, without
        # the confirmation streak. A gappy OGN feed keeps resetting that streak
        # (a normal beacon gap looks like silence), which can otherwise leave a
        # pilot at altitude stuck at GROUND/LANDED.
        if alt_m >= cfg.airborne_alt_m:
            set_state(FlightState.AIRBORNE)
            set_since("takeoff_since", None)
            return
        if speed_kmh >= cfg.takeoff_speed_kmh or alt_m > cfg.takeoff_alt_m:
            since = get_since("takeoff_since")
            if since is None:
                set_since("takeoff_since", now)
            elif (now - since).total_seconds() >= cfg.takeoff_confirm_s:
                set_state(FlightState.AIRBORNE)
                set_since("takeoff_since", None)
        else:
            set_since("takeoff_since", None)
        return

    if state == FlightState.AIRBORNE:
        # Landing check.
        if speed_kmh <= cfg.landing_speed_kmh and alt_m <= cfg.landing_alt_m:
            since = get_since("landing_since")
            if since is None:
                set_since("landing_since", now)
            elif (now - since).total_seconds() >= cfg.landing_confirm_s:
                set_state(FlightState.LANDED)
                set_since("landing_since", None)
        else:
            set_since("landing_since", None)
        return


def impact_threshold(attivita: str, cfg: "EmConfig") -> float:
    """Per-activity impact threshold in g (0 disables impact detection)."""
    return {
        "CYCLIST":         cfg.impact_g_cyclist,
        "CLIMBER":         cfg.impact_g_climber,
        "HIKER":           cfg.impact_g_hiker,
        "RUNNER":          cfg.impact_g_runner,
        "OTHER_ON_GROUND": cfg.impact_g_other,
        "PARAGLIDER":      cfg.impact_g_paraglider,
        "HANGGLIDER":      cfg.impact_g_hangglider,
    }.get(attivita, 0.0)


def _update_ground(tracker: SessionTracker, point: dict, cfg: "EmConfig", now: datetime):
    # Impact is decided server-side from the peak acceleration the app reports,
    # against a per-activity threshold in g.
    accel     = point.get("accel_magnitude")
    threshold = impact_threshold(tracker.attivita, cfg)
    impact    = accel is not None and threshold > 0 and accel >= threshold
    speed_kmh = point.get("speed_kmh") or 0.0

    # IMPACT is transient: it overrides everything for one tick.
    if impact:
        tracker.state = GroundState.IMPACT
        tracker.stationary_since = None
        return

    if speed_kmh >= cfg.moving_speed_kmh:
        tracker.state = GroundState.MOVING
        tracker.stationary_since = None
    else:
        if tracker.stationary_since is None:
            tracker.stationary_since = now
        elif (now - tracker.stationary_since).total_seconds() >= cfg.stationary_confirm_s:
            tracker.state = GroundState.STATIONARY
        # otherwise keep the current state until confirmed


def _parse_ts(ts) -> datetime:
    from datetime import timezone
    if ts is None:
        return datetime.now(timezone.utc)
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts)
