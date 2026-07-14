"""
Notifiche emergenza GrappaSafe.
Canali: Telegram (bot consortile) + email admin.
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


def _maps_url(lat, lon) -> str:
    return f"https://maps.google.com/?q={lat},{lon}"


def _format_emergency(emergency: dict) -> str:
    nome     = emergency.get("nome") or "—"
    cognome  = emergency.get("cognome") or "—"
    telefono = emergency.get("telefono") or "—"
    ec       = emergency.get("emergenza_contatto") or "—"
    et       = emergency.get("emergenza_telefono") or "—"
    gs       = emergency.get("gruppo_sanguigno") or "—"
    ns       = emergency.get("note_salute") or "—"
    attivita = emergency.get("attivita") or "—"
    trigger  = emergency.get("trigger") or "—"
    lat      = emergency.get("lat")
    lon      = emergency.get("lon")
    lingua   = emergency.get("lingua") or "it"

    loc = _maps_url(lat, lon) if lat and lon else "posizione non disponibile"

    return (
        f"🆘 EMERGENZA GRAPPASAFE\n\n"
        f"👤 {nome} {cognome}\n"
        f"📞 {telefono}\n"
        f"🏃 Attività: {attivita}\n"
        f"⚡ Trigger: {trigger}\n"
        f"📍 {loc}\n\n"
        f"🩸 Gruppo sanguigno: {gs}\n"
        f"🏥 Note salute: {ns}\n"
        f"🆘 Contatto emergenza: {ec} — {et}\n"
        f"🌐 Lingua: {lingua}"
    )


def _send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  [Telegram] token o chat_id non configurati — skip")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = httpx.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"  [Telegram] errore: {e}")
        return False


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


def notify_emergency(emergency_id: int):
    """
    Recupera l'emergenza dal DB e invia le notifiche su tutti i canali.
    Logga ogni invio in notification_log.
    Eseguito in thread separato per non bloccare la risposta API.
    """
    def _send():
        emergencies = _db.get_open_emergencies()
        emergency = next((e for e in emergencies if e["id"] == emergency_id), None)
        if not emergency:
            print(f"  [notify] emergenza {emergency_id} non trovata")
            return

        text = _format_emergency(emergency)
        subject = f"EMERGENZA GrappaSafe — {emergency.get('nome','')} {emergency.get('cognome','')}"

        ok_tg = _send_telegram(text)
        _db.log_notification(emergency_id, "TELEGRAM", TELEGRAM_CHAT_ID, ok_tg)

        ok_mail = _send_email(subject, text)
        _db.log_notification(emergency_id, "EMAIL", NOTIFY_EMAIL, ok_mail)

    threading.Thread(target=_send, daemon=True).start()
