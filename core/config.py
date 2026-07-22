import os


def aprs_passcode(callsign: str) -> int:
    """APRS-IS passcode for a callsign. A valid passcode is required for the
    server to honour the geographic filter on the receive feed."""
    call = callsign.upper().split("-")[0]
    code = 0x73E2
    for i, c in enumerate(call):
        if i % 2 == 0:
            code ^= ord(c) << 8
        else:
            code ^= ord(c)
    return code & 0x7FFF


# Monitoring area
AREA_LAT    = float(os.getenv("AREA_LAT", "45.85261987481419"))
AREA_LON    = float(os.getenv("AREA_LON", "11.771344896002997"))
AREA_RADIUS_KM = float(os.getenv("AREA_RADIUS_KM", "19.0"))

# OGN / APRS. The passcode is derived from the callsign, so pick a short,
# unique callsign (a shared one gets kicked off APRS-IS).
APRS_USER   = os.getenv("APRS_USER", "GSAFE1")
APRS_PASS   = aprs_passcode(APRS_USER)

# Notifications (Telegram + email/SMTP + recipients) are configured entirely
# from the admin Notifiche page, stored in the config table — no env vars.

# Web session
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
