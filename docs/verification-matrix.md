# Verification matrix

Audit del 2026-07-09 rispetto a:

- `/Users/albertobocchieri/Downloads/ParcheggIA_Piano_Operativo.md`
- `/Users/albertobocchieri/Downloads/StrutturaProgettoCloud.md`
- `/Users/albertobocchieri/Downloads/ParcheggIA_Project_Plan_v0.2.md`

## Gate eseguiti

Ultimo gate locale eseguito con stack Docker attivo:

```bash
scripts/static_checks.sh
scripts/run_checks.sh
ITERATIONS=30 scripts/load_test.sh
```

Esito:

```text
Static checks OK
Smoke test OK
E2E demo OK
All checks OK
Load test OK: 30 iterations
```

Verifiche runtime puntuali:

- `GET /api/v1/segments/current?lat=37.507&lon=15.083` restituisce un segmento OSM su Via Plebiscito con tipo sosta e regole AMTS.
- `GET /api/v1/segments/nearby?lat=37.507&lon=15.083&radius_m=500&limit=5` restituisce segmenti vicini con predizione.
- `GET /api/v1/road-network?lat=37.507&lon=15.083&radius_m=700` restituisce 700 edge e 686 nodi.
- `GET /ai/ready` restituisce `mode=nemotron` e modello `nvidia/nemotron-3-nano-30b-a3b`.
- `GET /traffic/tomtom/budget` espone contatori e cap di test senza esporre la key.
- `git diff --check` non segnala whitespace/errori di patch.

## Requisiti prodotto

| Requisito | Evidenza repo | Stato |
|---|---|---|
| Radar continuo | `frontend`, `location-service`, `/live-sessions/*` | OK |
| Mappa live | MapLibre GL in `frontend/app.js` | OK |
| Heatmap parcheggiabilita | `/segment-heatmap`, ribbon/marker segmenti su MapLibre | OK |
| Segmenti piccoli per via | `parking_segments` da OSM, split max 120 m dove possibile | OK |
| Tipo sosta | override AMTS/Comune + inferenza `probable_free` | OK iniziale |
| Percentuale per tratto | prediction segment-level + marker su mappa | OK |
| Click-to-drive | snap su rete `road_edges`, non su segmenti parcheggio | OK |
| Simulazione guida | demo 500 m con camera e marker | OK |
| Parcheggi vicini | TomTom Search POI cache + marker animati | OK |
| Suggerimenti AI | Nemotron backend-only, target segmenti/POI validati | OK |
| TTS | `/ai/tts` con ElevenLabs e fallback browser | OK |
| Segnalazioni rapide | `POST /segment-reports`, influenza segmenti vicini | OK |
| Destinazione opzionale | pannelli visibili solo quando impostata | OK parziale/demo |
| Dashboard/admin demo | `admin-service`, scenari RabbitMQ, reset | OK |

## Requisiti backend e dati

| Requisito | Evidenza repo | Stato |
|---|---|---|
| API Gateway/BFF | nginx gateway su `8000`, proxy `/api/v1`, `/ai`, `/traffic` | OK |
| Zone/Segment Service | FastAPI + PostGIS, segmenti, road network, heatmap | OK |
| Location Service | FastAPI + Redis + RabbitMQ | OK |
| Prediction Service | rule-based segment-level + Redis signals | OK |
| Ingestion Service | scenari demo + TomTom Flow/Incidents/Search parsimonioso | OK |
| Admin Service | health fonti, eventi, scenari | OK |
| Nemotron Service | NVIDIA OpenAI-compatible + cache + fallback | OK |
| PostgreSQL/PostGIS | migrazioni con `parking_segments`, `road_edges`, `road_nodes` | OK |
| Redis | cache sessioni, segnali prediction, budget TomTom | OK |
| RabbitMQ | eventi applicativi e scenari demo | OK |
| OpenAPI/schema | `shared/openapi/parcheggia-api.yaml`, check contratti | OK base |
| MongoDB | opzionale nel piano | Non implementato |

## TomTom e quote

| Voce | Stato |
|---|---|
| Traffic Flow/Incidents | Integrati backend-only per segnali prediction locali |
| Search API parcheggi | Integrata backend-only per POI parcheggio entro 500 m |
| Routing API | Non integrata nella GUI; rinviata |
| Traffic tiles | Non usate, scelta corretta per evitare consumo tile |
| Guardrail quote | Redis budget guard, default 5% quota mensile |
| Raggio operativo | 500 m, cache cella circa 250 m, TTL 5 minuti |
| Chiamate per movimento GUI | Nessuna per ogni step; TomTom passa da cache/cella |

## Cloud e DevOps

| Requisito | Evidenza repo | Stato |
|---|---|---|
| Dockerfile servizi | frontend + backend services | OK |
| Docker Compose | `docker-compose.yml`, healthcheck, smoke | OK |
| Kubernetes locale | `infrastructure/k8s/local-demo.yaml`, kubeconform | OK |
| Multipass/k3s | playbook Ansible presenti | Non rieseguito in questo audit |
| Terraform AWS | `infrastructure/terraform/aws` | Presente; non applicato |
| Ansible | playbook locali presenti | Presente; non rieseguito |
| CI/CD GitHub Actions | workflow presenti | Presente; non rieseguito |
| AWS reale | EKS/RDS/ElastiCache/Amazon MQ come IaC | Non deployato |

## Scostamenti dal piano

- Il piano operativo iniziale partiva da 8-12 zone/poligoni; il progetto e' andato oltre, usando segmenti OSM per via.
- Lo stack frontend non usa React/Vite/Tailwind: usa HTML/CSS/JS vanilla + MapLibre, scelta piu semplice e coerente con il vincolo successivo "nessun framework".
- MongoDB resta fuori: Redis + PostGIS + RabbitMQ bastano per la demo e per i requisiti principali.
- Routing turn-by-turn reale resta fuori scope: c'e' simulazione e rete stradale, ma non calcolo percorso reale.
- AWS e CI/CD sono predisposti ma non provati con credenziali reali per evitare costi e side effect.

## Rischi residui

- Gli override strisce blu sono iniziali: servono campionamento manuale e fonti ufficiali piu complete per copertura legale/operativa.
- La prediction e' ancora rule-based: buona per demo, ma va calibrata con storico e metriche reali.
- Nemotron e ElevenLabs consumano crediti: restano on-demand/cache, ma vanno monitorati.
- La navigazione su rete OSM e' una demo: per produzione servono OSRM/Valhalla o TomTom Routing.
- Non esiste ancora una pipeline CI remota verificata end-to-end su GitHub Actions dopo questa evoluzione.
