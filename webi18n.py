"""
Minimal i18n for the user-facing web pages (base nav, /me, /profile).

Scope is deliberately narrow: only the pages a normal user sees, not the admin
backend. Language is resolved per request as: the `web_lang` cookie override
(set by the in-page switcher) → the logged-in user's saved `lingua` → the
browser Accept-Language header → Italian.

The login landing is intentionally NOT covered here yet (its copy is being
reworked before translation).
"""

LANGS = ["it", "en", "de", "fr", "pl", "nl", "es", "cs"]
LANG_NAMES = {
    "it": "Italiano", "en": "English", "de": "Deutsch", "fr": "Français",
    "pl": "Polski", "nl": "Nederlands", "es": "Español", "cs": "Čeština",
}


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
    "profile.dob": "Data di nascita",
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
    "profile.dob": "Date of birth",
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
    "profile.dob": "Geburtsdatum",
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

_fr = {
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "Mes appareils",
    "nav.profile": "Profil",
    "nav.logout": "Se déconnecter",

    "common.save": "Enregistrer",
    "common.cancel": "Annuler",
    "common.delete": "Supprimer",

    "act.PARAGLIDER": "Parapente",
    "act.HANGGLIDER": "Deltaplane",

    "me.greeting": "Bonjour {name} 👋",
    "me.introHtml": "Ici, vous gérez votre profil et vos <strong>données médicales</strong>, que les secours voient immédiatement en cas d'urgence.",
    "me.editProfileBtn": "Modifier le profil et les données médicales",
    "me.flarmSummary": "Appareils FLARM / OGN",
    "me.flarmSummaryOpt": "— facultatif, pour ceux qui volent avec un tracker",
    "me.flarmHelp": "Utile uniquement si vous volez en parapente, deltaplane ou planeur et avez un tracker FLARM/OGN à bord : l'associer permet au système de vous reconnaître même lorsque vous n'êtes suivi que par l'OGN. La plupart des utilisateurs peuvent ignorer cette section.",
    "me.myDevicesH3": "Mes appareils",
    "me.addDevice": "+ Ajouter un appareil",
    "me.deviceNameLabel": "Nom de l'appareil",
    "me.deviceNamePlaceholder": "ex. Voile rouge, Ozone Rush",
    "me.ognIdLabel": "ID OGN / FLARM",
    "me.ognIdPlaceholder": "ex. DDA123 (adresse hexadécimale du transpondeur)",
    "me.ognIdHelpHtml": "Vous le trouvez dans la configuration de votre tracker FLARM/OGN, ou sur <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Activité",
    "me.activityAuto": "Automatique (d'après le type OGN)",
    "me.activityHelp": "Si vous la définissez, elle l'emporte sur le type déduit de l'OGN : sur la carte, votre appareil affichera l'activité déclarée.",
    "me.noDevices": "Aucun appareil associé. Ajoutez votre FLARM/OGN pour être reconnu en vol.",
    "me.ognPrefix": "OGN/FLARM : ",
    "me.noOgnWarn": "⚠ aucun ID OGN — ne sera pas reconnu",
    "me.activityPrefix": "Activité : ",
    "me.edit": "Modifier",
    "me.nameRequired": "Le nom est obligatoire",
    "me.saveError": "Erreur lors de l'enregistrement",
    "me.confirmDelete": "Supprimer cet appareil ?",

    "profile.title": "Profil personnel",
    "profile.name": "Prénom",
    "profile.surname": "Nom",
    "profile.phone": "Téléphone",
    "profile.dob": "Date de naissance",
    "profile.emergencyContact": "Contact d'urgence",
    "profile.contactName": "Nom du contact",
    "profile.contactPhone": "Téléphone du contact",
    "profile.medical": "Données médicales (visibles par les secours)",
    "profile.bloodType": "Groupe sanguin",
    "profile.bloodTypePh": "ex. A+",
    "profile.healthNotes": "Notes de santé",
    "profile.healthNotesPh": "Allergies, médicaments, pathologies pertinentes",
    "profile.language": "Langue préférée",
    "profile.devicesNoteHtml": "Les appareils OGN/FLARM se gèrent sur la page <a href=\"/me\">Mes appareils</a>.",

    "lang.label": "Langue",
}

