# ParcheggIA

Demo locale per il progetto di Sistemi Cloud: radar di parcheggiabilita su zone di Catania.

## Avvio rapido

```bash
docker compose up -d --build
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

Non serve un file `.env` per la demo locale: senza API key esterne l'app carica automaticamente i segmenti OSM di Catania, usa stime simulate locali, suggerimenti fallback e TTS del browser. Per verificare lo stack dopo l'avvio:

```bash
scripts/smoke_test.sh
scripts/e2e_demo_test.sh
```

## Segmenti OSM Catania

I segmenti stradali OSM del Comune di Catania sono gia' inclusi in `data/osm/catania_segments.sql` e vengono caricati da `docker compose up`. Per rigenerarli manualmente:

```bash
python3 scripts/import_osm_segments.py --fetch --output data/osm/catania_segments.sql
docker compose exec -T postgres psql -U parcheggia -d parcheggia < data/osm/catania_segments.sql
python3 scripts/apply_parking_overrides.py
docker compose exec -T postgres psql -U parcheggia -d parcheggia < data/osm/catania_blue_overrides.sql
curl -fsS -X POST http://localhost:8000/api/v1/admin/demo-scenarios/reset
```

Gli override strisce blu sono in `data/parking_overrides/catania_blue_zones.csv` e derivano dal piano sosta AMTS. Il match e' per nome strada OSM normalizzato: copre le vie riconosciute con sicurezza e lascia `probable_free` dove il piano non combacia con un segmento OSM.

## TomTom parsimonioso

La key TomTom resta solo backend. In test il cap predefinito e' il 5% delle quote mensili configurate:

```bash
TOMTOM_API_KEY=...
TOMTOM_BUDGET_FRACTION=0.05
```

Endpoint operativi:

```http
GET  /ingestion/traffic/tomtom/probe?lat=37.507&lon=15.083&radius_m=500
POST /ingestion/traffic/tomtom/publish
GET  /api/v1/tomtom/parking-pois?lat=37.507&lon=15.083&radius_m=500
GET  /ingestion/traffic/tomtom/budget
```

`probe` e `publish` usano cache 5 minuti per cella circa 250m. `parking-pois` usa Search API con cache 24 ore e trova `7369` Open Parking Area e `7313` Parking Garage, senza disponibilita' live.
La GUI usa `publish` in modalita' conservativa: una cella live consuma fino a 5 chiamate Traffic Flow e 1 Traffic Incidents; se la cache backend o frontend e' valida, consuma 0.

## Suggerimenti Nemotron

La key Nemotron resta solo backend. Per attivare i suggerimenti live, aggiungi al `.env` locale:

```bash
NEMOTRON_API_KEY=...
NEMOTRON_BASE_URL=https://integrate.api.nvidia.com/v1
NEMOTRON_MODEL=nvidia/nemotron-3-nano-30b-a3b
NEMOTRON_TIMEOUT_SECONDS=45
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
ELEVENLABS_SIMILARITY_BOOST=0.50
ELEVENLABS_STYLE_EXAGGERATION=0.25
```

Il frontend chiama solo `/ai/explain`. Se la key manca o l'endpoint non risponde, `nemotron-service` usa il fallback locale.
Per la voce naturale, il frontend chiama `/ai/tts`: se ElevenLabs non risponde, torna automaticamente al TTS del browser.

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

Per simulare l'architettura cloud senza account AWS e senza API key esterne:

```bash
scripts/cloud_sim_local_up.sh
```

Questo avvia un cluster k3d, deploya i microservizi su Kubernetes, importa i segmenti OSM reali, usa prediction/suggerimenti/TTS simulati e restituisce l'URL locale:

```text
http://localhost:18080
```

Spegnimento:

```bash
scripts/cloud_sim_local_down.sh
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
GET  /segments
GET  /segments/current?lat=37.507&lon=15.083
GET  /segments/nearby?lat=37.507&lon=15.083&radius_m=500
GET  /road-network?lat=37.507&lon=15.083&radius_m=700
GET  /segments/{segment_id}
GET  /segments/{segment_id}/prediction
GET  /segment-heatmap?bbox=15.073,37.500,15.093,37.516&zoom=18
GET  /tomtom/parking-pois?lat=37.507&lon=15.083&radius_m=500
POST /live-sessions/start
POST /live-sessions/{session_id}/location
GET  /live-sessions/{session_id}/nearby-segments
POST /live-sessions/{session_id}/stop
POST /segment-reports
POST /predictions
GET  /predictions/{prediction_id}
GET  /admin/source-health
GET  /admin/events
POST /admin/demo-scenarios/reset
GET  http://localhost:8002/scenarios
POST http://localhost:8002/scenarios/{scenario_id}/start
GET  http://localhost:8002/traffic/tomtom/budget
POST http://localhost:8003/ai/explain
```

## Stato MVP

Implementato per demo locale: frontend statico, dashboard admin, zone-service geospaziale, prediction-service, location-service, admin-service, ingestion-service con scenari demo, Nemotron fallback service, PostgreSQL/PostGIS, Redis, RabbitMQ, seed zone Catania, heatmap, prediction demo e report utente rapidi.

Non eseguito automaticamente: deploy AWS reale e modello Nemotron reale, perche' richiedono credenziali/costi o provider AI esterno. La repo contiene IaC, deploy Kubernetes locale verificato e fallback locale.
