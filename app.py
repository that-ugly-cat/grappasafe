import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from auth import hash_password, verify_password, get_current_user, require_auth, require_admin
from core.config import SECRET_KEY
from core.notify import notify_emergency
from core.ogn import ogn_worker
from core.state_machine import SessionTracker, update_sm
from core.terrain import compute_agl
from core.emergency import (
    EmConfig, EmContext, EmergencyTrigger, evaluate_em, update_em_context, ack_ok, ogn_kind,
)
import db

_stop_flag = threading.Event()
_session_trackers: dict[int, SessionTracker] = {}   # session_id -> SM tracker
_em_contexts:      dict[int, EmContext]       = {}   # session_id -> EM context
_trackers_lock = threading.Lock()

# ── Config cache ──────────────────────────────────────────────────────────────
_config_cache: EmConfig = EmConfig()
_config_loaded_at: datetime = datetime.min.replace(tzinfo=timezone.utc)
_CONFIG_TTL = 60  # secondi

def _get_config() -> EmConfig:
    global _config_cache, _config_loaded_at
    now = datetime.now(timezone.utc)
    if (now - _config_loaded_at).total_seconds() > _CONFIG_TTL:
        try:
            _config_cache = db.load_em_config()
        except Exception:
            pass  # keep the previous cache
        _config_loaded_at = now
    return _config_cache

def _invalidate_config():
    global _config_loaded_at
    _config_loaded_at = datetime.min.replace(tzinfo=timezone.utc)

# ── Emergency rules cache ─────────────────────────────────────────────────────
_rules_cache: dict = {}
_rules_loaded_at: datetime = datetime.min.replace(tzinfo=timezone.utc)

def _get_rules() -> dict:
    global _rules_cache, _rules_loaded_at
    now = datetime.now(timezone.utc)
    if (now - _rules_loaded_at).total_seconds() > _CONFIG_TTL:
        try:
            _rules_cache = db.load_em_rules()
        except Exception:
            pass  # keep the previous cache
        _rules_loaded_at = now
    return _rules_cache

def _invalidate_rules():
    global _rules_loaded_at
    _rules_loaded_at = datetime.min.replace(tzinfo=timezone.utc)

db.init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=ogn_worker, args=(_stop_flag,), daemon=True)
    t.start()
    yield
    _stop_flag.set()


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Auth ──────────────────────────────────────────────────────────────────────

def _home_for(user) -> str:
    """Post-login landing page by role: admin -> dashboard, user -> /me."""
    return "/dashboard" if user.get("role") == "admin" else "/me"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(_home_for(user), status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = db.get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request, "login.html", {"error": "Credenziali non valide"})
    # Web login is open to every user: admins go to the dashboard, regular
    # users to their /me home (profile + OGN devices).
    request.session["user"] = {"id": user["id"]}
    return RedirectResponse(_home_for(user), status_code=303)


@app.post("/api/login")
async def api_login(request: Request):
    """
    JSON login for the mobile app. Accepts any user, not only admins.
    The session cookie is returned via Set-Cookie (handled by Starlette).
    """
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    user = db.get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return JSONResponse({"ok": False, "error": "Credenziali non valide"}, status_code=401)
    request.session["user"] = {"id": user["id"]}
    return JSONResponse({"ok": True})


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ── Dashboard (live map, admin only) ─────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


# ── User home (/me): profile + OGN devices ───────────────────────────────────

@app.get("/me", response_class=HTMLResponse)
async def me_home(request: Request):
    user, redir = require_auth(request)
    if redir:
        return redir
    return templates.TemplateResponse(request, "me.html", {
        "user": user,
        "devices": db.get_user_devices(user["id"]),
    })


# ── Device API (user self-service) ────────────────────────────────────────────

@app.get("/api/me/devices")
async def api_my_devices(request: Request):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return JSONResponse(db.get_user_devices(user["id"]))


