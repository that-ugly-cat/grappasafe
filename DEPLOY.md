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
| `ADMIN_USER` / `ADMIN_PASS` / `ADMIN_NOME` / `ADMIN_COGNOME` | no | `admin` / `changeme` | initial admin, created by `seed.py` |

Telegram and email notifications are **not** env vars — they are configured from the admin
**Notifiche** page and stored in the database (see §6).

Generate a secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 2. Tiles

**Elevation (SRTM1).** Altitude thresholds are computed above ground level. Fetch once (the
app still runs without them, falling back to AMSL with reduced accuracy):

```bash
./fetch_tiles.sh          # N45E011.hgt + N45E012.hgt (~52 MB) into tiles/
```

With Docker these are baked into the image at build time, so run it before building.

**Offline map (OpenTopoMap).** Optional, only for the mobile app's offline map. Fetch the
raster tiles for the monitored circle once (zoom 9–16, ~350 MB), served under `/map-tiles/`:

```bash
python fetch_map_tiles.py
```

Unlike the SRTM tiles these are **not** baked into the image — they live in a host volume
(`./map_tiles`, see `docker-compose.yml`). With Docker, fetch them into that volume from the
running container, so no rebuild is needed:

```bash
docker compose exec api python fetch_map_tiles.py
```

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
file and `./map_tiles` for the offline map tiles. Seed the admin user once the container is up:

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

## 6. Notifications

Emergency events — **opened, acknowledged, resolved** — are pushed to a Telegram group, each
with the salient details and a link to the emergency page; the opening event also goes out by
email. Configure Telegram from the admin **Notifiche** page (applied within 60 s, no restart):

- **Bot token** — from `@BotFather`.
- **Group chat id** — add the bot to the group, send a message, then read `chat.id` from
  `https://api.telegram.org/bot<TOKEN>/getUpdates` (group ids start with `-100`).
- **Public base URL** — e.g. `https://grappasafe.borant.eu`, used to build the emergency-page
  link inside the messages.
- An **on/off toggle** mutes notifications without clearing the token.

Email (used for the **password-reset** flow and, optionally, the emergency alert) is
configured in the same page: SMTP server, sender, an on/off toggle, and one or more
recipients for emergency emails (comma-separated), with a **Salva e invia email di prova**
button. The page also carries the **in-emergency message** shown on the subject's phone —
leave it empty to use the app's own text, translated into the app's language; set it only to
force a fixed, single-language message. All notification settings live in the database —
there are no notification env vars.

## 7. Updating

```bash
git pull
docker compose up -d --build
```

## 8. Backup

The whole state is the SQLite file under `data/`. Back it up with a copy or `sqlite3 .backup`.
