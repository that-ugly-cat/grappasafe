"""
Notifiche emergenza GrappaSafe.
Canali: Telegram (gruppo consortile) + email admin.

Telegram è configurabile a runtime dal pannello admin (token, chat id, on/off).
Gli eventi notificati sul gruppo sono tre: emergenza aperta, presa in carico,
risolta. Ogni messaggio porta gli elementi salienti e il link alla scheda.
"""

import smtplib
import threading
from email.mime.text import MIMEText

import httpx

import db as _db
from core.config import (
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_EMAIL,
)

_TRIG = {
    "MANUAL":        "SOS manuale",
    "AUTO_CHUTE":    "Paracadute di emergenza",
    "AUTO_IMPACT":   "Impatto + immobile",
    "AUTO_IMMOBILE": "Immobilità prolungata",
}
_ACT = {
    "PARAGLIDER": "Parapendio", "HANGGLIDER": "Deltaplano",
    "CYCLIST": "Ciclismo", "CLIMBER": "Arrampicata", "HIKER": "Escursionismo",
    "RUNNER": "Trail running", "OTHER_ON_GROUND": "Altro",
}


def _maps_url(lat, lon) -> str:
    return f"https://maps.google.com/?q={lat},{lon}"


def _who(em) -> str:
    name = f"{em.get('nome') or ''} {em.get('cognome') or ''}".strip()
    return name or em.get("ogn_id") or "Sconosciuto"


def _full_name(nome, cognome) -> str:
    return f"{nome or ''} {cognome or ''}".strip() or "—"


# ── Telegram ──────────────────────────────────────────────────────────────────

def _tg_conf():
    """Telegram config from the DB, falling back to the env values. Returns
    (token, chat_id, enabled)."""
    token   = (_db.get_config_value("telegram_bot_token", "") or TELEGRAM_TOKEN or "").strip()
    chat    = (_db.get_config_value("telegram_chat_id", "") or TELEGRAM_CHAT_ID or "").strip()
    enabled = (_db.get_config_value("telegram_enabled", "true") or "true").lower() in ("true", "1", "yes")
    return token, chat, enabled


def _send_telegram(text: str):
    """Send a Telegram message. Returns (ok, chat_id_used)."""
    token, chat, enabled = _tg_conf()
    if not enabled:
        print("  [Telegram] disabilitato — skip")
        return False, chat
    if not token or not chat:
        print("  [Telegram] token o chat_id non configurati — skip")
        return False, chat
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = httpx.post(url, json={
            "chat_id": chat, "text": text,
            "disable_web_page_preview": True,
        }, timeout=10)
        r.raise_for_status()
        return True, chat
    except Exception as e:
        print(f"  [Telegram] errore: {e}")
        return False, chat


def send_telegram_test(text: str):
    """Send a one-off test message. Returns (ok, detail) for the admin panel."""
    token, chat, enabled = _tg_conf()
    if not token or not chat:
        return False, "Token o chat id mancanti."
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = httpx.post(url, json={"chat_id": chat, "text": text}, timeout=10)
        if r.status_code == 200:
            return True, "Messaggio inviato."
        return False, f"Telegram ha risposto {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


# ── Email ─────────────────────────────────────────────────────────────────────

def _send_email(subject: str, body: str) -> bool:
    if not SMTP_HOST or not NOTIFY_EMAIL:
        print("  [Email] SMTP non configurato — skip")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = NOTIFY_EMAIL
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"  [Email] errore: {e}")
        return False


# ── Link + message builders ───────────────────────────────────────────────────

def _emergency_link(eid) -> str:
    base = (_db.get_config_value("public_base_url", "") or "").strip().rstrip("/")
    return f"{base}/admin/emergency/{eid}" if base else ""


def _link_line(eid):
    link = _emergency_link(eid)
    return ["", f"🔗 Scheda emergenza: {link}"] if link else \
           ["", "🔗 Scheda emergenza: (configura public_base_url)"]


def _msg_opened(em) -> str:
    lat, lon = em.get("lat"), em.get("lon")
    loc = _maps_url(lat, lon) if lat and lon else "posizione non disponibile"
    lines = [
        "🆘 EMERGENZA APERTA — GrappaSafe", "",
        f"👤 {_who(em)}",
        f"📞 {em.get('telefono') or '—'}",
        f"🏃 Attività: {_ACT.get(em.get('attivita'), em.get('attivita') or '—')}",
        f"⚡ {_TRIG.get(em.get('trigger'), em.get('trigger') or '—')}",
        f"📍 {loc}", "",
        f"🩸 Gruppo sanguigno: {em.get('gruppo_sanguigno') or '—'}",
        f"🏥 Note salute: {em.get('note_salute') or '—'}",
        f"🆘 Contatto emergenza: {em.get('emergenza_contatto') or '—'} — {em.get('emergenza_telefono') or '—'}",
        f"🌐 Lingua: {em.get('lingua') or 'it'}",
    ]
    return "\n".join(lines + _link_line(em["id"]))


def _msg_ack(em) -> str:
    lat, lon = em.get("lat"), em.get("lon")
    loc = _maps_url(lat, lon) if lat and lon else "posizione non disponibile"
    lines = [
        "✅ EMERGENZA PRESA IN CARICO — GrappaSafe", "",
        f"👤 {_who(em)}",
        f"🧭 Gestita da: {_full_name(em.get('acker_nome'), em.get('acker_cognome'))}",
        f"📍 {loc}",
    ]
    return "\n".join(lines + _link_line(em["id"]))


def _msg_resolved(em) -> str:
    lines = [
        "🟢 EMERGENZA RISOLTA — GrappaSafe", "",
        f"👤 {_who(em)}",
        f"✔️ Risolta da: {_full_name(em.get('resolver_nome'), em.get('resolver_cognome'))}",
        f"📝 Nota: {em.get('note') or '—'}",
    ]
    return "\n".join(lines + _link_line(em["id"]))


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _dispatch(emergency_id: int, event: str):
    """Build and send the notification for one emergency event. Runs in a
    background thread so it never blocks the request. event is one of
    'opened' | 'acknowledged' | 'resolved'."""
    def _send():
        em = _db.get_emergency(emergency_id)
        if not em:
            print(f"  [notify] emergenza {emergency_id} non trovata")
            return
        if event == "opened":
            text = _msg_opened(em)
        elif event == "acknowledged":
            text = _msg_ack(em)
        else:
            text = _msg_resolved(em)

        ok_tg, chat = _send_telegram(text)
        _db.log_notification(emergency_id, f"TELEGRAM_{event.upper()}", chat or "-", ok_tg)

        # Email only on the opening event, as before.
        if event == "opened":
            subject = f"EMERGENZA GrappaSafe — {em.get('nome','')} {em.get('cognome','')}".strip()
            ok_mail = _send_email(subject, text)
            _db.log_notification(emergency_id, "EMAIL", NOTIFY_EMAIL, ok_mail)

    threading.Thread(target=_send, daemon=True).start()


def notify_emergency(emergency_id: int):
    """Emergency opened."""
    _dispatch(emergency_id, "opened")


def notify_emergency_ack(emergency_id: int):
    """Emergency taken in charge by an operator."""
    _dispatch(emergency_id, "acknowledged")


def notify_emergency_resolved(emergency_id: int):
    """Emergency resolved."""
    _dispatch(emergency_id, "resolved")
