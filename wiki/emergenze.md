# Le emergenze: quando scatta un allarme

GrappaSafe distingue tra due modi di attivazione:

- **immediato** — l'emergenza si apre subito (SOS manuale, reti OGN);
- **con conferma** — prima dell'allarme ricevi sul telefono una **richiesta di conferma** con un conto alla rovescia: *«Sto bene»* la annulla, *«Chiama i soccorsi»* la conferma subito, il silenzio la fa scattare da sola. È il paracadute contro i falsi allarmi — e contro l'eventualità che tu non possa rispondere.

Le soglie esatte (accelerazioni, velocità, tempi) sono in corso di taratura sui dati reali e vengono regolate dal consorzio; qui descriviamo le *condizioni*, che sono stabili.

## I trigger

### SOS manuale — *immediato*
Tieni premuto il pulsante SOS per 3 secondi. Funziona con o senza sessione attiva. È sempre la via più diretta: se sei cosciente e hai il telefono, usala.

### Impatto seguito da immobilità — *con conferma* (app, volo e terra)
L'accelerometro rileva un picco violento — una caduta, un urto, un atterraggio duro — e nei minuti successivi la posizione non si sposta dal punto dell'impatto. Se dopo l'urto ti muovi e ti allontani, l'impatto viene dimenticato: evidentemente stai bene. Per l'**arrampicata** il solo impatto è sufficiente (dopo un volo in parete si può restare appesi: l'immobilità orizzontale non significa nulla).

### Immobilità prolungata senza impatto — *con conferma* (app, a terra)
Fermo a lungo, senza che ci sia stato un urto. Disattivata di default: una lunga sosta di solito è solo una sosta. Il consorzio può attivarla per attività o periodi specifici.

### Paracadute d'emergenza — *immediato* (OGN, solo volo)
Il FLARM mostra una discesa **sostenuta a rateo da paracadute** che *non rientra* in volo normale, seguita da **immobilità** al suolo. Le manovre di discesa rapida intenzionali (orecchie, B-stall, spirale) hanno lo stesso rateo ma *rientrano* in volo normale prima di terra — e allora non scatta nulla: è l'esito a distinguere l'emergenza dalla manovra.

### Segnale perso dopo discesa anomala — *immediato dopo una breve attesa* (OGN, solo volo)
La discesa a rateo da paracadute c'è stata, poi il beacon **tace vicino a terra**. Il sistema aspetta qualche minuto un ritorno del segnale; se resta muto e l'ultima quota era bassa, l'allarme parte. Un atterraggio normale (nessuna discesa anomala prima) e un buco di copertura in quota non attivano questa rete.

## Cosa succede quando l'emergenza si apre

### Se usi l'app
1. Nel caso dei trigger *con conferma*: il telefono **suona ad alto volume** — anche in silenzioso, anche a schermo bloccato — e mostra la schermata di conferma con il conto alla rovescia.
2. All'apertura dell'emergenza (confermata, scaduta, o immediata): gli **operatori del consorzio ricevono subito** posizione, identità e dati medici. L'app mostra lo stato: quando un operatore prende in carico, lo vedi sullo schermo.
3. Il monitoraggio continua per tutta l'emergenza: la tua posizione resta aggiornata per i soccorritori. L'emergenza si chiude quando un operatore la risolve.

Se il telefono **muore dopo l'impatto** (rotto, scarico): l'allarme parte comunque. Il server nota l'assenza di risposta alla richiesta di conferma e apre l'emergenza da solo, con l'ultima posizione nota.

### Se non usi l'app (solo OGN)
L'allarme si apre lo stesso, sulle reti paracadute e segnale-perso:

- **dispositivo abbinato a un profilo** → l'allarme porta la tua identità e i tuoi dati medici, come per l'app;
- **dispositivo non abbinato** → gli operatori vedono posizione e ID del dispositivo, senza sapere chi sei. L'allarme c'è, ma il soccorso parte con meno informazioni — [abbina il tuo dispositivo](/wiki/ogn), è un minuto di lavoro.

In entrambi i casi, senza app **non ricevi nulla sul telefono**: nessuna richiesta di conferma, nessuna possibilità di annullare un falso allarme. Gli operatori gestiscono la verifica.
