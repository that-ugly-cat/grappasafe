"""
Minimal i18n for the user-facing web pages (base nav, /me, /profile).

Scope is deliberately narrow: only the pages a normal user sees, not the admin
backend. Language is resolved per request as: the `web_lang` cookie override
(set by the in-page switcher) → the logged-in user's saved `lingua` → the
browser Accept-Language header → Italian.

The login landing is intentionally NOT covered here yet (its copy is being
reworked before translation).
"""

LANGS = ["it", "en", "de"]
LANG_NAMES = {"it": "Italiano", "en": "English", "de": "Deutsch"}


def resolve_lang(request, user=None) -> str:
    cookie = request.cookies.get("web_lang")
    if cookie in LANGS:
        return cookie
    if user and user.get("lingua") in LANGS:
        return user["lingua"]
    accept = request.headers.get("accept-language", "")
    for part in accept.split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LANGS:
            return code
    return "it"


def translator(lang: str):
    table = WEB_STRINGS.get(lang, WEB_STRINGS["it"])
    fallback = WEB_STRINGS["it"]

    def t(key: str, **vars) -> str:
        s = table.get(key) or fallback.get(key) or key
        if vars:
            for k, v in vars.items():
                s = s.replace("{" + k + "}", str(v))
        return s

    return t


_it = {
    # nav (base.html)
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "I miei device",
    "nav.profile": "Profilo",
    "nav.logout": "Esci",

    # common
    "common.save": "Salva",
    "common.cancel": "Annulla",
    "common.delete": "Elimina",

    # activities (used in me.html JS)
    "act.PARAGLIDER": "Parapendio",
    "act.HANGGLIDER": "Deltaplano",

    # me.html
    "me.greeting": "Ciao {name} 👋",
    "me.introHtml": "Qui gestisci il tuo profilo e i tuoi <strong>dati medici</strong>, che i soccorritori vedono subito in caso di emergenza.",
    "me.editProfileBtn": "Modifica profilo e dati medici",
    "me.flarmSummary": "Dispositivi FLARM / OGN",
    "me.flarmSummaryOpt": "— opzionale, per chi vola con un tracker",
    "me.flarmHelp": "Serve solo se voli con parapendio, deltaplano o aliante e hai un tracker FLARM/OGN a bordo: abbinarlo permette al sistema di riconoscerti quando sei tracciato solo dall'OGN. La maggior parte degli utenti può ignorare questa sezione.",
    "me.myDevicesH3": "I miei device",
    "me.addDevice": "+ Aggiungi device",
    "me.deviceNameLabel": "Nome del device",
    "me.deviceNamePlaceholder": "es. Vela rossa, Ozone Rush",
    "me.ognIdLabel": "OGN / FLARM ID",
    "me.ognIdPlaceholder": "es. DDA123 (indirizzo esadecimale del transponder)",
    "me.ognIdHelpHtml": "Lo trovi nella configurazione del tuo FLARM/OGN tracker, o su <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Attività",
    "me.activityAuto": "Automatica (dal tipo OGN)",
    "me.activityHelp": "Se la imposti, vince sul tipo dedotto dall'OGN: sulla mappa il tuo mezzo apparirà con l'attività che dichiari.",
    "me.noDevices": "Nessun device abbinato. Aggiungi il tuo FLARM/OGN per essere riconosciuto in volo.",
    "me.ognPrefix": "OGN/FLARM: ",
    "me.noOgnWarn": "⚠ nessun ID OGN — non verrà riconosciuto",
    "me.activityPrefix": "Attività: ",
    "me.edit": "Modifica",
    "me.nameRequired": "Il nome è obbligatorio",
    "me.saveError": "Errore nel salvataggio",
    "me.confirmDelete": "Eliminare questo device?",

    # profile.html
    "profile.title": "Profilo personale",
    "profile.name": "Nome",
    "profile.surname": "Cognome",
    "profile.phone": "Telefono",
    "profile.emergencyContact": "Contatto emergenza",
    "profile.contactName": "Nome contatto",
    "profile.contactPhone": "Telefono contatto",
    "profile.medical": "Dati medici (visibili ai soccorritori)",
    "profile.bloodType": "Gruppo sanguigno",
    "profile.bloodTypePh": "es. A+",
    "profile.healthNotes": "Note salute",
    "profile.healthNotesPh": "Allergie, farmaci, patologie rilevanti",
    "profile.language": "Lingua preferita",
    "profile.devicesNoteHtml": "I dispositivi OGN/FLARM si gestiscono nella pagina <a href=\"/me\">I miei device</a>.",

    # language switcher
    "lang.label": "Lingua",
}

