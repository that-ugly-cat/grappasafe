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

def _smtp_conf():
    """SMTP config from the DB, falling back to the env values."""
    host = (_db.get_config_value("smtp_host", "") or SMTP_HOST or "").strip()
    try:
        port = int(_db.get_config_value("smtp_port", "") or SMTP_PORT or 587)
    except (ValueError, TypeError):
        port = SMTP_PORT or 587
    user = (_db.get_config_value("smtp_user", "") or SMTP_USER or "").strip()
    pw   = _db.get_config_value("smtp_pass", "") or SMTP_PASS or ""
    frm  = (_db.get_config_value("smtp_from", "") or user or NOTIFY_EMAIL or "").strip()
    tls  = (_db.get_config_value("smtp_tls", "true") or "true").lower() in ("true", "1", "yes")
    enabled = (_db.get_config_value("email_enabled", "true") or "true").lower() in ("true", "1", "yes")
    return host, port, user, pw, frm, tls, enabled


def _send_email(subject: str, body: str, to: str = None) -> bool:
    host, port, user, pw, frm, tls, enabled = _smtp_conf()
    to = to or NOTIFY_EMAIL
    if not enabled:
        print("  [Email] disabilitato — skip")
        return False
    if not host or not to:
        print("  [Email] SMTP o destinatario non configurati — skip")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"]    = frm or user
        msg["To"]      = to
        with smtplib.SMTP(host, port, timeout=15) as s:
            if tls:
                s.starttls()
            if user and pw:
                s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"  [Email] errore: {e}")
        return False


def send_email_test(to: str):
    """One-off test email for the admin panel. Returns (ok, detail)."""
    host, *_rest = _smtp_conf()
    if not host or not to:
        return False, "Host SMTP o destinatario mancanti."
    ok = _send_email("GrappaSafe — Email di prova",
                     "Se leggi questo, l'SMTP di GrappaSafe è configurato correttamente.", to)
    return ok, ("Email inviata." if ok else "Invio fallito — controlla host/porta/credenziali.")


# Password-reset email, localized. {link} is substituted at send time.
_RESET_MAIL = {
    "it": ("GrappaSafe — Reimposta la password",
           "Hai richiesto di reimpostare la password del tuo account GrappaSafe.\n\n"
           "Apri questo link per scegliere una nuova password (valido 1 ora):\n{link}\n\n"
           "Se non hai fatto questa richiesta, ignora questa email."),
    "en": ("GrappaSafe — Reset your password",
           "You asked to reset the password for your GrappaSafe account.\n\n"
           "Open this link to choose a new password (valid for 1 hour):\n{link}\n\n"
           "If you didn't request this, ignore this email."),
    "de": ("GrappaSafe — Passwort zurücksetzen",
           "Du hast angefordert, das Passwort deines GrappaSafe-Kontos zurückzusetzen.\n\n"
           "Öffne diesen Link, um ein neues Passwort zu wählen (1 Stunde gültig):\n{link}\n\n"
           "Wenn du das nicht angefordert hast, ignoriere diese E-Mail."),
    "fr": ("GrappaSafe — Réinitialiser le mot de passe",
           "Vous avez demandé à réinitialiser le mot de passe de votre compte GrappaSafe.\n\n"
           "Ouvrez ce lien pour choisir un nouveau mot de passe (valide 1 heure) :\n{link}\n\n"
           "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail."),
    "es": ("GrappaSafe — Restablecer la contraseña",
           "Has solicitado restablecer la contraseña de tu cuenta de GrappaSafe.\n\n"
           "Abre este enlace para elegir una nueva contraseña (válido 1 hora):\n{link}\n\n"
           "Si no lo has solicitado, ignora este correo."),
    "nl": ("GrappaSafe — Wachtwoord opnieuw instellen",
           "Je hebt gevraagd om het wachtwoord van je GrappaSafe-account opnieuw in te stellen.\n\n"
           "Open deze link om een nieuw wachtwoord te kiezen (1 uur geldig):\n{link}\n\n"
           "Als je dit niet hebt aangevraagd, negeer deze e-mail."),
    "pl": ("GrappaSafe — Zresetuj hasło",
           "Poprosiłeś o zresetowanie hasła do swojego konta GrappaSafe.\n\n"
           "Otwórz ten link, aby wybrać nowe hasło (ważny 1 godzinę):\n{link}\n\n"
           "Jeśli to nie Ty, zignoruj tę wiadomość."),
    "cs": ("GrappaSafe — Obnovit heslo",
           "Požádali jste o obnovení hesla ke svému účtu GrappaSafe.\n\n"
           "Otevřete tento odkaz a zvolte nové heslo (platí 1 hodinu):\n{link}\n\n"
           "Pokud jste o to nežádali, tento e-mail ignorujte."),
}


def send_password_reset(to: str, link: str, lang: str = "it"):
    """Send the reset link in the user's language, in a background thread."""
    subject, body = _RESET_MAIL.get(lang, _RESET_MAIL["it"])
    body = body.replace("{link}", link)

    def _send():
        _send_email(subject, body, to=to)

    threading.Thread(target=_send, daemon=True).start()


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
