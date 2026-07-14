<p align="center">
  <b>GrappaSafe</b><br>
  <i>Outdoor safety monitoring for the Monte Grappa flying community.</i>
</p>

---

GrappaSafe tracks pilots and outdoor athletes across a 19 km radius around Monte Grappa
and raises an alarm when something looks wrong. It merges two data sources: a mobile app
(GPS + accelerometer) and the live OGN/FLARM APRS feed, so it covers both people running
the app and any transponder-equipped glider in the area. When an emergency is detected it
notifies the admins over Telegram and email with the subject's position and medical details.

## How it works

The core is split in two:

- **State machine** — a pure kinematic description of what an entity is doing
  (`GROUND / AIRBORNE / DESCENDING_FAST / LANDED` in flight, `MOVING / STATIONARY / IMPACT`
  on the ground). Transitions are confirmed over time, not per tick, so an uneven GPS
  stream doesn't produce false positives.
- **Emergency manager** — decides when a situation becomes an emergency, from the states
  above and a set of thresholds editable at runtime from the admin UI. Manual SOS, reserve
  chute and OGN signal loss fire immediately; impact and prolonged immobility go through a
  confirmation window before the alarm is raised.

Altitude thresholds are computed above ground level using local SRTM1 tiles.

## Features

- **Two sources merged**: mobile app and OGN/FLARM, resolved to the same identity through
  per-user device linking (an OGN emergency carries name, phone and medical info).
- **Live admin dashboard**: Leaflet map with all active entities, filters, and an open-
  emergencies panel with full contact and medical data.
- **User self-service**: pilots log in on the web to manage their profile and link their
  OGN/FLARM devices.
- **Runtime configuration**: every state-machine / emergency threshold is editable from
  `/admin/config`, applied within 60 s with no restart.
- **Shareable live map**: a public `/map/{token}` URL for family and friends.
- **Notifications** over Telegram and email.

## Quick start

```bash
git clone https://github.com/that-ugly-cat/grappasafe.git
cd grappasafe
pip install -r requirements.txt
cp .env.example .env         # set SECRET_KEY, notification channels
python seed.py               # create the initial admin user
./fetch_tiles.sh             # download the SRTM elevation tiles (~52 MB)
uvicorn app:app --reload
```

Open http://localhost:8000/ and log in as the admin created by `seed.py`.

## Stack

FastAPI · SQLite · Jinja2 · Leaflet. No build step. The OGN worker runs in a background
thread inside the same process.

```
app.py              — routes: auth, GPS ingest, sessions, emergencies, admin, map
db.py               — SQLite schema and queries
auth.py             — password hashing and session/role guards
seed.py             — create the initial admin user
core/
  config.py         — environment configuration
  state_machine.py  — kinematic state machine (flight + ground)
  emergency.py      — emergency manager, thresholds, config metadata
  ogn.py            — OGN/APRS worker, area filter, signal-loss watcher
  terrain.py        — SRTM1 tile reader for above-ground-level altitude
  notify.py         — Telegram + email notifications
templates/          — login, dashboard, users, config, profile, me, map
```

See [DEPLOY.md](DEPLOY.md) for production deployment.
