# Privacy e conservazione dei dati

> ⚠︎ **Da completare prima della pubblicazione**: denominazione esatta del titolare del trattamento, indirizzo e contatto privacy. Questa pagina è una descrizione tecnica fedele del funzionamento del sistema; la sua validazione legale è responsabilità del titolare.

## Quali dati raccogliamo

**Dati di account e profilo** — nome, cognome, username, email, telefono, data di nascita, lingua. Facoltativi ma fortemente consigliati, perché sono ciò che arriva ai soccorritori: gruppo sanguigno, note di salute, contatto d'emergenza. I dati sanitari li inserisci **tu, volontariamente**: il sistema non li deduce da nulla.

**Dati di tracciamento (solo durante una sessione attiva)** — posizione GPS, quota, velocità, livello di batteria, e il **picco di accelerazione** per ogni intervallo: un singolo numero, non una registrazione continua del sensore. Il tracciamento parte quando avvii un'attività e si ferma quando la chiudi: l'app non ti localizza fuori dalle sessioni.

**Dati OGN** — se abbini un ID OGN/FLARM, i beacon del tuo dispositivo nell'area vengono associati al tuo profilo. I beacon OGN sono trasmissioni radio pubbliche, ricevute da una rete aperta.

**Cosa NON raccogliamo** — niente microfono (l'app non ne chiede il permesso), niente fotocamera, niente contatti, niente tracciamento pubblicitario, nessuna cessione di dati a terzi per fini commerciali. I cookie del sito sono solo tecnici (sessione di accesso).

## Per cosa li usiamo

Un solo scopo: la **tua sicurezza** — rilevare le emergenze, allertare i soccorritori con le informazioni che servono, documentare gli incidenti. I dati aggregati delle tracce servono inoltre alla **taratura delle soglie** di rilevamento (meno falsi allarmi, rilevamento più affidabile).

## Chi vi ha accesso

- **Tu** — i tuoi dati, sempre, dal profilo (web o app).
- **Gli operatori del consorzio** (ruoli observer e admin) — la dashboard di monitoraggio e, quando serve per un'emergenza, i profili con contatti e dati medici.
- **In caso di emergenza** — identità, posizione e dati medici partono verso i canali operativi del consorzio (gruppo Telegram, email degli operatori). La scheda dell'emergenza può essere condivisa con soccorritori esterni tramite un link che **scade dopo 24 ore**.
- **Chi riceve il tuo link di tracking live** — la tua traccia della sessione in corso, finché la sessione è attiva. Il link lo condividi tu.
- **I sistemi terzi che attivi tu** — se accendi l'inoltro dati (vedi sotto), la tua posizione arriva anche lì.

## Inoltro a sistemi terzi (facoltativo, spento di default)

Dalle impostazioni dell'app puoi far mandare la tua posizione anche a un altro sistema di tracciamento, per esempio Vedetta, dove un gruppo di amici segue i tuoi voli. Funziona così:

- **Lo attivi tu**, sistema per sistema, e lo spegni quando vuoi. L'interruttore *è* il consenso: senza, non parte nulla. La data di attivazione viene registrata.
- **A inoltrare è il server**, non il telefono: nessun consumo di batteria aggiuntivo.
- **Viene inoltrata solo la posizione** — coordinate, quota, velocità, attività e stato di volo. Nel pacchetto non c'è nemmeno il tuo nome: chi lo riceve sa già chi sei, perché sei tu ad avergli dato il token. Niente dati sanitari, niente contatti d'emergenza, e nessun allarme: le emergenze restano dentro GrappaSafe e sui canali del consorzio.
- **L'inoltro è attivo solo durante una sessione**, come tutto il resto del tracciamento.
- **Da lì in poi valgono le regole dell'altro sistema.** Una volta uscito da GrappaSafe, quel dato è conservato secondo la privacy di chi lo riceve, non la nostra: se spegni l'inoltro, smettiamo di mandare, ma quello che è già arrivato lo cancella l'altro sistema.

## Per quanto li conserviamo

| Dato | Conservazione |
|---|---|
| Tracce GPS e beacon OGN **senza emergenza** | Cancellati automaticamente dopo pochi giorni (default: 7, impostazione del consorzio) |
| Tracce e beacon **relativi a un'emergenza** | Conservati come documentazione dell'incidente |
| Presenze entro 300 m al momento di un'emergenza (potenziali testimoni) | Conservate con l'emergenza |
| Registro eventi delle emergenze (inclusi i falsi allarmi annullati) | Conservato per l'audit e la taratura |
| Dati di account e profilo | Finché l'account esiste |

## I tuoi diritti (GDPR)

- **Accesso e rettifica** — profilo e dispositivi sono self-service: vedi e correggi i tuoi dati in autonomia.
- **Cancellazione** — puoi chiedere la cancellazione dell'account e dei dati associati contattando il titolare (recapito in fondo alla pagina). I dati di emergenze già documentate possono essere conservati dove esiste un obbligo o un legittimo interesse alla documentazione dell'incidente.
- **Portabilità** — puoi richiedere l'export dei tuoi dati.
- **Reclamo** — hai diritto di rivolgerti al Garante per la Protezione dei Dati Personali.

Base giuridica in sintesi: il trattamento si fonda sul tuo **consenso** (registrazione e uso volontario del servizio); per i dati sanitari che scegli di inserire, sul **consenso esplicito**; nella gestione di un'emergenza, sulla **salvaguardia degli interessi vitali** della persona.

> ⚠︎ **Titolare del trattamento**: *[da completare — denominazione, sede, contatto email]*