@app.post("/api/me/devices")
async def api_add_device(request: Request):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    display_name = (body.get("display_name") or "").strip()
    if not display_name:
        raise HTTPException(400, "Il nome del device è obbligatorio")
    did = db.add_device(
        user["id"], display_name,
        ogn_id=(body.get("ogn_id") or "").strip() or None,
        activity=(body.get("activity") or "").strip() or None,
        color=body.get("color") or "#3b82f6",
    )
    return JSONResponse({"id": did})


@app.put("/api/me/devices/{device_id}")
async def api_update_device(request: Request, device_id: int):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    dev = db.get_device(device_id)
    if not dev or dev["owner_user_id"] != user["id"]:
        raise HTTPException(404, "Device non trovato")
    body = await request.json()
    display_name = (body.get("display_name") or "").strip()
    if not display_name:
        raise HTTPException(400, "Il nome del device è obbligatorio")
    db.update_device(
        device_id, user["id"], display_name,
        ogn_id=(body.get("ogn_id") or "").strip() or None,
        activity=(body.get("activity") or "").strip() or None,
        color=body.get("color") or "#3b82f6",
    )
    return JSONResponse({"ok": True})


@app.delete("/api/me/devices/{device_id}")
async def api_delete_device(request: Request, device_id: int):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    dev = db.get_device(device_id)
    if not dev or dev["owner_user_id"] != user["id"]:
        raise HTTPException(404, "Device non trovato")
    db.delete_device(device_id, user["id"])
    return JSONResponse({"ok": True})


# ── User profile ──────────────────────────────────────────────────────────────

@app.get("/profile", response_class=HTMLResponse)
async def profile_get(request: Request):
    user, redir = require_auth(request)
    if redir:
        return redir
    return templates.TemplateResponse(request, "profile.html", {"user": user})


@app.post("/profile")
async def profile_post(
    request: Request,
    nome: str = Form(...), cognome: str = Form(...),
    telefono: str = Form(""), emergenza_contatto: str = Form(""),
    emergenza_telefono: str = Form(""), gruppo_sanguigno: str = Form(""),
    note_salute: str = Form(""), flarm_id: str = Form(""),
    lingua: str = Form("it"),
):
    user, redir = require_auth(request)
    if redir:
        return redir
    db.update_user_profile(
        user["id"],
        nome=nome, cognome=cognome, telefono=telefono,
        emergenza_contatto=emergenza_contatto,
        emergenza_telefono=emergenza_telefono,
        gruppo_sanguigno=gruppo_sanguigno,
        note_salute=note_salute,
        flarm_id=flarm_id or None,
        lingua=lingua,
    )
    return RedirectResponse("/me", status_code=303)


# ── Session API ───────────────────────────────────────────────────────────────

@app.post("/api/session/start")
async def session_start(request: Request):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    body = await request.json()
    attivita = body.get("attivita")
    valid = {"PARAGLIDER","HANGGLIDER","CYCLIST","CLIMBER","HIKER","RUNNER","OTHER_ON_GROUND"}
    if attivita not in valid:
        raise HTTPException(400, f"attivita deve essere uno di: {valid}")
    existing = db.get_active_session(user["id"])
    if existing:
        db.end_session(existing["id"])
        with _trackers_lock:
            _session_trackers.pop(existing["id"], None)
            _em_contexts.pop(existing["id"], None)
    session_id = db.create_session(user["id"], attivita)
    session    = db.get_session(session_id)
    now        = datetime.now(timezone.utc)
    tracker = SessionTracker(
        session_id=session_id, user_id=user["id"],
        attivita=attivita, state=session["state"],
    )
    ctx = EmContext(
        session_id=session_id, attivita=attivita,
        current_sm_state=session["state"],
        state_entered_at=now,
    )
    with _trackers_lock:
        _session_trackers[session_id] = tracker
        _em_contexts[session_id]      = ctx
    return JSONResponse({"session_id": session_id, "state": session["state"]})


