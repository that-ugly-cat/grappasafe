"""
Emergency manager.

Decides when a situation becomes an emergency, based on the kinematic states
produced by the state machine and a set of configurable rules. Kept separate
from the SM: the SM describes, the EM decides.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from core.state_machine import (
    FLIGHT_ACTIVITIES, GROUND_ACTIVITIES,
    FlightState, GroundState,
)


class EmergencyTrigger(str, Enum):
    MANUAL        = "MANUAL"         # manual SOS from the app
    AUTO_CHUTE    = "AUTO_CHUTE"     # landed under reserve chute
    AUTO_IMPACT   = "AUTO_IMPACT"    # impact followed by a long stop
    AUTO_IMMOBILE = "AUTO_IMMOBILE"  # motionless for a long time, no impact
    SIGNAL_LOST   = "SIGNAL_LOST"    # OGN: signal lost while airborne


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

    # GPS gap: silence longer than this clears the streak timestamps.
    # Must be larger than the expected GPS interval (app default 15s).
    max_gap_s:            float = 120.0

    # Ground emergency rules
    impact_recovery_s:    float = 120.0  # motionless after impact -> AUTO_IMPACT
    immobile_emergency_s: float = 600.0  # motionless without impact -> AUTO_IMMOBILE
    ack_cooldown_s:       float = 1800.0 # quiet period after "I'm fine"

    # OGN rule
    signal_lost_min:      float = 5.0    # minutes without OGN signal while airborne

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
    ack_at:             Optional[datetime] = None   # last "I'm fine"
    emergency_open:     bool               = False

    # Pending confirmation (AUTO_IMPACT / AUTO_IMMOBILE). Set when the EM detects
    # the condition: the emergency is held until the user answers. Cleared by a
    # confirm, an "I'm fine", or a timeout.
    pending_trigger:    Optional["EmergencyTrigger"] = None
    pending_since:      Optional[datetime]           = None


def update_em_context(ctx: EmContext, old_state: str, new_state: str, now: datetime):
    """Called by app.py on every SM transition to update the EM memory."""
    ctx.previous_sm_state = old_state
    ctx.current_sm_state  = new_state
    ctx.state_entered_at  = now

    if new_state == GroundState.IMPACT:
        ctx.impact_at = now


def ack_ok(ctx: EmContext, now: datetime):
    """User says "I'm fine": reset the alarm context and clear any pending."""
    ctx.ack_at          = now
    ctx.impact_at       = None   # the previous impact is forgiven
    ctx.pending_trigger = None
    ctx.pending_since   = None


def evaluate_em(ctx: EmContext, cfg: EmConfig, now: datetime) -> Optional[EmergencyTrigger]:
    """Evaluate the rules on a GPS tick and return a trigger, or None.

    Returns None if an emergency is already open, or if a pending one is
    waiting for the user to confirm (avoids duplicates).
    """
    if ctx.emergency_open:
        return None
    if ctx.pending_trigger is not None:
        return None

    if ctx.attivita in FLIGHT_ACTIVITIES:
        return _eval_flight(ctx)
    elif ctx.attivita in GROUND_ACTIVITIES:
        return _eval_ground(ctx, cfg, now)
    return None


def _eval_flight(ctx: EmContext) -> Optional[EmergencyTrigger]:
    """Flight rule: DESCENDING_FAST -> LANDED means landed under reserve chute."""
    if (ctx.current_sm_state == FlightState.LANDED
            and ctx.previous_sm_state == FlightState.DESCENDING_FAST):
        return EmergencyTrigger.AUTO_CHUTE
    return None


def _eval_ground(ctx: EmContext, cfg: EmConfig, now: datetime) -> Optional[EmergencyTrigger]:
    """Ground rules:
      1. STATIONARY after IMPACT for > impact_recovery_s -> AUTO_IMPACT
      2. STATIONARY without impact for > immobile_emergency_s -> AUTO_IMMOBILE
    """
    if ctx.current_sm_state != GroundState.STATIONARY:
        return None

    seconds_stationary = (now - ctx.state_entered_at).total_seconds()

    # An impact only counts if it hasn't been cleared by a later ack.
    impact_relevant = ctx.impact_at
    if impact_relevant and ctx.ack_at and ctx.ack_at > impact_relevant:
        impact_relevant = None

    # General ack cooldown, to avoid false positives right after "I'm fine".
    if ctx.ack_at:
        time_since_ack = (now - ctx.ack_at).total_seconds()
        if time_since_ack < cfg.ack_cooldown_s:
            return None

    # Rule 1: impact then motionless.
    if impact_relevant and seconds_stationary >= cfg.impact_recovery_s:
        return EmergencyTrigger.AUTO_IMPACT

    # Rule 2: prolonged stop without impact.
    if not impact_relevant and seconds_stationary >= cfg.immobile_emergency_s:
        return EmergencyTrigger.AUTO_IMMOBILE

    return None


# Default config, used when the DB is not reachable.
DEFAULT_CONFIG = EmConfig()


# Config metadata for the admin UI: (key, category, description, type).
# Descriptions stay in Italian, they are shown to the admin as-is.
CONFIG_META = [
    ("takeoff_speed_kmh",    "volo", "Velocità minima decollo (km/h)",                          "float"),
    ("takeoff_alt_m",        "volo", "Quota alternativa per confermare decollo (m)",              "float"),
    ("takeoff_confirm_s",    "volo", "Secondi in condizione decollo per confermare",              "float"),
    ("landing_speed_kmh",    "volo", "Velocità massima atterraggio (km/h)",                      "float"),
    ("landing_alt_m",        "volo", "Quota massima atterraggio (m)",                            "float"),
    ("landing_confirm_s",    "volo", "Secondi in condizione atterraggio per confermare",          "float"),
    ("descending_vspeed_ms", "volo", "Velocità verticale soglia paracadute (m/s, negativo)",     "float"),
    ("descending_confirm_s", "volo", "Secondi in discesa rapida per confermare",                  "float"),
    ("signal_lost_min",      "volo", "Minuti senza segnale OGN in volo → emergenza",             "float"),

    ("moving_speed_kmh",      "terrestre", "Velocità minima per considerarsi in movimento (km/h)",       "float"),
    ("stationary_confirm_s",  "terrestre", "Secondi sotto soglia velocità → STATIONARY",                 "float"),
    ("max_gap_s",             "terrestre", "Silenzio GPS > N secondi → azzera streak (volo + terrestre)", "float"),
    ("impact_recovery_s",     "terrestre", "Secondi fermo dopo impatto → AUTO_IMPACT",                   "float"),
    ("immobile_emergency_s",  "terrestre", "Secondi fermo senza impatto → AUTO_IMMOBILE",                "float"),
    ("ack_cooldown_s",        "terrestre", "Secondi di pausa dopo 'sto bene' prima di riallarmare",                          "float"),
    ("pending_timeout_s",     "terrestre", "Secondi per confermare o annullare l'emergenza dal telefono (poi auto-confirm)", "float"),
]
