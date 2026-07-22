<p align="center">
  <b>GrappaSafe</b><br>
  <i>Monitoraggio di sicurezza outdoor per la comunità del volo sul Monte Grappa.</i>
</p>

---

GrappaSafe segue piloti e sportivi outdoor in un raggio di 19 km attorno al Monte Grappa e
lancia un allarme quando qualcosa non va. Fonde due sorgenti di dati — un'app mobile
(GPS + accelerometro) e il feed APRS OGN/FLARM in tempo reale — così copre sia chi usa
l'app sia qualsiasi mezzo con transponder nell'area. Quando rileva un'emergenza avvisa gli
amministratori via Telegram ed email con posizione e dati medici della persona.

Il client mobile sta in un repo separato,
[grappasafe-mobile](https://github.com/that-ugly-cat/grappasafe-mobile) (React Native /
Expo); questo repo è il backend e i pannelli web con cui dialoga.

## Come funziona

Il cuore è diviso in due:

- **Macchina degli stati** — una descrizione puramente cinematica di cosa sta facendo
  un'entità (`GROUND / AIRBORNE / DESCENDING_FAST / LANDED` in volo,
  `MOVING / STATIONARY / IMPACT` a terra). Le transizioni sono confermate nel tempo, non a
  ogni tick, così un flusso GPS irregolare non genera falsi positivi.
- **Macchina delle emergenze** — decide quando una situazione diventa un'emergenza, a
  partire dagli stati sopra e da soglie modificabili a runtime dal pannello admin.

Trigger d'emergenza:

- **SOS manuale** — l'utente preme il pulsante nell'app. Scatta subito.
- **Paracadute d'emergenza** — una discesa verticale rapida (`DESCENDING_FAST`) seguita da
  atterraggio. Scatta subito.
- **Impatto** — un picco di accelerazione forte seguito dallo stare fermi. Passa da una
  finestra di conferma: l'utente ha qualche minuto per annullare dal telefono prima che
  l'allarme parta.
- **Immobilità prolungata** — fermo a lungo senza un impatto precedente. Stessa finestra di
  conferma; disattivata di default, perché una lunga sosta di solito è solo una sosta.

Trasversale a tutti:

- **L'immobilità è decisa per spostamento** su una finestra temporale, non per velocità GPS
  istantanea, così un pin ballerino non azzera il timer. I punti a bassa accuratezza sono
  ignorati, e un impatto viene dimenticato appena la persona si allontana dal punto.
- Uno **sweep in background auto-conferma un pending senza risposta** anche se il telefono
  smette di trasmettere (un device che si spegne dopo un impatto ottiene comunque l'allarme
  aperto lato server).
- Un operatore può **prendere in carico** un'emergenza (acknowledge) prima di risolverla;
  l'app lo segnala alla persona in difficoltà. La risoluzione chiude la sessione attiva del
  soggetto.

### App, OGN e entrambe

Le due sorgenti osservano cose diverse, quindi alzano allarmi diversi e si coprono a vicenda:

- **App (GPS + accelerometro).** L'insieme completo: SOS manuale, paracadute (confermato da
  un controllo di immobilità post-atterraggio), impatto (accelerometro, in volo e a terra) e
  immobilità prolungata. La velocità verticale è derivata dalla quota GPS, quindi è rumorosa
  — non c'è barometro.
- **OGN / FLARM (feed APRS).** Solo paracadute. Il FLARM dà una velocità verticale pulita,
  quindi il rilevamento della discesa rapida è affidabile anche per una riserva morbida — ma
  non c'è accelerometro (niente impatto) e i beacon di solito cessano a terra (nessun
  controllo di immobilità, quindi il paracadute scatta sulla transizione
  `DESCENDING_FAST → LANDED` stessa).
