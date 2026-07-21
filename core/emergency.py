"""
Emergency manager.

Decides when a situation becomes an emergency, based on the kinematic states
produced by the state machine and a set of configurable rules. Kept separate
from the SM: the SM describes, the EM decides.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from core.state_machine import (
    FLIGHT_ACTIVITIES, GROUND_ACTIVITIES,
    FlightState, GroundState,
)


class EmergencyTrigger(str, Enum):
    MANUAL        = "MANUAL"         # manual SOS from the app
    AUTO_CHUTE    = "AUTO_CHUTE"     # landed under reserve chute, then immobile
    AUTO_IMPACT   = "AUTO_IMPACT"    # impact followed by a long stop
    AUTO_IMMOBILE = "AUTO_IMMOBILE"  # motionless for a long time, no impact


@dataclass
class EmConfig:
    """SM + EM parameters, loaded from the config table at runtime."""

    # Flight thresholds
    takeoff_speed_kmh:    float = 15.0   # minimum takeoff speed
    takeoff_alt_m:        float = 30.0   # alternative takeoff altitude
    takeoff_confirm_s:    float = 45.0   # seconds in condition to confirm
    landing_speed_kmh:    float = 10.0   # maximum landing speed
    landing_alt_m:        float = 30.0   # maximum landing altitude
    landing_confirm_s:    float = 45.0   # seconds in condition to confirm
    descending_vspeed_ms: float = -8.0   # vspeed below this -> DESCENDING_FAST
    descending_confirm_s: float = 10.0   # seconds in condition to confirm

    # Ground thresholds
    moving_speed_kmh:     float = 2.0    # below this the entity is not moving
    stationary_confirm_s: float = 20.0   # seconds below speed -> STATIONARY

    # Immobility is decided by displacement over a time window, not by
    # instantaneous GPS speed (which jitters and would reset the timer).
    immobile_radius_m:    float = 60.0   # stayed within this over the window -> immobile
    gps_accuracy_max_m:   float = 100.0  # ignore GPS points worse than this for immobility

    # Impact threshold per activity, in g, decided server-side from the peak
    # acceleration reported by the app. Energies differ a lot by activity.
    # 0 disables impact detection for that activity.
    impact_g_cyclist:     float = 6.0
    impact_g_climber:     float = 5.0
    impact_g_hiker:       float = 8.0
    impact_g_runner:      float = 8.0
    impact_g_other:       float = 0.0
    # Flight impact (hard landing / crash), app accelerometer. Off until
    # calibrated from real data — a normal landing must not cross it.
    impact_g_paraglider:  float = 0.0
    impact_g_hangglider:  float = 0.0

    # GPS gap: silence longer than this clears the streak timestamps.
    # Must be larger than the expected GPS interval (app default 15s).
    max_gap_s:            float = 120.0

    # Data / system
    live_window_min:      float = 10.0   # no data for longer -> entity drops off the live map
    retention_days:       float = 7.0    # keep tracks without an emergency this long
    ogn_flight_gap_min:   float = 30.0   # OGN silence that separates two flights (track/barogram)

    # Ground emergency rules
    impact_recovery_s:    float = 120.0  # motionless after impact -> AUTO_IMPACT
    immobile_emergency_s: float = 600.0  # motionless without impact -> AUTO_IMMOBILE

    # Reserve-chute rule: after DESCENDING_FAST -> LANDED, the pilot must stay
    # immobile (speed <= landing_speed_kmh) this long to confirm the emergency.
    chute_immobile_s:     float = 120.0

    # Confirmation window for AUTO_IMPACT / AUTO_IMMOBILE only. After detection
    # the user has this long to answer from the phone; otherwise the emergency
    # is confirmed automatically. MANUAL, AUTO_CHUTE and SIGNAL_LOST are immediate.
    pending_timeout_s:    float = 180.0


@dataclass
class EmContext:
    session_id:         int
    attivita:           str
    current_sm_state:   str
    state_entered_at:   datetime

    previous_sm_state:  Optional[str]      = None
    impact_at:          Optional[datetime] = None   # last IMPACT tick
    impact_lat:         Optional[float]    = None   # where the impact happened
    impact_lon:         Optional[float]    = None
    ack_at:             Optional[datetime] = None   # last "I'm fine"
    emergency_open:     bool               = False

    # Pending confirmation (AUTO_IMPACT / AUTO_IMMOBILE). Set when the EM detects
    # the condition: the emergency is held until the user answers. Cleared by a
    # confirm, an "I'm fine", or a timeout.
    pending_trigger:    Optional["EmergencyTrigger"] = None
    pending_since:      Optional[datetime]           = None

    # Reserve-chute watch: set when DESCENDING_FAST -> LANDED. The pilot must
    # stay immobile for chute_immobile_s to confirm; cleared if they move.
    chute_watch_since:  Optional[datetime]           = None

    # Recent positions (ts, lat, lon, accuracy_m) for displacement-based
    # immobility. Appended by the GPS handler each tick, pruned to a horizon.
    recent:             list                         = field(default_factory=list)


def update_em_context(ctx: EmContext, old_state: str, new_state: str, now: datetime):
    """Called by app.py on every SM transition to update the EM memory."""
    ctx.previous_sm_state = old_state
    ctx.current_sm_state  = new_state
    ctx.state_entered_at  = now

    if new_state == GroundState.IMPACT:
        ctx.impact_at = now

    # Landing straight out of a fast descent starts the reserve-chute watch.
    if old_state == FlightState.DESCENDING_FAST and new_state == FlightState.LANDED:
        ctx.chute_watch_since = now


def ack_ok(ctx: EmContext, now: datetime):
    """User says "I'm fine": reset the alarm context and clear any pending."""
    ctx.ack_at          = now
    ctx.impact_at       = None   # the previous impact is forgiven
    ctx.pending_trigger = None
    ctx.pending_since   = None


def evaluate_em(ctx: EmContext, cfg: EmConfig, rules: dict, now: datetime,
                speed_kmh=None) -> Optional[EmergencyTrigger]:
    """Evaluate the enabled rules on a GPS tick and return a trigger, or None.

    Rules come from the DB (enabled / applies_to / mode), so an admin can turn
    them on and off and scope them to activities. Returns None if an emergency
    is already open, or a pending one is waiting for confirmation.
    """
    if ctx.emergency_open:
        return None
    if ctx.pending_trigger is not None:
        return None

    if ctx.attivita in FLIGHT_ACTIVITIES:
        return _eval_flight(ctx, cfg, rules, now)
    elif ctx.attivita in GROUND_ACTIVITIES:
        return _eval_ground(ctx, cfg, rules, now)
    return None


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _is_immobile(recent, window_s, cfg: EmConfig, now: datetime) -> bool:
    """True if the entity stayed within immobile_radius_m over the last window_s.

    Displacement-based, so a jittery GPS speed spike can't reset the timer. Uses
    only points with usable accuracy, and needs history covering (most of) the
    window — otherwise we can't yet claim immobility for that long.
    """
    pts = [(t, la, lo) for (t, la, lo, acc) in recent
           if (now - t).total_seconds() <= window_s
           and (acc is None or acc <= cfg.gps_accuracy_max_m)]
    if len(pts) < 2:
        return False
    oldest = min(t for t, _, _ in pts)
    if (now - oldest).total_seconds() < window_s * 0.8:
        return False
    _, la0, lo0 = min(pts, key=lambda p: p[0])
    return all(_haversine_m(la0, lo0, la, lo) <= cfg.immobile_radius_m
               for _, la, lo in pts)


def _latest_good(recent, cfg: EmConfig):
    """Most recent (lat, lon) with usable accuracy, or None."""
    good = [(la, lo) for (t, la, lo, acc) in recent
            if acc is None or acc <= cfg.gps_accuracy_max_m]
    return good[-1] if good else None


def _eval_chute(ctx: EmContext, cfg: EmConfig, rules: dict, now: datetime) -> Optional[EmergencyTrigger]:
    """Reserve chute: fast descent -> landing -> immobile for chute_immobile_s.
    Immobility is measured by displacement (jitter-robust), not instant speed."""
    if ctx.chute_watch_since is None:
        return None
    if not rule_active(rules, "AUTO_CHUTE", ctx.attivita):
        ctx.chute_watch_since = None
        return None
    if (now - ctx.chute_watch_since).total_seconds() < cfg.chute_immobile_s:
        return None  # not enough time watched yet
    if _is_immobile(ctx.recent, cfg.chute_immobile_s, cfg, now):
        ctx.chute_watch_since = None
        return EmergencyTrigger.AUTO_CHUTE
    # Time passed but the pilot moved away from the landing spot: stand down.
    ctx.chute_watch_since = None
    return None


def _eval_flight(ctx: EmContext, cfg: EmConfig, rules: dict, now: datetime) -> Optional[EmergencyTrigger]:
    """Flight: the reserve-chute gate (vertical speed) OR a hard impact followed
    by immobility. Two independent nets — the chute catches soft descents when
    the vspeed is clean (OGN / a barometer), the impact catches a hard landing on
    any phone. Both dedup against an OGN emergency for the same pilot."""
    return _eval_chute(ctx, cfg, rules, now) or _impact_immobile(ctx, cfg, rules, now)


def _impact_immobile(ctx: EmContext, cfg: EmConfig, rules: dict, now: datetime) -> Optional[EmergencyTrigger]:
    """Hard impact, then immobile-since-impact for impact_recovery_s -> AUTO_IMPACT.
    Shared by ground and flight (app accelerometer). The impact is forgotten if
    the subject moves away from the spot (walked off / flew away = evidently ok)."""
    impact_relevant = ctx.impact_at
    if impact_relevant and ctx.ack_at and ctx.ack_at > impact_relevant:
        impact_relevant = None
    if not impact_relevant:
        return None
    if ctx.impact_lat is not None:
        latest = _latest_good(ctx.recent, cfg)
        if latest and _haversine_m(ctx.impact_lat, ctx.impact_lon, latest[0], latest[1]) > cfg.immobile_radius_m:
            ctx.impact_at = ctx.impact_lat = ctx.impact_lon = None
            return None
    if ((now - ctx.impact_at).total_seconds() >= cfg.impact_recovery_s
            and _is_immobile(ctx.recent, cfg.impact_recovery_s, cfg, now)
            and rule_active(rules, "AUTO_IMPACT", ctx.attivita)):
        return EmergencyTrigger.AUTO_IMPACT
    return None


def _eval_ground(ctx: EmContext, cfg: EmConfig, rules: dict, now: datetime) -> Optional[EmergencyTrigger]:
    """Ground rules (immobility by displacement, jitter-robust):
      AUTO_IMPACT:   impact then immobile-since-impact. For CLIMBER the impact
                     fires directly (horizontal immobility is meaningless).
      AUTO_IMMOBILE: immobile without impact (off by default).
    """
    impact_relevant = ctx.impact_at
    if impact_relevant and ctx.ack_at and ctx.ack_at > impact_relevant:
        impact_relevant = None

    # Climbing: a fall fires on the impact itself, before any movement check.
    if (impact_relevant and ctx.attivita == "CLIMBER"
            and rule_active(rules, "AUTO_IMPACT", ctx.attivita)):
        return EmergencyTrigger.AUTO_IMPACT

    trigger = _impact_immobile(ctx, cfg, rules, now)
    if trigger:
        return trigger

    # Immobile without any impact (off by default; never for climbing).
    if (not ctx.impact_at and ctx.attivita != "CLIMBER"
            and _is_immobile(ctx.recent, cfg.immobile_emergency_s, cfg, now)
            and rule_active(rules, "AUTO_IMMOBILE", ctx.attivita)):
        return EmergencyTrigger.AUTO_IMMOBILE

    return None


# Default config, used when the DB is not reachable.
DEFAULT_CONFIG = EmConfig()


# Config metadata for the admin UI: (key, machine, category, description, type).
# machine is "SM" (state definitions) or "EM" (emergency rules). Descriptions
# stay in Italian, they are shown to the admin as-is.
CONFIG_META = [
    # State machine — flight
    ("takeoff_speed_kmh",    "SM", "volo", "Velocità minima decollo (km/h)",                     "float"),
    ("takeoff_alt_m",        "SM", "volo", "Quota AGL alternativa per confermare decollo (m)",   "float"),
    ("takeoff_confirm_s",    "SM", "volo", "Secondi in condizione decollo per confermare",       "float"),
    ("landing_speed_kmh",    "SM", "volo", "Velocità massima atterraggio (km/h)",                "float"),
    ("landing_alt_m",        "SM", "volo", "Quota AGL massima atterraggio (m)",                  "float"),
    ("landing_confirm_s",    "SM", "volo", "Secondi in condizione atterraggio per confermare",   "float"),
    ("descending_vspeed_ms", "SM", "volo", "Velocità verticale soglia discesa rapida (m/s, negativo)", "float"),
    ("descending_confirm_s", "SM", "volo", "Secondi in discesa rapida per confermare",           "float"),

    # State machine — ground
    ("moving_speed_kmh",     "SM", "terrestre", "Velocità minima per considerarsi in movimento (km/h)", "float"),
    ("stationary_confirm_s", "SM", "terrestre", "Secondi sotto soglia velocità → STATIONARY",          "float"),
    ("impact_g_cyclist",     "SM", "terrestre", "Soglia impatto ciclismo (g, 0 = disattivato)",        "float"),
    ("impact_g_climber",     "SM", "terrestre", "Soglia impatto arrampicata (g, 0 = disattivato)",     "float"),
    ("impact_g_hiker",       "SM", "terrestre", "Soglia impatto escursionismo (g, 0 = disattivato)",   "float"),
    ("impact_g_runner",      "SM", "terrestre", "Soglia impatto trail running (g, 0 = disattivato)",   "float"),
    ("impact_g_other",       "SM", "terrestre", "Soglia impatto altre attività (g, 0 = disattivato)",  "float"),
    ("impact_g_paraglider",  "SM", "volo", "Soglia impatto parapendio (g, 0 = disattivato)",       "float"),
    ("impact_g_hangglider",  "SM", "volo", "Soglia impatto deltaplano (g, 0 = disattivato)",        "float"),

    # State machine — common
    ("max_gap_s",            "SM", "comune", "Silenzio GPS > N secondi → azzera le conferme in corso", "float"),

    # Data / system
    ("live_window_min",    "SM", "sistema", "Minuti senza dati oltre cui un'entità sparisce dalla mappa (pin stale)", "float"),
    ("retention_days",     "SM", "sistema", "Giorni di conservazione delle tracce senza emergenza",                   "float"),
    ("ogn_flight_gap_min", "SM", "sistema", "Minuti di silenzio OGN che separano due voli (traccia/barogramma)",      "float"),

    # Emergency machine — flight rules
    ("chute_immobile_s",     "EM", "volo", "Secondi immobile dopo atterraggio col paracadute → emergenza", "float"),

    # Emergency machine — ground rules
    ("impact_recovery_s",    "EM", "terrestre", "Secondi fermo dopo impatto → AUTO_IMPACT",       "float"),
    ("immobile_emergency_s", "EM", "terrestre", "Secondi fermo senza impatto → AUTO_IMMOBILE",    "float"),
    ("immobile_radius_m",    "EM", "terrestre", "Raggio entro cui si è considerati fermi nella finestra (m)", "float"),
    ("gps_accuracy_max_m",   "EM", "terrestre", "Accuratezza GPS oltre cui il punto è ignorato per l'immobilità (m)", "float"),
    ("pending_timeout_s",    "EM", "terrestre", "Secondi per confermare/annullare dal telefono (poi auto-confirm)", "float"),
]


# Default emergency rules, seeded into the emergency_rules table.
# (key, enabled, applies_to CSV, mode).
FREE_FLIGHT = "PARAGLIDER,HANGGLIDER"
GROUND_ALL  = "CYCLIST,CLIMBER,HIKER,RUNNER,OTHER_ON_GROUND"

RULE_DEFAULTS = [
    ("AUTO_CHUTE",    1, FREE_FLIGHT, "immediate"),
    ("AUTO_IMPACT",   1, FREE_FLIGHT + "," + GROUND_ALL,  "pending"),
    # Prolonged immobility without an impact is almost always a legit break
    # (lunch, rest). Off by default; the admin can re-enable it on the EM page.
    ("AUTO_IMMOBILE", 0, GROUND_ALL,  "pending"),
]


# OGN/FLARM aircraft type codes -> activity label. Shared by the API and the
# OGN worker to tell paragliders and hang gliders apart from powered traffic.
_OGN_KIND = {
    1:  "AIRCRAFT",     # glider — not monitored, treated as generic aircraft
    2:  "AIRCRAFT",     # tow plane
    3:  "HELICOPTER",
    4:  "SKYDIVER",
    5:  "AIRCRAFT",     # drop plane
    6:  "HANGGLIDER",
    7:  "PARAGLIDER",
    8:  "AIRCRAFT",     # powered
    9:  "AIRCRAFT",     # jet
    11: "BALLOON",
    12: "AIRSHIP",
    13: "UAV",
}


def ogn_kind(aircraft_type) -> str:
    return _OGN_KIND.get(aircraft_type, "UNKNOWN")


def rule_active(rules: dict, key: str, attivita: str) -> bool:
    """True if the rule is present, enabled, and scoped to this activity."""
    r = rules.get(key)
    return bool(r and r["enabled"] and attivita in r["applies_to"])
