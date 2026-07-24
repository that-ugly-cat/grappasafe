# Il server e il monitoraggio

## Cosa fa il server

Il server GrappaSafe riceve i dati dalle due sorgenti (app e OGN) e li passa a due motori:

- la **macchina degli stati** descrive cosa sta facendo ogni entità — in volo: a terra / in aria / atterrato; a terra: in movimento / fermo / impatto. Le transizioni sono confermate nel tempo, non al singolo dato, così un GPS ballerino non genera falsi allarmi;
- la **macchina delle emergenze** decide quando una situazione diventa un'emergenza (i criteri sono descritti nella pagina [emergenze](/wiki/emergenze)).

Tutte le soglie sono regolabili dal consorzio senza fermare il sistema, e vengono tarate sui dati reali raccolti.

## Chi ha accesso a cosa

Tre livelli di accesso:

- **Utente** (tu) — vede e gestisce solo i propri dati: profilo, dispositivi, le proprie sessioni. Nessun accesso ai dati degli altri.
- **Observer** (operatori del consorzio) — vede la dashboard live e le emergenze in sola lettura, può aprire i profili per contatti e dati medici quando serve, e può prendere in carico e risolvere le emergenze. Non modifica utenti né configurazioni.
- **Admin** — accesso completo: gestione utenti e ruoli, configurazione delle soglie, export delle tracce per la taratura del sistema.

## Come il consorzio monitora e gestisce le emergenze

Gli operatori hanno una **dashboard live** con la mappa di tutte le entità attive nell'area — utenti dell'app e beacon OGN — con le emergenze in evidenza. Quando scatta un allarme:

1. **Notifica immediata** agli operatori (gruppo Telegram ed email) con identità, posizione e dati medici del soggetto — più un avviso a tutto schermo su qualsiasi pagina del pannello.
2. **Triage**: un operatore **prende in carico** l'emergenza. Questo viene comunicato anche al tuo telefono — sai che qualcuno ti ha visto e si sta muovendo.
3. **Gestione**: l'operatore valuta la situazione — contatto telefonico, contatto d'emergenza, attivazione del soccorso — con la scheda dell'emergenza davanti: posizione aggiornata, traccia, dati medici. La scheda è condivisibile anche con soccorritori esterni tramite un **link pubblico a scadenza (24 ore)**.
4. **Risoluzione**: l'emergenza si chiude con una **nota obbligatoria** che documenta com'è andata. La chiusura termina anche la sessione di monitoraggio.

Ogni passaggio — pre-allarme inviato, annullato, confermato, aperto, preso in carico, risolto — viene **registrato** con orario. Anche i falsi allarmi annullati restano in archivio: servono a tarare meglio le soglie.

## Cosa succede alle tracce

- Le tracce **senza emergenza** vengono cancellate automaticamente dopo un periodo di conservazione breve (default: 7 giorni, configurabile dal consorzio).
- Le tracce **con emergenza** vengono conservate: sono la documentazione dell'incidente.
- Al momento di un'emergenza, il sistema fotografa **chi altro era tracciato entro 300 m**: i potenziali testimoni non si perdono con la cancellazione automatica delle tracce.

Il dettaglio completo su dati e conservazione è nella pagina [privacy](/wiki/privacy).
