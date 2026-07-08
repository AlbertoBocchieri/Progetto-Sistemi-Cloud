# User Stories

## Utente

- Come utente, apro l'app e vedo la parcheggiabilita intorno a me.
- Come utente, cambio posizione demo e vedo zona corrente e zone vicine.
- Come utente, vedo score, trend, confidence e tempo stimato.
- Come utente, scelgo una destinazione demo e confronto la sua parcheggiabilita.
- Come utente, invio una segnalazione rapida.
- Come utente, chiedo una spiegazione AI/fallback on-demand.

## Admin Demo

- Come admin, avvio uno scenario sintetico.
- Come admin, vedo gli ultimi eventi ricevuti.
- Come admin, verifico lo stato di PostgreSQL, Redis e RabbitMQ.
- Come admin, resetto scenari e cache per ripetere la demo.

## Sistema

- Come sistema, ricevo eventi asincroni da RabbitMQ.
- Come sistema, aggiorno segnali Redis e invalido cache prediction/heatmap.
- Come sistema, calcolo prediction e heatmap senza dipendere da API esterne.
- Come sistema, mantengo sessioni anonime e coordinate approssimate.
