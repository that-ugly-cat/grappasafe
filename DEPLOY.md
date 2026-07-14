# Deploying GrappaSafe

GrappaSafe is a single FastAPI app backed by one SQLite file. The OGN worker runs in a
background thread, so there are no external services to run besides the app itself.

## 1. Configuration (environment variables)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | **yes, in production** | `change-me-in-production` | signs the session cookie — set a long random value |
| `GRAPPASAFE_DB` | no | `grappasafe.db` | path to the SQLite file (`/data/grappasafe.db` in Docker) |
| `AREA_LAT` / `AREA_LON` / `AREA_RADIUS_KM` | no | Monte Grappa, 19 km | monitoring area |
| `APRS_USER` | no | `GSAFE1` | OGN/APRS receive callsign (passcode derived from it; keep it short and unique) |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | no | empty | Telegram notifications (skipped if empty) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `NOTIFY_EMAIL` | no | empty | email notifications (skipped if unset) |
| `ADMIN_USER` / `ADMIN_PASS` / `ADMIN_NOME` / `ADMIN_COGNOME` | no | `admin` / `changeme` | initial admin, created by `seed.py` |

Generate a secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 2. Elevation tiles

Altitude thresholds are computed above ground level from SRTM1 tiles. Fetch them once
(the app still runs without them, falling back to AMSL with reduced accuracy):

```bash
./fetch_tiles.sh
```

This downloads `N45E011.hgt` and `N45E012.hgt` (~52 MB) into `tiles/`. With Docker they are
baked into the image at build time, so run this before building.

## 3. Local / bare-metal

```bash
pip install -r requirements.txt
cp .env.example .env         # set SECRET_KEY and notification channels
python seed.py               # first run only
./fetch_tiles.sh
uvicorn app:app --host 0.0.0.0 --port 8000
```

## 4. Docker

```bash
cp .env.example .env         # set SECRET_KEY and notification channels
./fetch_tiles.sh             # tiles are copied into the image
docker compose up -d --build
```

`docker-compose.yml` maps the app to `127.0.0.1:8010` and mounts `./data` for the SQLite
file. Seed the admin user once the container is up:

```bash
docker compose exec api python seed.py
```

## 5. Reverse proxy (HTTPS)

Behind Caddy on `grappasafe.borant.eu`:

```
grappasafe.borant.eu {
    reverse_proxy localhost:8010
}
```

Reload: `sudo systemctl reload caddy`. HTTPS certificates are issued automatically.

## 6. Updating

```bash
git pull
docker compose up -d --build
```

## 7. Backup

The whole state is the SQLite file under `data/`. Back it up with a copy or `sqlite3 .backup`.
