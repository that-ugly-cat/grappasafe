# L'app GrappaSafe

## Cosa fa

L'app trasforma il telefono in un dispositivo di monitoraggio personale. Durante un'attività:

- registra la **posizione GPS** a intervalli regolari e la invia al server, anche a schermo spento e con il telefono in tasca;
- misura con l'**accelerometro** il picco di accelerazione tra un invio e l'altro — è così che un impatto viene rilevato anche se avviene tra due posizioni GPS;
- riceve dal server le **richieste di conferma** quando viene rilevata una situazione anomala, e le fa suonare forte, anche in modalità silenziosa e a schermo bloccato;
- offre un pulsante **SOS** sempre disponibile per chiedere aiuto manualmente.

L'accelerometro **non registra** un flusso continuo: per ogni posizione inviata viene trasmesso un solo numero, il picco di accelerazione della finestra. Il microfono non viene mai usato — l'app non ne chiede nemmeno il permesso.

## Come funziona una sessione

1. Apri l'app e premi **Inizia attività**, scegliendo il tipo (parapendio, deltaplano, escursionismo, bici, arrampicata, corsa, altro). Il tipo di attività regola la sensibilità del rilevamento: un atterraggio in parapendio e una pedalata su sterrato producono accelerazioni molto diverse.
2. Da quel momento il telefono può stare in tasca, a schermo spento: la posizione e il picco di accelerazione partono a ogni intervallo. Una notifica fissa ti ricorda che il monitoraggio è attivo.
3. Se il server rileva qualcosa di anomalo, il telefono **suona ad alto volume** e mostra la schermata di conferma: *«Sto bene»* (falso allarme, tutto si annulla) oppure *«Chiama i soccorsi»*. Se non rispondi entro il tempo limite, l'allarme parte da solo — l'ipotesi è che tu non sia in grado di rispondere.
4. A fine attività premi **Stop**. La sessione si chiude anche sul server.

Se resti **senza copertura**, i punti non vanno persi: si accumulano sul telefono e partono appena torna la rete, con il loro orario originale. Lo stesso vale per un SOS premuto senza rete: resta in coda e viene ritentato in continuazione finché il server non lo riceve.

### SOS manuale

Il pulsante rosso **SOS** funziona anche *senza* una sessione attiva. Tienilo premuto per 3 secondi: parte la richiesta d'aiuto con la tua posizione. Finché un operatore non prende in carico, l'app mostra lo stato dell'invio — incluso l'avviso esplicito se l'invio non è riuscito, così sai che devi chiamare direttamente il 118.

### Condivisione live

Durante una sessione puoi condividere un **link di tracking live** (dal chip in alto sulla mappa): chi lo apre vede la tua traccia aggiornarsi, senza bisogno di un account. Utile per chi ti aspetta a casa o all'atterraggio.

## Impostazioni

- **Frequenza dei punti GPS** — da 5 a 60 secondi. Più fitta = traccia più precisa e rilevamento più reattivo, ma più consumo di batteria.
- **Avvisi fuori zona** — una notifica quando esci dal cerchio monitorato (fuori dal cerchio il monitoraggio OGN e l'operatività del consorzio non sono garantiti).
- **Mappa offline** — scarica la cartografia della zona sul telefono: la mappa funziona anche senza rete.
- **Lingua** — italiano, inglese, tedesco, francese, spagnolo, olandese, polacco, ceco.
- **Profilo** — i tuoi dati anagrafici e medici (gruppo sanguigno, note di salute, contatto d'emergenza). Sono i dati che arrivano ai soccorritori quando scatta un allarme: tienili aggiornati.
- **I tuoi dispositivi** — le tue vele/mezzi con l'eventuale ID OGN/FLARM (vedi [la pagina OGN](/wiki/ogn)).

## Permessi: perché servono e come impostarli

Il monitoraggio a schermo spento è tecnicamente esigente, e Android è aggressivo nel risparmiare batteria. Nelle impostazioni dell'app c'è la voce **Verifica permessi** che controlla tutto e ti guida; queste sono le tre autorizzazioni che servono:

1. **Posizione: "Consenti sempre"** — non basta "mentre usi l'app": il GPS deve funzionare a schermo spento.
2. **Notifiche** — senza, non senti gli allarmi. Le notifiche d'emergenza suonano sul canale *sveglia*: passano anche con il telefono in silenzioso.
3. **Batteria senza limitazioni** — con l'ottimizzazione batteria attiva, Android blocca l'invio dei dati a schermo spento. L'app te lo chiede al primo avvio di un'attività.

Su alcuni telefoni (Xiaomi, Huawei, Oppo e simili) c'è un ulteriore risparmio energetico del produttore: va esclusa GrappaSafe anche lì, nelle impostazioni batteria di sistema.

## Consumo di batteria

Il monitoraggio tiene attivi GPS, accelerometro e rete per tutta l'attività: il consumo è reale. Con l'intervallo di default, un'attività di mezza giornata è ampiamente nel raggio di una carica. Per attività molto lunghe: intervallo più lento (30–60 s) e una powerbank. Il livello di batteria viene trasmesso col resto dei dati, così gli operatori sanno quanto margine ha il tuo telefono.
