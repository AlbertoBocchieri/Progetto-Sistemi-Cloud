# Architettura Demo Locale

```text
Browser
  |
  | http://localhost:8080
  v
Frontend statico nginx
  |
  | http://localhost:8000
  v
API Gateway nginx
  |
  +--> Zone Service --> PostgreSQL + PostGIS
  +--> Prediction Service --> PostgreSQL + Redis
  +--> Location Service --> Redis + RabbitMQ
  +--> Admin Service --> Redis + RabbitMQ + Zone Service
  +--> Ingestion Service --> RabbitMQ
  +--> Nemotron Service --> Rule-based fallback

RabbitMQ eventi --> Zone Service consumer --> Redis segnali zona
```

Servizi Docker:

- `frontend`: UI demo con mappa SVG, heatmap e bottoni report.
- `zone-service`: API geospaziale, report, admin demo e consumer eventi.
- `prediction-service`: parkability, prediction by-id e heatmap.
- `location-service`: live session, posizione utente e nearby zones.
- `admin-service`: dashboard admin, eventi recenti, reset scenari e source health.
- `ingestion-service`: pubblica scenari sintetici su RabbitMQ.
- `nemotron-service`: spiegazioni AI/fallback senza dati esterni.
- `postgres`: database relazionale geospaziale.
- `db-init`: applica seed SQL idempotente.
- `redis`: cache heatmap/prediction, live session e segnali zona.
- `rabbitmq`: exchange eventi per scenari demo.

Scelta ponytail: gli endpoint admin legacy restano nel `zone-service`, ma il gateway usa `admin-service`.

## Delivery

- Docker Compose: `docker compose up --build`
- Quality gate locale: `scripts/run_checks.sh`
- Kubernetes locale: `scripts/k8s_apply_local.sh`
- CI GitHub Actions: `.github/workflows/ci.yml`
- Metriche demo: `GET http://localhost:8001/metrics`
- Log applicativi: JSON su stdout con `request_id`, metodo, path, status e durata.
