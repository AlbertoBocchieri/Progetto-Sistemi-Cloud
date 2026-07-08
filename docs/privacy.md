# Privacy

ParcheggIA demo usa sessioni anonime.

## Dati Posizione

- La UI invia solo coordinate demo.
- La sessione usa un UUID casuale.
- Lo stato sessione viene salvato in Redis con TTL.
- Non vengono salvati account, device ID, targhe o cronologia utente persistente.

## Report Utente

I report sono aggregabili per zona:

- `found_spot`
- `full_zone`
- `released_spot`
- `parking_closed`

Possono includere solo il `session_id` anonimo per rate limit temporaneo.

## Retention Demo

- `live_session:{session_id}` scade dopo 1 ora.
- `rate_limit:report:{session_id}` scade dopo 30 secondi.
- `zone:signals:{zone_id}` scade dopo 30 minuti.
- `raw_events` conserva solo gli ultimi 100 eventi.

## Limiti

Per una versione reale servono:

- consenso privacy;
- retention configurabile;
- audit log;
- informativa utente;
- minimizzazione coordinate precise;
- cancellazione dati.