@app.post("/api/session/end")
async def session_end(request: Request):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    session = db.get_active_session(user["id"])
    if not session:
        raise HTTPException(404, "Nessuna sessione attiva")
    db.end_session(session["id"])
    with _trackers_lock:
        _session_trackers.pop(session["id"], None)
        _em_contexts.pop(session["id"], None)
    return JSONResponse({"ok": True})


@app.post("/api/session/ok")
async def session_ok(request: Request):
    """
    User reports "I'm fine":
    - resets the EM context (impact_at, ack cooldown)
    - clears any pending emergency without opening it
    """
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    session = db.get_active_session(user["id"])
    if not session:
        raise HTTPException(404, "Nessuna sessione attiva")
    now = datetime.now(timezone.utc)
    with _trackers_lock:
        ctx = _em_contexts.get(session["id"])
    if ctx:
        ack_ok(ctx, now)   # also clears pending_trigger/pending_since
    return JSONResponse({"ok": True})


@app.post("/api/emergency/confirm")
async def emergency_confirm(request: Request):
    """
    User confirms the pending emergency from the phone.
    Turns the pending into an open emergency (notifies admins/contacts).
    If the server had already auto-confirmed it, replies ok with already=True.
    """
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    session = db.get_active_session(user["id"])
    if not session:
        raise HTTPException(404, "Nessuna sessione attiva")

    body    = await request.json()
    lat     = body.get("lat")
    lon     = body.get("lon")
    alt_m   = body.get("alt_m")

    with _trackers_lock:
        ctx     = _em_contexts.get(session["id"])
        tracker = _session_trackers.get(session["id"])

    if not ctx:
        raise HTTPException(404, "Contesto sessione non trovato")

    if ctx.emergency_open:
        return JSONResponse({"ok": True, "already": True})

    if ctx.pending_trigger:
        t                   = ctx.pending_trigger
        ctx.pending_trigger = None
        ctx.pending_since   = None
        _handle_emergency(session["id"], ctx, tracker, t, lat, lon, alt_m)

    return JSONResponse({"ok": True, "already": False})


# ── Current session status API ────────────────────────────────────────────────

@app.get("/api/session/status")
async def session_status(request: Request):
    """
    Status of the current user's active session.
    Used by the mobile app when tracking mounts, to check the session is still
    alive on the server (avoids orphan GPS points after a server restart).
    """
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"active": False, "error": "not authenticated"}, status_code=401)
    session = db.get_active_session(user["id"])
    if not session:
        return JSONResponse({"active": False})
    return JSONResponse({
        "active":     True,
        "session_id": session["id"],
        "attivita":   session["attivita"],
        "state":      session["state"],
    })


# ── API — GPS points ──────────────────────────────────────────────────────────