- **App + OGN (stesso pilota, device abbinato all'account).** Girano entrambe le reti e si
  completano: la vspeed pulita dell'OGN prende una riserva morbida che il GPS rumoroso
  dell'app potrebbe perdere, l'accelerometro dell'app prende un impatto duro che l'OGN non
  vede. Si tiene **una sola emergenza aperta per persona** — vince la sorgente che scatta
  prima e l'altra viene **deduplicata per identità risolta**. L'impatto non alimenta mai il
  gate OGN: le due reti restano indipendenti.

Un **cap di velocità orizzontale** configurabile sul controllo di discesa rapida evita che
un aeromobile in picchiata nell'area venga scambiato per una riserva.

Le soglie di quota sono calcolate rispetto al suolo (AGL) con le tile SRTM1 locali.

**Quando scatta un allarme**, identità, posizione e dati medici del soggetto (gruppo
sanguigno, note salute, data di nascita / età) partono sui canali configurati — un gruppo
Telegram ed email — e l'emergenza ha la sua scheda dedicata, condivisibile anche come link
pubblico a scadenza (24 h) per soccorritori non registrati. Un job in background registra
**chi altro era tracciato entro 300 m nel momento in cui è accaduto** (app o OGN), così i
potenziali testimoni non si perdono con la retention delle tracce. Ogni soglia citata sopra
è modificabile a runtime dalle pagine admin **Stati** (macchina degli stati) e **Regole**
(quale trigger è attivo, per attività, immediato o con conferma), attive entro 60 s senza
riavvio.

## Ruoli e permessi

Tre livelli, applicati dai guard `require_auth` / `require_viewer` / `require_admin`:

- **Utente** — manda i dati dall'app (GPS, accelerometro, SOS) e gestisce il proprio profilo
  e i propri device OGN/FLARM da web (`/me`, `/profile`) o app. **Non** accede alla dashboard
  né alle configurazioni.
- **Observer** — accesso in **sola lettura** alla dashboard live e al recap emergenze; apre i
  profili per contatti e dati medici; può **prendere in carico e risolvere** le emergenze
  dalla scheda (con nota obbligatoria). **Non** modifica utenti né configurazioni.
- **Admin** — accesso completo: dashboard, gestione emergenze, **utenti e ruoli**,
  **configurazioni** (Stati, Regole, Notifiche) e tracce/export.

Al login, admin e observer vanno alla dashboard, l'utente alla propria pagina.

## Funzionalità

- **Due sorgenti fuse**: app mobile e OGN/FLARM, ricondotte alla stessa identità tramite
  l'abbinamento device per utente, così un'emergenza OGN porta nome, telefono e dati medici.
- **Dashboard admin live**: mappa Leaflet con tutte le entità attive, colorate per attività
  (blu per l'aereo, arancione per il terrestre), filtri e pannello emergenze aperte. Un
  **popup a tutto schermo** avvisa di una nuova emergenza su qualsiasi pagina admin.
- **Client mobile**: auto-registrazione pubblica, modifica profilo, sessioni di attività con
  GPS in background, emergenze manuali e automatiche con messaggio configurabile, una
  **OpenTopoMap offline** del cerchio monitorato e un link di tracking live condivisibile.
- **Self-service utente**: da web o app, gli utenti gestiscono il profilo e abbinano i loro
  device OGN/FLARM.
- **Configurazione a runtime**: ogni soglia della macchina stati / emergenze è modificabile
  dalla pagina admin, attiva entro 60 s senza riavvio.
- **Mappa live condivisibile**: una URL pubblica `/map/{token}` che si aggiorna ogni 15 s.
- **Notifiche**: emergenza **aperta / presa in carico / risolta** inviata a un gruppo
  Telegram — elementi salienti più un link alla scheda — ed email all'apertura (a uno o più
  destinatari). Telegram e SMTP si configurano interamente dalla pagina admin **Notifiche** e
  sono salvati nel database; nessuna variabile d'ambiente per le notifiche.
- **Recupero password**: un link email firmato, usa-e-getta, valido 1 h (`/forgot` →
  `/reset`) via lo stesso SMTP configurato da admin; l'email dell'account è obbligatoria e
  unica.
- **Ricerca testimoni**: per ogni emergenza, i soggetti tracciati entro 300 m nel momento in
  cui è accaduta (app o OGN, con filtro verticale per i volatili) vengono trovati e salvati —
  a richiesta o automaticamente a +10 minuti — sopravvivendo alla retention delle tracce.
- **Localizzazione**: l'app mobile e le pagine web rivolte all'utente (`/me`, `/profile`,
  registrazione) sono tradotte in 8 lingue (it/en/de/fr/pl/nl/es/cs); i pannelli admin
  restano in italiano.
- **Registrazione web**: una pagina pubblica `/register` i cui campi un sito partner (es. il
  portale della fly card) può precompilare via query string — prende quello che arriva.
- **Export per taratura**: le tracce registrate (app + OGN) sono navigabili ed esportabili in
  Excel per tarare le soglie di rilevamento su dati reali.

## API per l'app

Sotto cookie di sessione, HTTPS: `POST /api/login`, `/api/register`, `GET`/`PUT /api/me`,
`GET /api/config` (area monitorata), `POST /api/session/{start,end,ok}` + `GET status`,
`POST /api/gps`, `POST /api/emergency` + `/emergency/confirm` + `GET /api/emergency/status`,
`GET /api/map/{token}` (traccia live pubblica) e le tile offline sotto `/map-tiles/`.

## Avvio rapido

```bash
git clone https://github.com/that-ugly-cat/grappasafe.git
cd grappasafe
pip install -r requirements.txt
cp .env.example .env         # imposta SECRET_KEY (le notifiche si configurano dal pannello admin)
python seed.py               # crea l'utente admin iniziale
./fetch_tiles.sh             # tile quota SRTM (~52 MB), per l'altitudine sul suolo
python fetch_map_tiles.py    # opzionale: tile OpenTopoMap per la mappa offline dell'app (~350 MB)
uvicorn app:app --reload
```

Apri http://localhost:8000/ e accedi come admin creato da `seed.py`. Lo schema completo e i
default di config/regole sono creati in modo idempotente all'avvio (`CREATE TABLE IF NOT
EXISTS` + seed `INSERT OR IGNORE`) — lo schema in `db.py` è l'unica fonte di verità, senza
migrazioni incrementali.

## Stack

FastAPI · SQLite · Jinja2 · Leaflet. Nessuno step di build. Il worker OGN e lo sweep dei
pending girano in thread in background nello stesso processo.

```
app.py              — route: auth, ingest GPS, sessioni, emergenze, admin, API app, mappa
db.py               — schema SQLite (senza migrazioni), seed e query
auth.py             — hashing password e guard di sessione/ruolo
seed.py             — crea l'utente admin iniziale
fetch_tiles.sh      — scarica le tile quota SRTM1
fetch_map_tiles.py  — pre-scarica le tile OpenTopoMap per la mappa offline dell'app
core/
  config.py         — configurazione da ambiente (area monitorata, segreti)
  state_machine.py  — macchina degli stati cinematica (volo + terra)
  emergency.py      — macchina delle emergenze, soglie, metadati di config
  ogn.py            — worker OGN/APRS: filtro area, SM di volo, paracadute all'atterraggio
  terrain.py        — lettore tile SRTM1 per la quota sul suolo (AGL)
  notify.py         — notifiche Telegram + email
webi18n.py          — traduzioni delle pagine web rivolte all'utente (/me, /profile)
templates/          — dashboard, emergenze (lista + scheda + link pubblico), utenti,
                      impostazioni stati/emergenze/notifiche, profilo, me, registrazione,
                      forgot/reset, tracce registrate, mappa pubblica, topbar admin condivisa
```

Vedi [DEPLOY.md](DEPLOY.md) per il deploy in produzione.
