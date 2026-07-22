# Deploy di GrappaSafe

GrappaSafe è una singola app FastAPI con un unico file SQLite. Il worker OGN gira in un
thread in background, quindi non ci sono servizi esterni da avviare oltre all'app stessa.

## 1. Configurazione (variabili d'ambiente)

| Variabile | Obbligatoria | Default | Scopo |
|---|---|---|---|
| `SECRET_KEY` | **sì, in produzione** | `change-me-in-production` | firma il cookie di sessione — imposta un valore lungo e casuale |
| `GRAPPASAFE_DB` | no | `grappasafe.db` | percorso del file SQLite (`/data/grappasafe.db` in Docker) |
| `AREA_LAT` / `AREA_LON` / `AREA_RADIUS_KM` | no | Monte Grappa, 19 km | area monitorata |
| `APRS_USER` | no | `GSAFE1` | callsign di ricezione OGN/APRS (il passcode ne deriva; tienilo corto e unico) |
| `ADMIN_USER` / `ADMIN_PASS` / `ADMIN_NOME` / `ADMIN_COGNOME` | no | `admin` / `changeme` | admin iniziale, creato da `seed.py` |

Le notifiche Telegram ed email **non** sono variabili d'ambiente — si configurano dalla
pagina admin **Notifiche** e sono salvate nel database (vedi §6).

Genera un secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 2. Tile

**Quota (SRTM1).** Le soglie di altitudine sono calcolate rispetto al suolo. Scarica una
volta (l'app funziona anche senza, ripiegando sull'AMSL con accuratezza ridotta):

```bash
./fetch_tiles.sh          # N45E011.hgt + N45E012.hgt (~52 MB) in tiles/
```

Con Docker vengono incluse nell'immagine in fase di build, quindi eseguilo prima di buildare.

**Mappa offline (OpenTopoMap).** Opzionale, solo per la mappa offline dell'app mobile.
Scarica una volta le tile raster del cerchio monitorato (zoom 9–16, ~350 MB), servite sotto
`/map-tiles/`:

```bash
python fetch_map_tiles.py
```

A differenza delle tile SRTM queste **non** sono incluse nell'immagine — vivono in un volume
host (`./map_tiles`, vedi `docker-compose.yml`). Con Docker, scaricale in quel volume dal
container in esecuzione, così non serve un rebuild:

```bash
docker compose exec api python fetch_map_tiles.py
```

## 3. Locale / bare-metal

```bash
pip install -r requirements.txt
cp .env.example .env         # imposta SECRET_KEY (le notifiche si configurano dal pannello admin)
python seed.py               # solo al primo avvio
./fetch_tiles.sh
uvicorn app:app --host 0.0.0.0 --port 8000
```

## 4. Docker

```bash
cp .env.example .env         # imposta SECRET_KEY (le notifiche si configurano dal pannello admin)
./fetch_tiles.sh             # le tile vengono copiate nell'immagine
docker compose up -d --build
```

`docker-compose.yml` espone l'app su `127.0.0.1:8010` e monta `./data` per il file SQLite e
`./map_tiles` per le tile della mappa offline. Crea l'utente admin una volta che il container
è su:

```bash
docker compose exec api python seed.py
```

## 5. Reverse proxy (HTTPS)

Dietro Caddy su `grappasafe.borant.eu`:

```
grappasafe.borant.eu {
    reverse_proxy localhost:8010
}
```

Ricarica: `sudo systemctl reload caddy`. I certificati HTTPS sono emessi automaticamente.

## 6. Notifiche

Gli eventi d'emergenza — **aperta, presa in carico, risolta** — sono inviati a un gruppo
Telegram, ognuno con gli elementi salienti e un link alla scheda emergenza; l'apertura parte
anche via email. Configura Telegram dalla pagina admin **Notifiche** (attivo entro 60 s,
senza riavvio):

- **Token del bot** — da `@BotFather`.
- **ID del gruppo/chat** — aggiungi il bot al gruppo, scrivi un messaggio, poi leggi `chat.id`
  da `https://api.telegram.org/bot<TOKEN>/getUpdates` (gli id dei gruppi iniziano con `-100`).
- **URL pubblico del pannello** — es. `https://grappasafe.borant.eu`, usato per comporre il
  link alla scheda dentro i messaggi.
- Un **toggle on/off** silenzia le notifiche senza cancellare il token.

L'email (usata per il **recupero password** e, opzionalmente, per l'allerta d'emergenza) si
configura nella stessa pagina: server SMTP, mittente, un toggle on/off e uno o più
destinatari per le email d'emergenza (separati da virgola), con un pulsante **Salva e invia
email di prova**. La pagina porta anche il **messaggio in emergenza** mostrato sul telefono
del soggetto — lascialo vuoto per usare il testo dell'app, tradotto nella lingua dell'app;
compilalo solo per forzare un messaggio fisso in una sola lingua. Tutte le impostazioni di
notifica vivono nel database — non ci sono variabili d'ambiente per le notifiche.

## 7. Aggiornamento

```bash
git pull
docker compose up -d --build
```

## 8. Backup

L'intero stato è il file SQLite sotto `data/`. Fanne un backup con una copia o
`sqlite3 .backup`.
