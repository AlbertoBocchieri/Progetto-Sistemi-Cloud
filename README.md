# ParcheggIA

Demo locale per il progetto di Sistemi Cloud: radar di parcheggiabilita su zone di Catania.

## Avvio rapido

```bash
docker compose up --build
```

Frontend demo:

```text
http://localhost:8080
```

API Gateway:

```text
http://localhost:8000/api/v1
```

API FastAPI:

```text
http://localhost:8001/docs
```

Prediction service:

```text
http://localhost:8004/docs
```

Location service:

```text
http://localhost:8005/docs
```

Admin service:

```text
http://localhost:8006/docs
```

Ingestion service:

```text
http://localhost:8002/docs
```

Nemotron fallback service:

```text
http://localhost:8003/docs
```

RabbitMQ management:

```text
http://localhost:15672
```

Credenziali demo RabbitMQ: `parcheggia` / `parcheggia`.

## Smoke test

Con i container avviati:

```bash
scripts/smoke_test.sh
```

Quality gate completo:

```bash
scripts/run_checks.sh
```

Controlli senza avviare container:

```bash
scripts/static_checks.sh
```

## Kubernetes locale

Manifest e script sono in [docs/kubernetes-local.md](docs/kubernetes-local.md).
Su macOS Sequoia il runtime verificato in shell e' `colima` + `k3d`, con preset leggero per 8 GB RAM:

```bash
scripts/colima_start.sh
scripts/k3d_prepare_local.sh
scripts/k8s_apply_local.sh
```

## IaC e AWS

Ansible e Terraform sono documentati in [docs/iac-aws.md](docs/iac-aws.md).

## Documenti

- [Architettura](docs/architecture.md)
- [Product requirements](docs/product-requirements.md)
- [User stories](docs/user-stories.md)
- [API](docs/api-spec.md)
- [Data model](docs/data-model.md)
- [Event flow](docs/event-flow.md)
- [Deployment view](docs/deployment-view.md)
- [Test plan](docs/test-plan.md)
- [Privacy](docs/privacy.md)
- [Kubernetes locale](docs/kubernetes-local.md)
- [Cloud deployment](docs/cloud-deployment.md)
- [Demo script](docs/demo-script.md)
- [Verification matrix](docs/verification-matrix.md)
- [Outline presentazione](docs/professor-presentation-outline.md)

## Endpoint principali

```http
GET  /health
GET  /ready
GET  /zones
GET  /zones/current?lat=37.507&lon=15.083
GET  /zones/nearby?lat=37.507&lon=15.083&radius_m=2200
GET  /zones/{zone_id}
GET  /zones/{zone_id}/prediction
GET  /heatmap
POST /live-sessions/start
POST /live-sessions/{session_id}/location
GET  /live-sessions/{session_id}/nearby-zones
POST /live-sessions/{session_id}/stop
POST /reports
POST /predictions
GET  /predictions/{prediction_id}
GET  /admin/source-health
GET  /admin/events
POST /admin/demo-scenarios/reset
GET  http://localhost:8002/scenarios
POST http://localhost:8002/scenarios/{scenario_id}/start
POST http://localhost:8003/ai/explain
```

## Stato MVP

Implementato per demo locale: frontend statico, dashboard admin, zone-service geospaziale, prediction-service, location-service, admin-service, ingestion-service con scenari demo, Nemotron fallback service, PostgreSQL/PostGIS, Redis, RabbitMQ, seed zone Catania, heatmap, prediction demo e report utente rapidi.

Non eseguito automaticamente: deploy AWS reale e modello Nemotron reale, perche' richiedono credenziali/costi o provider AI esterno. La repo contiene IaC, deploy Kubernetes locale verificato e fallback locale.
