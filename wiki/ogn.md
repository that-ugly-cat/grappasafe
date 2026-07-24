# La rete OGN/FLARM

## Cos'è

**FLARM** è il transponder anticollisione montato su gran parte dei mezzi da volo (parapendio e deltaplano inclusi, con i dispositivi portatili). **OGN** — Open Glider Network — è la rete aperta di antenne a terra che riceve questi segnali e li pubblica come feed dati in tempo reale.

GrappaSafe ascolta il feed OGN e segue **tutti i beacon nell'area del Grappa**: posizione, quota, velocità verticale, tipo di mezzo. Questo copre anche chi non usa l'app — e dà al sistema un dato che il telefono non ha: una **velocità verticale pulita e affidabile**, misurata dal FLARM.

## Cosa vediamo

Per ogni dispositivo FLARM nell'area, il sistema riceve dal feed pubblico OGN:

- l'**identificativo del dispositivo** (l'ID OGN/FLARM — una sigla, non un nome);
- **posizione, quota e velocità** aggiornate a ogni beacon;
- il **tipo di aeromobile** dichiarato dal dispositivo.

Su questi dati girano due reti di sicurezza specifiche del volo (i dettagli nella pagina [emergenze](/wiki/emergenze)):

- **paracadute d'emergenza** — discesa sostenuta a rateo da paracadute seguita da immobilità;
- **segnale perso dopo discesa anomala** — la discesa c'è stata, poi il beacon tace vicino a terra.

## Dispositivo non abbinato: cosa succede

Le reti di sicurezza OGN girano **per tutti i dispositivi nell'area**, abbinati o no. Se un beacon anonimo mostra una discesa d'emergenza, l'allarme scatta comunque: gli operatori vedono posizione e ID del dispositivo, ma non sanno *chi* sei — niente nome, niente telefono, niente dati medici, nessuna notifica sul tuo telefono.

## Dispositivo abbinato: cosa cambia

Se nel tuo profilo (web o app, sezione **I miei dispositivi**) associ l'ID OGN/FLARM della tua vela o del tuo mezzo:

- un allarme OGN sul tuo dispositivo arriva ai soccorritori **con la tua identità**: nome, telefono, contatto d'emergenza, gruppo sanguigno, note di salute;
- le due sorgenti si fondono: se usi anche l'app, il sistema sa che il beacon e il telefono sono la stessa persona, e tiene **una sola emergenza** — la sorgente più rapida vince, l'altra non duplica;
- le reti si completano: l'OGN porta la rete paracadute (che il telefono non può avere), l'app porta l'accelerometro (che il FLARM non ha).

Per trovare o registrare il tuo ID: [ogn.flarm.com](https://ogn.flarm.com/) e [glidernet.org](https://www.glidernet.org/). Il pulsante «?» nella sezione dispositivi dell'app spiega il percorso.

## Un limite da conoscere

Le antenne OGN coprono bene l'area, ma la radio è radio: valli strette, ostacoli e la quota bassa creano **zone d'ombra**. Un beacon che sparisce in quota in una zona d'ombra non è distinguibile da un buco di copertura, e non genera allarme. I dettagli nella pagina [limiti](/wiki/limiti).