_es = {
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "Mis dispositivos",
    "nav.profile": "Perfil",
    "nav.logout": "Cerrar sesión",

    "common.save": "Guardar",
    "common.cancel": "Cancelar",
    "common.delete": "Eliminar",

    "act.PARAGLIDER": "Parapente",
    "act.HANGGLIDER": "Ala delta",

    "me.greeting": "Hola {name} 👋",
    "me.introHtml": "Aquí gestionas tu perfil y tus <strong>datos médicos</strong>, que los servicios de rescate ven de inmediato en una emergencia.",
    "me.editProfileBtn": "Editar perfil y datos médicos",
    "me.flarmSummary": "Dispositivos FLARM / OGN",
    "me.flarmSummaryOpt": "— opcional, para quien vuela con un tracker",
    "me.flarmHelp": "Solo es necesario si vuelas en parapente, ala delta o planeador y llevas un tracker FLARM/OGN a bordo: asociarlo permite que el sistema te reconozca incluso cuando solo te sigue el OGN. La mayoría de los usuarios puede ignorar esta sección.",
    "me.myDevicesH3": "Mis dispositivos",
    "me.addDevice": "+ Añadir dispositivo",
    "me.deviceNameLabel": "Nombre del dispositivo",
    "me.deviceNamePlaceholder": "ej. Vela roja, Ozone Rush",
    "me.ognIdLabel": "ID OGN / FLARM",
    "me.ognIdPlaceholder": "ej. DDA123 (dirección hexadecimal del transpondedor)",
    "me.ognIdHelpHtml": "Lo encuentras en la configuración de tu tracker FLARM/OGN, o en <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Actividad",
    "me.activityAuto": "Automática (según el tipo OGN)",
    "me.activityHelp": "Si la defines, prevalece sobre el tipo deducido del OGN: en el mapa tu aparato mostrará la actividad que declares.",
    "me.noDevices": "Ningún dispositivo asociado. Añade tu FLARM/OGN para ser reconocido en vuelo.",
    "me.ognPrefix": "OGN/FLARM: ",
    "me.noOgnWarn": "⚠ sin ID OGN — no será reconocido",
    "me.activityPrefix": "Actividad: ",
    "me.edit": "Editar",
    "me.nameRequired": "El nombre es obligatorio",
    "me.saveError": "Error al guardar",
    "me.confirmDelete": "¿Eliminar este dispositivo?",

    "profile.title": "Perfil personal",
    "profile.name": "Nombre",
    "profile.surname": "Apellidos",
    "profile.phone": "Teléfono",
    "profile.dob": "Fecha de nacimiento",
    "profile.emergencyContact": "Contacto de emergencia",
    "profile.contactName": "Nombre del contacto",
    "profile.contactPhone": "Teléfono del contacto",
    "profile.medical": "Datos médicos (visibles para los servicios de rescate)",
    "profile.bloodType": "Grupo sanguíneo",
    "profile.bloodTypePh": "ej. A+",
    "profile.healthNotes": "Notas de salud",
    "profile.healthNotesPh": "Alergias, medicación, patologías relevantes",
    "profile.language": "Idioma preferido",
    "profile.devicesNoteHtml": "Los dispositivos OGN/FLARM se gestionan en la página <a href=\"/me\">Mis dispositivos</a>.",

    "lang.label": "Idioma",
}

