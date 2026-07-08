# Product Requirements

## Obiettivo

ParcheggIA e' un radar di parcheggiabilita per Catania: mentre l'utente si muove, mostra zona corrente, score, trend, tempo stimato di ricerca, alternative vicine e spiegazione AI/fallback.

## MVP Incluso

- Live radar con posizione demo.
- Heatmap per zone Catania.
- Seed parcheggi demo associati alle zone.
- Top zone vicine.
- Segnalazioni rapide.
- Destinazione opzionale su zone demo.
- Dashboard admin con health fonti ed eventi recenti.
- Admin service dedicato dietro gateway.
- Scenari sintetici via RabbitMQ.
- Prediction rule-based con Redis cache.
- Nemotron fallback service.
- Docker Compose, Kubernetes locale, Terraform/Ansible e CI.

## Fuori Scope

- Pagamenti.
- Navigazione turn-by-turn.
- Account utente reali.
- App mobile nativa.
- Sensori IoT reali.
- Geocoder esterno obbligatorio.
- Modello AI proprietario obbligatorio.

## Definition Of Done

- `scripts/run_checks.sh` passa.
- La demo parte con `docker compose up --build`.
- Il frontend e' raggiungibile su `http://localhost:8080`.
- I servizi espongono `/health` e `/ready`.
- La documentazione copre architettura, API, dati, privacy, test, K8s, IaC e demo.