_en = {
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "My devices",
    "nav.profile": "Profile",
    "nav.logout": "Log out",

    "common.save": "Save",
    "common.cancel": "Cancel",
    "common.delete": "Delete",

    "act.PARAGLIDER": "Paragliding",
    "act.HANGGLIDER": "Hang gliding",

    "me.greeting": "Hi {name} 👋",
    "me.introHtml": "Here you manage your profile and your <strong>medical data</strong>, which rescuers see immediately in an emergency.",
    "me.editProfileBtn": "Edit profile and medical data",
    "me.flarmSummary": "FLARM / OGN devices",
    "me.flarmSummaryOpt": "— optional, for those who fly with a tracker",
    "me.flarmHelp": "Only needed if you fly a paraglider, hang glider or sailplane and carry a FLARM/OGN tracker: linking it lets the system recognise you even when you are tracked by OGN alone. Most users can ignore this section.",
    "me.myDevicesH3": "My devices",
    "me.addDevice": "+ Add device",
    "me.deviceNameLabel": "Device name",
    "me.deviceNamePlaceholder": "e.g. Red wing, Ozone Rush",
    "me.ognIdLabel": "OGN / FLARM ID",
    "me.ognIdPlaceholder": "e.g. DDA123 (hex address of the transponder)",
    "me.ognIdHelpHtml": "You'll find it in your FLARM/OGN tracker's configuration, or on <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Activity",
    "me.activityAuto": "Automatic (from OGN type)",
    "me.activityHelp": "If you set it, it overrides the type inferred from OGN: on the map your aircraft will show the activity you declare.",
    "me.noDevices": "No device linked. Add your FLARM/OGN to be recognised in flight.",
    "me.ognPrefix": "OGN/FLARM: ",
    "me.noOgnWarn": "⚠ no OGN ID — it won't be recognised",
    "me.activityPrefix": "Activity: ",
    "me.edit": "Edit",
    "me.nameRequired": "The name is required",
    "me.saveError": "Error while saving",
    "me.confirmDelete": "Delete this device?",

    "profile.title": "Personal profile",
    "profile.name": "First name",
    "profile.surname": "Last name",
    "profile.phone": "Phone",
    "profile.emergencyContact": "Emergency contact",
    "profile.contactName": "Contact name",
    "profile.contactPhone": "Contact phone",
    "profile.medical": "Medical data (visible to rescuers)",
    "profile.bloodType": "Blood type",
    "profile.bloodTypePh": "e.g. A+",
    "profile.healthNotes": "Health notes",
    "profile.healthNotesPh": "Allergies, medication, relevant conditions",
    "profile.language": "Preferred language",
    "profile.devicesNoteHtml": "OGN/FLARM devices are managed on the <a href=\"/me\">My devices</a> page.",

    "lang.label": "Language",
}

_de = {
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "Meine Geräte",
    "nav.profile": "Profil",
    "nav.logout": "Abmelden",

    "common.save": "Speichern",
    "common.cancel": "Abbrechen",
    "common.delete": "Löschen",

    "act.PARAGLIDER": "Gleitschirm",
    "act.HANGGLIDER": "Drachen",

    "me.greeting": "Hallo {name} 👋",
    "me.introHtml": "Hier verwaltest du dein Profil und deine <strong>medizinischen Daten</strong>, die die Rettungskräfte im Notfall sofort sehen.",
    "me.editProfileBtn": "Profil und medizinische Daten bearbeiten",
    "me.flarmSummary": "FLARM / OGN-Geräte",
    "me.flarmSummaryOpt": "— optional, für alle mit einem Tracker",
    "me.flarmHelp": "Nur nötig, wenn du mit Gleitschirm, Drachen oder Segelflugzeug fliegst und einen FLARM/OGN-Tracker an Bord hast: Durch die Verknüpfung erkennt dich das System auch, wenn du nur über OGN verfolgt wirst. Die meisten Nutzer können diesen Abschnitt ignorieren.",
    "me.myDevicesH3": "Meine Geräte",
    "me.addDevice": "+ Gerät hinzufügen",
    "me.deviceNameLabel": "Gerätename",
    "me.deviceNamePlaceholder": "z. B. Roter Schirm, Ozone Rush",
    "me.ognIdLabel": "OGN / FLARM-ID",
    "me.ognIdPlaceholder": "z. B. DDA123 (Hex-Adresse des Transponders)",
    "me.ognIdHelpHtml": "Du findest sie in der Konfiguration deines FLARM/OGN-Trackers oder auf <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Aktivität",
    "me.activityAuto": "Automatisch (aus OGN-Typ)",
    "me.activityHelp": "Wenn du sie festlegst, hat sie Vorrang vor dem aus OGN abgeleiteten Typ: Auf der Karte erscheint dein Gerät mit der angegebenen Aktivität.",
    "me.noDevices": "Kein Gerät verknüpft. Füge dein FLARM/OGN hinzu, um im Flug erkannt zu werden.",
    "me.ognPrefix": "OGN/FLARM: ",
    "me.noOgnWarn": "⚠ keine OGN-ID — wird nicht erkannt",
    "me.activityPrefix": "Aktivität: ",
    "me.edit": "Bearbeiten",
    "me.nameRequired": "Der Name ist erforderlich",
    "me.saveError": "Fehler beim Speichern",
    "me.confirmDelete": "Dieses Gerät löschen?",

    "profile.title": "Persönliches Profil",
    "profile.name": "Vorname",
    "profile.surname": "Nachname",
    "profile.phone": "Telefon",
    "profile.emergencyContact": "Notfallkontakt",
    "profile.contactName": "Name des Kontakts",
    "profile.contactPhone": "Telefon des Kontakts",
    "profile.medical": "Medizinische Daten (für Rettungskräfte sichtbar)",
    "profile.bloodType": "Blutgruppe",
    "profile.bloodTypePh": "z. B. A+",
    "profile.healthNotes": "Gesundheitshinweise",
    "profile.healthNotesPh": "Allergien, Medikamente, relevante Vorerkrankungen",
    "profile.language": "Bevorzugte Sprache",
    "profile.devicesNoteHtml": "OGN/FLARM-Geräte werden auf der Seite <a href=\"/me\">Meine Geräte</a> verwaltet.",

    "lang.label": "Sprache",
}

WEB_STRINGS = {"it": _it, "en": _en, "de": _de}