_nl = {
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "Mijn apparaten",
    "nav.profile": "Profiel",
    "nav.logout": "Afmelden",

    "common.save": "Opslaan",
    "common.cancel": "Annuleren",
    "common.delete": "Verwijderen",

    "act.PARAGLIDER": "Paragliden",
    "act.HANGGLIDER": "Deltavliegen",

    "me.greeting": "Hallo {name} 👋",
    "me.introHtml": "Hier beheer je je profiel en je <strong>medische gegevens</strong>, die hulpdiensten bij een noodgeval meteen zien.",
    "me.editProfileBtn": "Profiel en medische gegevens bewerken",
    "me.flarmSummary": "FLARM / OGN-apparaten",
    "me.flarmSummaryOpt": "— optioneel, voor wie met een tracker vliegt",
    "me.flarmHelp": "Alleen nodig als je paraglidet, deltavliegt of zweefvliegt en een FLARM/OGN-tracker aan boord hebt: door deze te koppelen herkent het systeem je ook wanneer je alleen via OGN wordt gevolgd. De meeste gebruikers kunnen dit gedeelte negeren.",
    "me.myDevicesH3": "Mijn apparaten",
    "me.addDevice": "+ Apparaat toevoegen",
    "me.deviceNameLabel": "Apparaatnaam",
    "me.deviceNamePlaceholder": "bijv. Rood scherm, Ozone Rush",
    "me.ognIdLabel": "OGN / FLARM-ID",
    "me.ognIdPlaceholder": "bijv. DDA123 (hex-adres van de transponder)",
    "me.ognIdHelpHtml": "Je vindt het in de configuratie van je FLARM/OGN-tracker, of op <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Activiteit",
    "me.activityAuto": "Automatisch (op basis van OGN-type)",
    "me.activityHelp": "Als je deze instelt, gaat ze voor op het uit OGN afgeleide type: op de kaart verschijnt je toestel met de opgegeven activiteit.",
    "me.noDevices": "Geen apparaat gekoppeld. Voeg je FLARM/OGN toe om in de vlucht herkend te worden.",
    "me.ognPrefix": "OGN/FLARM: ",
    "me.noOgnWarn": "⚠ geen OGN-ID — wordt niet herkend",
    "me.activityPrefix": "Activiteit: ",
    "me.edit": "Bewerken",
    "me.nameRequired": "De naam is verplicht",
    "me.saveError": "Fout bij het opslaan",
    "me.confirmDelete": "Dit apparaat verwijderen?",

    "profile.title": "Persoonlijk profiel",
    "profile.name": "Voornaam",
    "profile.surname": "Achternaam",
    "profile.phone": "Telefoon",
    "profile.dob": "Geboortedatum",
    "profile.emergencyContact": "Noodcontact",
    "profile.contactName": "Naam contact",
    "profile.contactPhone": "Telefoon contact",
    "profile.medical": "Medische gegevens (zichtbaar voor hulpdiensten)",
    "profile.bloodType": "Bloedgroep",
    "profile.bloodTypePh": "bijv. A+",
    "profile.healthNotes": "Gezondheidsnotities",
    "profile.healthNotesPh": "Allergieën, medicatie, relevante aandoeningen",
    "profile.language": "Voorkeurstaal",
    "profile.devicesNoteHtml": "OGN/FLARM-apparaten beheer je op de pagina <a href=\"/me\">Mijn apparaten</a>.",

    "lang.label": "Taal",
}

_pl = {
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "Moje urządzenia",
    "nav.profile": "Profil",
    "nav.logout": "Wyloguj się",

    "common.save": "Zapisz",
    "common.cancel": "Anuluj",
    "common.delete": "Usuń",

    "act.PARAGLIDER": "Paralotniarstwo",
    "act.HANGGLIDER": "Lotniarstwo",

    "me.greeting": "Cześć {name} 👋",
    "me.introHtml": "Tutaj zarządzasz swoim profilem i <strong>danymi medycznymi</strong>, które ratownicy widzą natychmiast w razie nagłego wypadku.",
    "me.editProfileBtn": "Edytuj profil i dane medyczne",
    "me.flarmSummary": "Urządzenia FLARM / OGN",
    "me.flarmSummaryOpt": "— opcjonalne, dla latających z trackerem",
    "me.flarmHelp": "Potrzebne tylko, jeśli latasz na paralotni, lotni lub szybowcu i masz na pokładzie tracker FLARM/OGN: powiązanie go pozwala systemowi rozpoznać Cię nawet wtedy, gdy jesteś śledzony tylko przez OGN. Większość użytkowników może zignorować tę sekcję.",
    "me.myDevicesH3": "Moje urządzenia",
    "me.addDevice": "+ Dodaj urządzenie",
    "me.deviceNameLabel": "Nazwa urządzenia",
    "me.deviceNamePlaceholder": "np. Czerwone skrzydło, Ozone Rush",
    "me.ognIdLabel": "ID OGN / FLARM",
    "me.ognIdPlaceholder": "np. DDA123 (adres szesnastkowy transpondera)",
    "me.ognIdHelpHtml": "Znajdziesz go w konfiguracji swojego trackera FLARM/OGN lub na <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Aktywność",
    "me.activityAuto": "Automatycznie (z typu OGN)",
    "me.activityHelp": "Jeśli ją ustawisz, ma pierwszeństwo przed typem wywnioskowanym z OGN: na mapie Twój statek pojawi się z zadeklarowaną aktywnością.",
    "me.noDevices": "Brak powiązanego urządzenia. Dodaj swój FLARM/OGN, aby być rozpoznawanym w locie.",
    "me.ognPrefix": "OGN/FLARM: ",
    "me.noOgnWarn": "⚠ brak ID OGN — nie zostanie rozpoznane",
    "me.activityPrefix": "Aktywność: ",
    "me.edit": "Edytuj",
    "me.nameRequired": "Nazwa jest wymagana",
    "me.saveError": "Błąd podczas zapisywania",
    "me.confirmDelete": "Usunąć to urządzenie?",

    "profile.title": "Profil osobisty",
    "profile.name": "Imię",
    "profile.surname": "Nazwisko",
    "profile.phone": "Telefon",
    "profile.dob": "Data urodzenia",
    "profile.emergencyContact": "Kontakt awaryjny",
    "profile.contactName": "Imię kontaktu",
    "profile.contactPhone": "Telefon kontaktu",
    "profile.medical": "Dane medyczne (widoczne dla ratowników)",
    "profile.bloodType": "Grupa krwi",
    "profile.bloodTypePh": "np. A+",
    "profile.healthNotes": "Uwagi zdrowotne",
    "profile.healthNotesPh": "Alergie, leki, istotne schorzenia",
    "profile.language": "Preferowany język",
    "profile.devicesNoteHtml": "Urządzeniami OGN/FLARM zarządzasz na stronie <a href=\"/me\">Moje urządzenia</a>.",

    "lang.label": "Język",
}