@app.post("/api/gps")
async def gps_point(request: Request):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    body    = await request.json()
    session = db.get_active_session(user["id"])
    if not session:
        raise HTTPException(404, "Nessuna sessione attiva")

    session_id = session["id"]
    ts  = body.get("ts") or datetime.now(timezone.utc).isoformat()
    lat = body.get("lat")
    lon = body.get("lon")
    if lat is None or lon is None:
        raise HTTPException(400, "lat e lon obbligatori")

    # speed_kmh: expo-location reports speed in m/s, convert it
    speed_ms  = body.get("speed_ms")
    speed_kmh = body.get("speed_kmh") or ((speed_ms * 3.6) if speed_ms is not None else None)

    # vspeed_ms: computed server-side from the altitude delta
    alt_m     = body.get("alt_m")
    vspeed_ms = body.get("vspeed_ms")
    if vspeed_ms is None and alt_m is not None:
        prev = db.get_latest_point(session_id)
        if prev and prev.get("alt_m") is not None and prev.get("ts"):
            try:
                t1 = datetime.fromisoformat(prev["ts"])
                t2 = datetime.fromisoformat(ts)
                dt = (t2 - t1).total_seconds()
                if dt > 0:
                    vspeed_ms = (alt_m - prev["alt_m"]) / dt
            except Exception:
                pass

    db.write_gps_point(
        session_id=session_id, ts=ts, lat=lat, lon=lon,
        alt_m=alt_m, accuracy_m=body.get("accuracy_m"),
        battery_pct=body.get("battery_pct"),
        speed_kmh=speed_kmh, vspeed_ms=vspeed_ms,
        motion_state=body.get("motion_state"),
        impact_detected=body.get("impact_detected", False),
        accel_magnitude=body.get("accel_magnitude"),
    )

    # Enrich the point with the server-side computed values
    point = dict(body)
    point["ts"]        = ts
    point["speed_kmh"] = speed_kmh or 0.0
    point["vspeed_ms"] = vspeed_ms or 0.0
    now = datetime.fromisoformat(ts) if isinstance(ts, str) else ts

    # Replace alt_m with AGL for the SM (the DB already stored AMSL above)
    if alt_m is not None:
        point["alt_m"] = compute_agl(lat, lon, alt_m)

    # Fetch or create the tracker and context
    with _trackers_lock:
        tracker = _session_trackers.get(session_id)
        ctx     = _em_contexts.get(session_id)

    if not tracker:
        tracker = SessionTracker(
            session_id=session_id, user_id=user["id"],
            attivita=session["attivita"], state=session["state"],
        )
        ctx = EmContext(
            session_id=session_id, attivita=session["attivita"],
            current_sm_state=session["state"],
            state_entered_at=now,
        )
        with _trackers_lock:
            _session_trackers[session_id] = tracker
            _em_contexts[session_id]      = ctx

    cfg   = _get_config()
    rules = _get_rules()

    # 1. Update the SM
    old_state  = tracker.state
    sm_changed = update_sm(tracker, point, cfg)

    if sm_changed and not ctx.emergency_open:
        # Persist the new SM state only when not in emergency
        db.update_session_state(session_id, tracker.state)
        update_em_context(ctx, old_state, tracker.state, now)
    elif sm_changed and ctx.emergency_open:
        # The SM keeps running internally but the DB stays at EMERGENCY
        update_em_context(ctx, old_state, tracker.state, now)

    # 2. Evaluate the EM. Each rule's mode (immediate / pending) comes from its
    #    config: immediate opens the emergency now, pending gives the user
    #    pending_timeout_s to confirm or cancel from the phone.
    trigger = evaluate_em(ctx, cfg, rules, now, speed_kmh=speed_kmh)
    if trigger:
        rule = rules.get(trigger.value)
        mode = rule["mode"] if rule else "immediate"
        if mode == "immediate":
            _handle_emergency(session_id, ctx, tracker, trigger, lat, lon, alt_m)
        elif ctx.pending_trigger is None:
            ctx.pending_trigger = trigger
            ctx.pending_since   = now

    # 3. Auto-confirm an expired pending
    # If the user did not answer within pending_timeout_s, the server confirms
    # the emergency on its own (belt and suspenders on top of the client).
    if not ctx.emergency_open and ctx.pending_trigger and ctx.pending_since:
        elapsed = (now - ctx.pending_since).total_seconds()
        if elapsed >= cfg.pending_timeout_s:
            t = ctx.pending_trigger
            ctx.pending_trigger = None
            ctx.pending_since   = None
            _handle_emergency(session_id, ctx, tracker, t, lat, lon, alt_m)

    # 4. Build the response
    pending_em_resp = None
    if not ctx.emergency_open and ctx.pending_trigger and ctx.pending_since:
        elapsed   = (now - ctx.pending_since).total_seconds()
        remaining = max(0.0, cfg.pending_timeout_s - elapsed)
        pending_em_resp = {
            "trigger":    ctx.pending_trigger.value,
            "expires_in": int(remaining),
        }

    return JSONResponse({
        "sm_state":          tracker.state,
        "db_state":          "EMERGENCY" if ctx.emergency_open else tracker.state,
        "pending_emergency": pending_em_resp,
    })


