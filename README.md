<p align="center">
  <b>GrappaSafe</b><br>
  <i>Outdoor safety monitoring for the Monte Grappa flying community.</i>
</p>

---

GrappaSafe tracks pilots and outdoor athletes across a 19 km radius around Monte Grappa
and raises an alarm when something looks wrong. It merges two data sources — a mobile app
(GPS + accelerometer) and the live OGN/FLARM APRS feed — so it covers both people running
the app and any transponder-equipped aircraft in the area. When an emergency is detected it
notifies the admins over Telegram and email with the subject's position and medical details.

The mobile client lives in a separate repo,
[grappasafe-mobile](https://github.com/that-ugly-cat/grappasafe-mobile) (React Native /
Expo); this repo is the backend and the web panels it talks to.

## How it works

The core is split in two:

- **State machine** — a pure kinematic description of what an entity is doing
  (`GROUND / AIRBORNE / DESCENDING_FAST / LANDED` in flight, `MOVING / STATIONARY / IMPACT`
  on the ground). Transitions are confirmed over time, not per tick, so an uneven GPS
  stream doesn't produce false positives.
- **Emergency manager** — decides when a situation becomes an emergency, from the states
  above and a set of thresholds editable at runtime from the admin UI.

Emergency triggers:

- **Manual SOS** — the subject taps the button in the app. Fires immediately.
- **Reserve chute** — a fast vertical descent (`DESCENDING_FAST`) into a landing. Fires
  immediately.
- **Impact** — a hard acceleration peak followed by staying put. Goes through a confirmation
  window: the subject has a few minutes to cancel from the phone before the alarm is raised.
- **Prolonged immobility** — motionless for a long time with no preceding impact. Same
  confirmation window; off by default, since a long rest is usually just a rest.

Across all of them:

- **Immobility is decided by displacement** over a time window, not by instantaneous GPS
  speed, so a jittery pin can't reset the timer. Points with poor accuracy are ignored, and
  an impact is forgotten once the person walks away from the spot.
- A background **sweep auto-confirms an unanswered pending** even if the phone stops sending
  (a device that dies after an impact still gets the alarm opened server-side).
- An operator can **take an emergency in charge** (acknowledge) before resolving it; the app
  surfaces that to the person in distress. Resolving an emergency ends the subject's active
  session.

### App, OGN, and both

The two sources observe different things, so they raise different alarms and back each other up:

- **App (GPS + accelerometer).** The full set: manual SOS, reserve chute (confirmed by a
  post-landing immobility check), impact (accelerometer, in flight and on the ground), and
  prolonged immobility. Its vertical speed is derived from GPS altitude, so it is noisy —
  there is no barometer.
- **OGN / FLARM (APRS feed).** Reserve chute only. FLARM reports a clean vertical speed, so
  the fast-descent detection is reliable even for a soft reserve — but there is no
  accelerometer (no impact) and the beacons usually stop on the ground (no immobility check,
  so the chute fires on the `DESCENDING_FAST → LANDED` transition itself).
- **App + OGN (same pilot, device linked to the account).** Both nets run and complement each
  other: OGN's clean vspeed catches a soft reserve the app's noisy GPS might miss, the app's
  accelerometer catches a hard impact OGN cannot see. Only **one open emergency per person**
  is kept — whichever source fires first wins and the other is **deduplicated by resolved
  identity**. Impact is never fed into the OGN path: the two nets stay independent.

A configurable **horizontal-speed cap** on the fast-descent check keeps powered aircraft
diving through the area from being mistaken for a reserve.

Altitude thresholds are computed above ground level using local SRTM1 tiles.

## Features

- **Two sources merged**: mobile app and OGN/FLARM, resolved to the same identity through
  per-user device linking, so an OGN emergency carries name, phone and medical info.
- **Live admin dashboard**: Leaflet map with all active entities, colour-coded by activity
  (blue for aerial, orange for ground), filters, and an open-emergencies panel. A
  full-screen **new-emergency popup** appears on any admin page as soon as one comes in.
- **Mobile app client**: public self-registration, profile self-edit, activity sessions
  with background GPS, manual and automatic emergencies with a configurable message, an
  **offline OpenTopoMap** of the monitored circle, and a live-tracking share link.
- **User self-service**: from the web or the app, users manage their profile and link their
  OGN/FLARM devices.
- **Runtime configuration**: every state-machine / emergency threshold is editable from the
  admin config page, applied within 60 s with no restart.
- **Shareable live map**: a public `/map/{token}` URL that refreshes every 15 s.
- **Notifications**: emergency **opened / acknowledged / resolved** pushed to a Telegram
  group — salient details plus a link to the emergency page — and email on open. Bot token,
  group id, the link's base URL and an on/off toggle are set from the admin panel, with the
  environment values as a fallback.

## API for the app

Under the session cookie, HTTPS: `POST /api/login`, `/api/register`, `GET`/`PUT /api/me`,
`GET /api/config` (monitored area), `POST /api/session/{start,end,ok}` + `GET status`,
`POST /api/gps`, `POST /api/emergency` + `/emergency/confirm` + `GET /api/emergency/status`,
`GET /api/map/{token}` (public live track), and the offline tiles under `/map-tiles/`.

## Quick start

```bash
git clone https://github.com/that-ugly-cat/grappasafe.git
cd grappasafe
pip install -r requirements.txt
cp .env.example .env         # set SECRET_KEY, notification channels
python seed.py               # create the initial admin user
./fetch_tiles.sh             # SRTM elevation tiles (~52 MB), for above-ground altitude
python fetch_map_tiles.py    # optional: OpenTopoMap tiles for the app's offline map (~350 MB)
uvicorn app:app --reload
```

Open http://localhost:8000/ and log in as the admin created by `seed.py`. Schema
migrations run automatically on startup, so an existing database is upgraded in place.

## Stack

FastAPI · SQLite · Jinja2 · Leaflet. No build step. The OGN worker and the pending-sweep
run in background threads inside the same process.

```
app.py              — routes: auth, GPS ingest, sessions, emergencies, admin, app API, map
db.py               — SQLite schema, migrations and queries
auth.py             — password hashing and session/role guards
seed.py             — create the initial admin user
fetch_tiles.sh      — download SRTM1 elevation tiles
fetch_map_tiles.py  — prefetch OpenTopoMap tiles for the app's offline map
core/
  config.py         — environment configuration (monitoring area, secrets)
  state_machine.py  — kinematic state machine (flight + ground)
  emergency.py      — emergency manager, thresholds, config metadata
  ogn.py            — OGN/APRS worker: area filter, flight SM, reserve-chute on landing
  terrain.py        — SRTM1 tile reader for above-ground-level altitude
  notify.py         — Telegram + email notifications
templates/          — dashboard, emergencies (list + detail), users, config/state settings,
                      profile, me, public map, shared admin topbar
```

See [DEPLOY.md](DEPLOY.md) for production deployment.