_cs = {
    "nav.dashboard": "Dashboard",
    "nav.myDevices": "Moje zařízení",
    "nav.profile": "Profil",
    "nav.logout": "Odhlásit se",

    "common.save": "Uložit",
    "common.cancel": "Zrušit",
    "common.delete": "Smazat",

    "act.PARAGLIDER": "Paragliding",
    "act.HANGGLIDER": "Závěsné létání",

    "me.greeting": "Ahoj {name} 👋",
    "me.introHtml": "Zde spravujete svůj profil a své <strong>zdravotní údaje</strong>, které záchranáři v případě nouze okamžitě vidí.",
    "me.editProfileBtn": "Upravit profil a zdravotní údaje",
    "me.flarmSummary": "Zařízení FLARM / OGN",
    "me.flarmSummaryOpt": "— nepovinné, pro ty, kdo létají s trackerem",
    "me.flarmHelp": "Potřebné jen pokud létáte na padákovém kluzáku, rogalu nebo větroni a máte na palubě tracker FLARM/OGN: jeho propojení umožní systému rozpoznat vás i tehdy, když jste sledováni pouze přes OGN. Většina uživatelů může tuto sekci ignorovat.",
    "me.myDevicesH3": "Moje zařízení",
    "me.addDevice": "+ Přidat zařízení",
    "me.deviceNameLabel": "Název zařízení",
    "me.deviceNamePlaceholder": "např. Červené křídlo, Ozone Rush",
    "me.ognIdLabel": "ID OGN / FLARM",
    "me.ognIdPlaceholder": "např. DDA123 (hexadecimální adresa transpondéru)",
    "me.ognIdHelpHtml": "Najdete ho v konfiguraci svého trackeru FLARM/OGN nebo na <a href=\"https://www.glidernet.org/\" target=\"_blank\" rel=\"noopener\">glidernet.org</a> / <a href=\"https://ogn.flarm.com/\" target=\"_blank\" rel=\"noopener\">OGN device database</a>.",
    "me.activityLabel": "Aktivita",
    "me.activityAuto": "Automaticky (z typu OGN)",
    "me.activityHelp": "Pokud ji nastavíte, má přednost před typem odvozeným z OGN: na mapě se vaše zařízení zobrazí s deklarovanou aktivitou.",
    "me.noDevices": "Žádné propojené zařízení. Přidejte svůj FLARM/OGN, abyste byli rozpoznáni za letu.",
    "me.ognPrefix": "OGN/FLARM: ",
    "me.noOgnWarn": "⚠ žádné OGN ID — nebude rozpoznáno",
    "me.activityPrefix": "Aktivita: ",
    "me.edit": "Upravit",
    "me.nameRequired": "Název je povinný",
    "me.saveError": "Chyba při ukládání",
    "me.confirmDelete": "Smazat toto zařízení?",

    "profile.title": "Osobní profil",
    "profile.name": "Jméno",
    "profile.surname": "Příjmení",
    "profile.phone": "Telefon",
    "profile.dob": "Datum narození",
    "profile.emergencyContact": "Nouzový kontakt",
    "profile.contactName": "Jméno kontaktu",
    "profile.contactPhone": "Telefon kontaktu",
    "profile.medical": "Zdravotní údaje (viditelné pro záchranáře)",
    "profile.bloodType": "Krevní skupina",
    "profile.bloodTypePh": "např. A+",
    "profile.healthNotes": "Zdravotní poznámky",
    "profile.healthNotesPh": "Alergie, léky, relevantní onemocnění",
    "profile.language": "Preferovaný jazyk",
    "profile.devicesNoteHtml": "Zařízení OGN/FLARM spravujete na stránce <a href=\"/me\">Moje zařízení</a>.",

    "lang.label": "Jazyk",
}

WEB_STRINGS = {
    "it": _it, "en": _en, "de": _de, "fr": _fr,
    "pl": _pl, "nl": _nl, "es": _es, "cs": _cs,
}
