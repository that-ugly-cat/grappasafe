import os

# Monitoring area
AREA_LAT    = float(os.getenv("AREA_LAT", "45.85261987481419"))
AREA_LON    = float(os.getenv("AREA_LON", "11.771344896002997"))
AREA_RADIUS_KM = float(os.getenv("AREA_RADIUS_KM", "19.0"))

# OGN / APRS
APRS_USER   = os.getenv("APRS_USER", "grappasafe")
APRS_PASS   = int(os.getenv("APRS_PASS", "-1"))   # -1 = read-only

# Notifications
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST        = os.getenv("SMTP_HOST", "")
SMTP_PORT        = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER        = os.getenv("SMTP_USER", "")
SMTP_PASS        = os.getenv("SMTP_PASS", "")
NOTIFY_EMAIL     = os.getenv("NOTIFY_EMAIL", "")

# Web session
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