# ── Emergency helper ──────────────────────────────────────────────────────────

def _handle_emergency(session_id, ctx, tracker, trigger, lat, lon, alt_m):
    """Open an emergency: update the context, the DB, and send notifications."""
    ctx.emergency_open = True
    db.update_session_state(session_id, "EMERGENCY")
    eid = db.create_emergency(
        trigger=trigger.value,
        lat=lat, lon=lon, alt_m=alt_m,
        session_id=session_id,
    )
    notify_emergency(eid)


# ── Manual emergency API ──────────────────────────────────────────────────────

@app.post("/api/emergency")
async def emergency_manual(request: Request):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    body    = await request.json()
    session = db.get_active_session(user["id"])
    lat, lon, alt_m = body.get("lat"), body.get("lon"), body.get("alt_m")

    if session:
        with _trackers_lock:
            tracker = _session_trackers.get(session["id"])
            ctx     = _em_contexts.get(session["id"])
        if not ctx:
            ctx = EmContext(
                session_id=session["id"], attivita=session["attivita"],
                current_sm_state=session["state"],
                state_entered_at=datetime.now(timezone.utc),
            )
        _handle_emergency(session["id"], ctx, tracker, EmergencyTrigger.MANUAL, lat, lon, alt_m)
    else:
        # Emergency without an active session (e.g. outside tracking)
        eid = db.create_emergency(
            trigger="MANUAL", lat=lat, lon=lon, alt_m=alt_m,
            note="Manual emergency without session",
        )
        notify_emergency(eid)

    return JSONResponse({"ok": True})


# ── Public shareable map ──────────────────────────────────────────────────────

@app.get("/map/{share_token}", response_class=HTMLResponse)
async def map_view(request: Request, share_token: str):
    user = db.get_user_by_share_token(share_token)
    if not user:
        raise HTTPException(404, "Link non valido")
    session = db.get_active_session(user["id"])
    track   = db.get_track(session["id"]) if session else []
    return templates.TemplateResponse(request, "map.html", {
        "user": user,
        "session": session,
        "track": track,
    })


@app.get("/api/map/{share_token}")
async def map_api(share_token: str):
    """Polling endpoint for the live map."""
    user = db.get_user_by_share_token(share_token)
    if not user:
        raise HTTPException(404)
    session = db.get_active_session(user["id"])
    if not session:
        return JSONResponse({"active": False})
    track   = db.get_track(session["id"], limit=200)
    latest  = track[-1] if track else None
    return JSONResponse({
        "active":   True,
        "session":  {"id": session["id"], "attivita": session["attivita"], "state": session["state"]},
        "latest":   latest,
        "track":    track,
        "user":     {"nome": user["nome"], "cognome": user["cognome"]},
    })


# ── Current profile API (for the mobile app) ──────────────────────────────────

@app.get("/api/me")
async def api_me(request: Request):
    user, redir = require_auth(request)
    if redir:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return JSONResponse({
        "id":       user["id"],
        "username": user["username"],
        "nome":     user["nome"] or "",
        "cognome":  user["cognome"] or "",
        "is_admin": user.get("role") == "admin",
    })


# ── Admin: users and config ──────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def admin_redirect(request: Request):
    return RedirectResponse("/dashboard", status_code=301)

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    return templates.TemplateResponse(request, "users.html", {"user": user})

_CAT_LABELS = {
    "volo":      "Volo (parapendio / deltaplano / aliante)",
    "terrestre": "Attività terrestri",
    "comune":    "Comune",
}
_CAT_ORDER = ["volo", "terrestre", "comune"]


