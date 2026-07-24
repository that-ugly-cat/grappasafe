# I limiti del sistema

Questa è la pagina più importante della guida. GrappaSafe è una rete di sicurezza aggiuntiva: **funziona spesso, non sempre**. Conoscere i casi in cui può non funzionare è parte dell'usarlo bene.

## La regola prima di tutte

**Se puoi chiamare il 118, chiama il 118.** GrappaSafe non sostituisce la chiamata d'emergenza: la integra, per i casi in cui chiamare non puoi.

## Quando l'app può non proteggerti

**Niente rete cellulare.** Il GPS funziona anche senza rete, ma i dati non partono: si accumulano sul telefono e arrivano al server *quando la rete torna*. In un buco di copertura prolungato, un impatto viene rilevato **in ritardo** — anche di molto. Un SOS premuto senza rete resta in coda e parte appena possibile, e l'app ti dice chiaramente che non è ancora stato consegnato. Sul Grappa la copertura è complessivamente buona, ma forre, versanti nord e canaloni hanno buchi reali.

**Telefono spento, scarico o distrutto.** Un monitoraggio che vive sul telefono muore col telefono. Il server ha una protezione parziale: se il flusso di dati si interrompe *dopo* che una richiesta di conferma è stata inviata, l'allarme si apre da solo con l'ultima posizione nota. Ma un telefono che muore *prima* di qualsiasi rilevamento non lascia nulla da rilevare. Parti con la batteria carica; per le attività lunghe, intervallo GPS più lento e powerbank.

**Permessi e risparmio energetico.** Se la posizione non è su «Consenti sempre», se le notifiche sono bloccate, o se l'ottimizzazione batteria è attiva per GrappaSafe, il monitoraggio a schermo spento è compromesso. Usa **Verifica permessi** nelle impostazioni: tre spunte verdi = a posto. Sui telefoni con risparmi energetici del produttore (Xiaomi, Huawei, Oppo…) serve anche l'esclusione manuale nelle impostazioni di sistema.

**GPS degradato.** Bosco fitto, pareti, forre: la posizione può essere imprecisa o saltare. Il sistema filtra i dati di bassa qualità e tollera i valori anomali, ma una posizione degradata resta meno affidabile — e i soccorritori arrivano dove dice il GPS.

**Modalità aereo.** Tutto ciò che è radio tace: niente invii, niente allarmi in tempo reale. Se la usi per risparmiare batteria, sappi che stai spegnendo anche GrappaSafe.

## Quando la rete OGN può non proteggerti

**Zone d'ombra radio.** Le antenne OGN ricevono in linea d'aria: valli strette e bassa quota creano zone senza ricezione. Un beacon che sparisce **in quota** in una zona d'ombra non è distinguibile da un normale buco di copertura: il sistema non può allarmare su ogni segnale perso, diventerebbe inutilizzabile. La rete segnale-perso scatta solo quando la sparizione segue una **discesa anomala** ed è **vicino a terra**.

**FLARM spento, scarico o non funzionante.** Vale quanto per il telefono: nessun segnale, nessuna protezione. Controlla il tuo dispositivo come controlli la vela.

**Dispositivo non abbinato.** L'allarme scatta, ma anonimo: i soccorritori non sanno chi sei, non hanno i tuoi dati medici, non possono chiamarti. [Abbinare l'ID](/wiki/ogn) al profilo costa un minuto.

## Limiti geografici

Il sistema monitora un **cerchio di ~19 km attorno al Monte Grappa**: è l'area coperta dalle antenne e presidiata dal consorzio. L'app ti avvisa quando ne esci (se l'avviso è attivo nelle impostazioni). Fuori dal cerchio, l'app continua a tracciare ma l'infrastruttura di monitoraggio OGN e l'operatività locale non sono garantite.

## Limiti del rilevamento

Il rilevamento automatico è **probabilistico, non infallibile**. Un incidente può non superare le soglie (una caduta "morbida" senza picco netto, un malore da fermo con l'immobilità disattivata); un evento innocuo può superarle (le richieste di conferma esistono per questo). Le soglie vengono tarate continuamente sui dati reali, ma la garanzia assoluta non esiste — per questo il **SOS manuale** resta sempre disponibile, e la testa sulle spalle resta il primo dispositivo di sicurezza.