def _sections(rows):
    from collections import defaultdict
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["categoria"]].append(r)
    return [
        {"key": c, "label": _CAT_LABELS.get(c, c), "rows": by_cat[c]}
        for c in _CAT_ORDER if by_cat.get(c)
    ]


@app.get("/admin/config")
async def admin_config_redirect(request: Request):
    return RedirectResponse("/admin/states-settings", status_code=301)


@app.get("/admin/states-settings", response_class=HTMLResponse)
async def admin_states_settings(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    rows = [r for r in db.get_all_config() if r["macchina"] == "SM"]
    return templates.TemplateResponse(request, "states_settings.html", {
        "user": user,
        "sections": _sections(rows),
        "config": rows,
    })


# Rule display metadata for the emergency-settings page.
_FLIGHT_OPTS = [("PARAGLIDER", "Parapendio"), ("HANGGLIDER", "Deltaplano"), ("GLIDER", "Aliante")]
_GROUND_OPTS = [("CYCLIST", "Ciclismo"), ("CLIMBER", "Arrampicata"), ("HIKER", "Escursionismo"),
                ("RUNNER", "Trail running"), ("OTHER_ON_GROUND", "Altro")]
_RULE_UI = {
    "AUTO_CHUTE": {
        "title": "Paracadute di emergenza",
        "desc": "Transizione <code>descending_fast → landed</code> seguita da immobilità: sceso col paracadute, atterrato e fermo.",
        "activities": _FLIGHT_OPTS, "param_key": "chute_immobile_s", "param_label": "Immobile per",
    },
    "AUTO_IMPACT": {
        "title": "Impatto + immobile",
        "desc": "Dopo un <code>impact</code>, fermo per il tempo indicato.",
        "activities": _GROUND_OPTS, "param_key": "impact_recovery_s", "param_label": "Fermo per",
    },
    "AUTO_IMMOBILE": {
        "title": "Immobilità prolungata",
        "desc": "Fermo a lungo senza impatto recente. Spesso è solo una pausa: off di default.",
        "activities": _GROUND_OPTS, "param_key": "immobile_emergency_s", "param_label": "Fermo per",
    },
}
_RULE_ORDER = ["AUTO_CHUTE", "AUTO_IMPACT", "AUTO_IMMOBILE"]


@app.get("/admin/emergency-settings", response_class=HTMLResponse)
async def admin_emergency_settings(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    rules = {r["key"]: r for r in db.get_emergency_rules()}
    cfg   = {r["key"]: r for r in db.get_all_config()}
    rule_cards = []
    for key in _RULE_ORDER:
        r = rules.get(key)
        if not r:
            continue
        ui    = _RULE_UI[key]
        param = cfg.get(ui["param_key"])
        rule_cards.append({
            "key": key, "title": ui["title"], "desc": ui["desc"],
            "activities": ui["activities"],
            "applies_set": [a for a in (r["applies_to"] or "").split(",") if a],
            "enabled": bool(r["enabled"]), "mode": r["mode"],
            "param_key": ui["param_key"], "param_label": ui["param_label"],
            "param_value": param["value"] if param else "",
        })
    globals_ = [cfg[k] for k in ("ack_cooldown_s", "pending_timeout_s") if k in cfg]
    return templates.TemplateResponse(request, "emergency_settings.html", {
        "user": user, "rule_cards": rule_cards, "globals": globals_,
    })


@app.post("/api/admin/rules")
async def api_save_rules(request: Request):
    _, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()   # {key: {enabled, applies_to: [...], mode}}
    for key, r in body.items():
        applies_to = ",".join(r.get("applies_to", []))
        db.set_emergency_rule(key, bool(r.get("enabled", True)), applies_to, r.get("mode", "immediate"))
    _invalidate_rules()
    return JSONResponse({"ok": True})

@app.post("/api/admin/config")
async def api_save_config(request: Request):
    _, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()  # {key: value, ...}
    saved = []
    errors = []
    for key, value in body.items():
        try:
            db.set_config_value(key, value)
            saved.append(key)
        except Exception as e:
            errors.append({"key": key, "error": str(e)})
    _invalidate_config()  # forza reload al prossimo tick
    return JSONResponse({"saved": saved, "errors": errors})

@app.get("/api/admin/users")
async def api_list_users(request: Request):
    _, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    users = db.get_all_users()
    return JSONResponse([dict(u) for u in users])

@app.post("/api/admin/users")
async def api_create_user(request: Request):
    _, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    nome     = body.get("nome", "").strip()
    cognome  = body.get("cognome", "").strip()
    if not username or not password or not nome or not cognome:
        raise HTTPException(400, "username, password, nome e cognome sono obbligatori")
    if db.get_user_by_username(username):
        raise HTTPException(400, "Username già esistente")
    uid = db.create_user(
        username, hash_password(password), nome, cognome,
        role=body.get("role", "user"),
        telefono=body.get("telefono") or None,
        gruppo_sanguigno=body.get("gruppo_sanguigno") or None,
        emergenza_contatto=body.get("emergenza_contatto") or None,
        emergenza_telefono=body.get("emergenza_telefono") or None,
        flarm_id=body.get("flarm_id") or None,
        lingua=body.get("lingua", "it"),
        note_salute=body.get("note_salute") or None,
    )
    return JSONResponse({"id": uid})

@app.put("/api/admin/users/{uid}")
async def api_update_user(request: Request, uid: int):
    current, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    user = db.get_user(uid)
    if not user:
        raise HTTPException(404, "Utente non trovato")
    password = body.get("password", "").strip()
    db.update_user_full(
        uid,
        username=body.get("username", user["username"]).strip(),
        password_hash=hash_password(password) if password else None,
        nome=body.get("nome", user["nome"]).strip(),
        cognome=body.get("cognome", user["cognome"]).strip(),
        role=body.get("role", user["role"]),
        telefono=body.get("telefono") or None,
        gruppo_sanguigno=body.get("gruppo_sanguigno") or None,
        emergenza_contatto=body.get("emergenza_contatto") or None,
        emergenza_telefono=body.get("emergenza_telefono") or None,
        flarm_id=body.get("flarm_id") or None,
        lingua=body.get("lingua", "it"),
        note_salute=body.get("note_salute") or None,
    )
    return JSONResponse({"ok": True})

@app.delete("/api/admin/users/{uid}")
async def api_delete_user(request: Request, uid: int):
    current, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if uid == current["id"]:
        raise HTTPException(400, "Non puoi eliminare te stesso")
    if not db.get_user(uid):
        raise HTTPException(404, "Utente non trovato")
    db.delete_user(uid)
    return JSONResponse({"ok": True})


# ── Admin API used by the dashboard JS ────────────────────────────────────────

@app.get("/api/admin/live")
async def admin_live(request: Request):
    """All active users plus OGN traffic in the area. Used by the map poller."""
    _, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    active  = db.get_all_active_sessions()
    ogn     = db.get_ogn_latest()

    def _agl(lat, lon, alt):
        if alt is None or lat is None or lon is None:
            return None
        return compute_agl(lat, lon, alt)

    entities = []
    app_by_user = {}   # user_id -> app entity, so OGN beacons can merge into it

    for s in active:
        pt = db.get_latest_point(s["id"])
        if not pt:
            continue
        ent = {
            "id":       f"app_{s['id']}",
            "source":   "APP",
            "nome":     f"{s['nome']} {s['cognome']}",
            "attivita": s["attivita"],          # user's live choice: top priority
            "state":    s["state"],
            "lat":      pt["lat"],
            "lon":      pt["lon"],
            "alt_m":    pt.get("alt_m"),
            "agl_m":    _agl(pt["lat"], pt["lon"], pt.get("alt_m")),
            "speed_kmh": pt.get("speed_kmh"),
            "vspeed_ms": pt.get("vspeed_ms"),
            "course_deg": None,   # not tracked for app GPS points
            "battery":  pt.get("battery_pct"),
            "ts":       pt["ts"],
            "share_token": s["share_token"],
            "session_id":  s["id"],
            "linked":   False,
        }
        app_by_user[s["user_id"]] = ent
        entities.append(ent)

    for o in ogn:
        owner = o.get("owner_user_id")

        # Same person already tracked via the app: merge into that entity.
        # The user's declared activity wins; keep the fresher position.
        if owner is not None and owner in app_by_user:
            ent = app_by_user[owner]
            ent["linked"] = True
            if (o["ts"] or "") > (ent["ts"] or ""):
                ent["lat"]        = o.get("lat")
                ent["lon"]        = o.get("lon")
                ent["alt_m"]      = o.get("alt_m")
                ent["agl_m"]      = _agl(o.get("lat"), o.get("lon"), o.get("alt_m"))
                ent["speed_kmh"]  = o.get("speed_kmh")
                ent["vspeed_ms"]  = o.get("vspeed_ms")
                ent["course_deg"] = o.get("course_deg")
                ent["ts"]         = o["ts"]
            continue

        # Standalone OGN entity.
        if o.get("owner_nome") or o.get("owner_cognome"):
            ogn_nome = f"{o.get('owner_nome') or ''} {o.get('owner_cognome') or ''}".strip()
        else:
            ogn_nome = o.get("display_name") or o["ogn_id"]

        # Activity precedence for an OGN beacon: device-declared > aircraft type.
        attivita = o.get("device_activity") or ogn_kind(o.get("aircraft_type"))

        entities.append({
            "id":       f"ogn_{o['ogn_id']}",
            "source":   "OGN",
            "nome":     ogn_nome,
            "linked":   bool(owner),
            "attivita": attivita,
            "state":    o["state"],
            "lat":      o.get("lat"),
            "lon":      o.get("lon"),
            "alt_m":    o.get("alt_m"),
            "agl_m":    _agl(o.get("lat"), o.get("lon"), o.get("alt_m")),
            "speed_kmh": o.get("speed_kmh"),
            "vspeed_ms": o.get("vspeed_ms"),
            "course_deg": o.get("course_deg"),
            "battery":  None,
            "ts":       o["ts"],
            "share_token": None,
            "session_id":  None,
        })

    return JSONResponse(entities)


@app.get("/api/admin/track/{session_id}")
async def admin_track(request: Request, session_id: int):
    """Track of an app session for the admin map."""
    _, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    track = db.get_track(session_id, limit=300)
    return JSONResponse(track)


@app.get("/api/admin/emergencies")
async def admin_emergencies_api(request: Request, resolved: str = "false"):
    """List of emergencies filtered by resolution state."""
    _, redir = require_admin(request)
    if redir:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if resolved == "true":
        data = db.get_all_emergencies()
    else:
        data = db.get_open_emergencies()
    return JSONResponse(data)


@app.post("/admin/emergency/{eid}/resolve")
async def resolve_emergency(request: Request, eid: int, note: str = Form("")):
    user, redir = require_admin(request)
    if redir:
        return redir
    db.resolve_emergency(eid, resolved_by=user["id"], note=note)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/user/create")
async def admin_create_user(
    request: Request,
    username: str = Form(...), password: str = Form(...),
    nome: str = Form(...), cognome: str = Form(...),
    role: str = Form("user"),
):
    user, redir = require_admin(request)
    if redir:
        return redir
    db.create_user(username, hash_password(password), nome, cognome, role=role)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/user/{uid}/delete")
async def admin_delete_user(request: Request, uid: int):
    user, redir = require_admin(request)
    if redir:
        return redir
    if uid == user["id"]:
        raise HTTPException(400, "Non puoi eliminare te stesso")
    db.delete_user(uid)
    return RedirectResponse("/admin", status_code=303)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
