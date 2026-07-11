# ParcheggIA

ParcheggIA e' una demo cloud-native per stimare la probabilita' di trovare parcheggio nelle immediate vicinanze dell'utente a Catania.

L'app mostra una interfaccia tipo navigatore: mappa MapLibre, heatmap continua sui tratti stradali, marker con percentuale e tipo sosta, suggerimenti AI, TTS e simulazione di guida. Il backend e' composto da microservizi, PostgreSQL/PostGIS, Redis e RabbitMQ. La stessa app gira in tre modalita':

- locale con Docker Compose;
- Kubernetes locale con k3d, per simulare l'architettura cloud;
- AWS con EKS, RDS, ElastiCache, Amazon MQ, ECR, Terraform e script di spegnimento.

Non servono API key per provare il progetto: in assenza di TomTom, Nemotron ed ElevenLabs l'app usa segmenti OSM reali, prediction simulate, suggerimenti simulati e TTS del browser.

## Avvio rapido

Prerequisiti minimi:

- Docker o runtime Docker-compatible attivo;
- Git;
- shell Unix/macOS/Linux;
- circa 4-8 GB liberi per immagini, database e servizi.

Clone e avvio locale:

```bash
git clone https://github.com/AlbertoBocchieri/Progetto-Sistemi-Cloud.git
cd Progetto-Sistemi-Cloud
docker compose up -d --build
```

Apri:

```text
http://localhost:8080
```

Verifica:

```bash
docker compose ps
scripts/smoke_test.sh
scripts/e2e_demo_test.sh
```

Spegnimento:

```bash
docker compose down
```

Reset completo, inclusi dati PostgreSQL:

```bash
docker compose down -v
```

## Simulazione architettura cloud in locale

Questa modalita' serve per mostrare la stessa architettura a microservizi su Kubernetes senza creare risorse cloud.

Prerequisiti:

```bash
brew install colima k3d kubernetes-cli helm
```

Avvio Colima se serve:

```bash
scripts/colima_start.sh
```

Avvio simulazione cloud locale:

```bash
scripts/cloud_sim_local_up.sh
```

Lo script:

- crea o riusa il cluster k3d `parcheggia`;
- forza il context kubectl su `k3d-parcheggia`;
- builda le immagini Docker;
- importa le immagini nel cluster;
- deploya PostgreSQL/PostGIS, Redis, RabbitMQ e microservizi;
- importa segmenti OSM reali e override strisce blu;
- esegue smoke test automatico;
- apre il frontend su:

```text
http://localhost:18080
```

Il terminale deve restare aperto per mantenere i port-forward.

Stop:

```bash
scripts/cloud_sim_local_down.sh
```

Mapping simulazione -> AWS:

| k3d locale | AWS reale |
|---|---|
| Deployment Kubernetes | EKS |
| Pod PostgreSQL/PostGIS | RDS PostgreSQL |
| Pod Redis | ElastiCache Redis |
| Pod RabbitMQ | Amazon MQ for RabbitMQ |
| immagini Docker importate in k3d | ECR |
| port-forward locale | Load Balancer AWS |

## Deploy cloud reale

La repo contiene Terraform e script per accendere una demo cloud reale.

Attenzione: senza API key esterne non consumi TomTom/Nemotron/ElevenLabs, ma AWS crea risorse a costo continuo: EKS, nodi EC2, RDS, ElastiCache, Amazon MQ e Load Balancer. Usare solo per demo brevi e spegnere subito.

Prerequisiti:

- account AWS configurato;
- AWS CLI autenticata;
- Terraform;
- kubectl;
- Docker runtime;
- permessi per EKS, EC2/VPC, ECR, RDS, ElastiCache, Amazon MQ, SSM, CloudWatch, Lambda/EventBridge se usi auto-spegnimento.

Setup iniziale:

```bash
export AWS_PROFILE=parcheggia-dev
export AWS_REGION=eu-south-1
scripts/terraform_backend_bootstrap.sh
terraform -chdir=infrastructure/terraform/aws init -migrate-state
scripts/aws_ssm_sync_env.sh
```

`aws_ssm_sync_env.sh` genera o mantiene:

```text
/parcheggia/dev/secrets/postgres-password
/parcheggia/dev/secrets/rabbitmq-password
```

Le API key esterne sono opzionali:

```text
/parcheggia/dev/secrets/tomtom-api-key
/parcheggia/dev/secrets/nemotron-api-key
/parcheggia/dev/secrets/elevenlabs-api-key
```

Accensione demo cloud:

```bash
CONFIRM_APPLY=apply-parcheggia-dev scripts/cloud_demo_up.sh
```

Lo script:

1. abilita `enable_cloud_stack=true`;
2. esegue Terraform;
3. crea/usa ECR;
4. builda e pusha immagini;
5. aggiorna kubeconfig EKS;
6. crea ConfigMap/Secret Kubernetes da Terraform output + SSM;
7. applica `infrastructure/k8s/cloud-demo.yaml`;
8. importa OSM su RDS;
9. attende rollout;
10. stampa URL del Load Balancer;
11. programma auto-spegnimento, default 4 ore.

Spegnimento obbligatorio:

```bash
CONFIRM_DESTROY=destroy-parcheggia-dev scripts/cloud_down.sh
```

Nota per account AWS diversi: `infrastructure/terraform/aws/backend.tf` punta a uno state S3 specifico. Su un altro account bisogna creare il bucket con `scripts/terraform_backend_bootstrap.sh` e usare un backend coerente con quell'account.

## Cosa funziona senza API key

La demo e' progettata per funzionare dopo un clone pulito.

| Funzione | Senza API key | Con API key |
|---|---|---|
| Segmenti stradali | OSM Catania reali importati da `data/osm/catania_segments.sql` | uguale |
| Tipo sosta | override locali AMTS/Comune + inferenza `probable_free` | uguale |
| Prediction | modello locale simulato e deterministico | arricchito da TomTom Traffic |
| Heatmap | segmenti reali + stime locali | segmenti reali + segnali TomTom/report |
| Suggerimenti | `nemotron-service` in `simulated-fallback` | Nemotron live se configurato |
| TTS | Web Speech API del browser | ElevenLabs se configurato |
| POI parcheggi | ricerca live disattivata, UI comunque funzionante | TomTom Search API |

Controllo rapido modalita' AI:

```bash
curl http://localhost:8000/ai/ready
```

Senza key deve restituire una risposta simile:

```json
{"status":"ready","mode":"simulated-fallback","model":"nvidia/nemotron-3-nano-30b-a3b"}
```

## Architettura generale

```text
Browser
  |
  | http://localhost:8080
  v
Frontend statico nginx
  - MapLibre GL JS
  - PMTiles/Protomaps locale Catania
  - Heatmap, marker, HUD, TTS browser
  |
  | HTTP verso API Gateway
  v
API Gateway nginx :8000
  |
  +--> Zone Service :8001 --------> PostgreSQL/PostGIS
  |         |                         - parking_segments
  |         |                         - road_edges / road_nodes
  |         |                         - parking_lots
  |         |                         - segment_reports
  |         +----------------------> Redis
  |                                   - segment:signals:*
  |                                   - raw_events
  |
  +--> Prediction Service :8004 ---> PostgreSQL/PostGIS
  |         +----------------------> Redis cache/segnali
  |
  +--> Location Service :8005 -----> Redis live_session:*
  |         +----------------------> RabbitMQ user.location.updated
  |         +----------------------> Zone + Prediction Service
  |
  +--> Ingestion Service :8002 ----> RabbitMQ parcheggia.events
  |         +----------------------> Redis budget/cache TomTom
  |         +----------------------> TomTom, solo se key presente
  |
  +--> Admin Service :8006 --------> Redis + RabbitMQ + Zone Service
  |
  +--> Nemotron Service :8003 -----> Nemotron/ElevenLabs, solo se key presenti
            +---------------------> fallback simulato + TTS browser lato frontend

RabbitMQ parcheggia.events
  -> Zone Service consumer
  -> Redis segment:signals:*
  -> invalidazione cache prediction/heatmap
```

Il gateway e' il punto di ingresso pubblico. I microservizi comunicano tra loro tramite HTTP interno, Redis e RabbitMQ. PostgreSQL/PostGIS contiene i dati geospaziali; Redis contiene stato live, cache e segnali temporanei; RabbitMQ trasporta eventi asincroni.

## Stack tecnologico

| Area | Tecnologia | Uso |
|---|---|---|
| Frontend | HTML, CSS, JavaScript vanilla | GUI drive-style senza framework React/Vue |
| Mappa | MapLibre GL JS | rendering WebGL, camera pitch/bearing, layer heatmap/linee/marker |
| Basemap | PMTiles/Protomaps | mappa vettoriale locale Catania in `frontend/assets/catania.pmtiles` |
| Gateway | nginx | reverse proxy e CORS verso microservizi |
| Backend | FastAPI + Python | API microservizi |
| Database | PostgreSQL + PostGIS | segmenti, rete stradale, report, parcheggi |
| Cache/stato | Redis | sessioni live, cache prediction, segnali, budget TomTom |
| Messaging | RabbitMQ | eventi asincroni demo e segnali traffico/report |
| AI | Nemotron API compatibile OpenAI | suggerimenti live opzionali |
| TTS | ElevenLabs + Web Speech API | voce naturale opzionale, fallback browser |
| Container | Docker Compose | esecuzione locale completa |
| Kubernetes locale | k3d/k3s | simulazione cloud locale |
| Cloud | AWS EKS, ECR, RDS, ElastiCache, Amazon MQ | deploy cloud gestito |
| IaC | Terraform | provisioning AWS |
| Automazione | shell script + GitHub Actions | build, deploy, smoke, spegnimento |

## Servizi locali

| Servizio | Porta | Ruolo | Dipendenze principali |
|---|---:|---|---|
| `frontend` | `8080` | UI MapLibre/HUD | API Gateway |
| `api-gateway` | `8000` | contratto pubblico HTTP | tutti i servizi app |
| `zone-service` | `8001` | segmenti, road network, report, consumer eventi | PostGIS, Redis, RabbitMQ |
| `ingestion-service` | `8002` | scenari demo, TomTom probe/publish/POI | RabbitMQ, Redis, TomTom opzionale |
| `nemotron-service` | `8003` | suggerimenti AI e TTS | Nemotron/ElevenLabs opzionali |
| `prediction-service` | `8004` | prediction segment-level e heatmap | PostGIS, Redis |
| `location-service` | `8005` | live session e posizione utente | Redis, RabbitMQ, Zone, Prediction |
| `admin-service` | `8006` | dashboard admin, eventi, source health | Redis, RabbitMQ, Zone |
| `postgres` | `5432` | PostgreSQL/PostGIS | volume `postgres_data` |
| `redis` | `6379` | cache/stato | nessuna |
| `rabbitmq` | `5672`, `15672` | broker eventi + UI management | nessuna |

Endpoint utili:

```text
Frontend                  http://localhost:8080
Gateway pubblico           http://localhost:8000/api/v1
Zone docs                  http://localhost:8001/docs
Ingestion docs             http://localhost:8002/docs
Nemotron docs              http://localhost:8003/docs
Prediction docs            http://localhost:8004/docs
Location docs              http://localhost:8005/docs
Admin docs                 http://localhost:8006/docs
RabbitMQ management        http://localhost:15672
RabbitMQ login             parcheggia / parcheggia
```

## Frontend

Il frontend e' statico e viene servito da nginx. Non contiene segreti e non chiama mai direttamente TomTom, Nemotron o ElevenLabs.

Funzioni principali:

- mappa MapLibre full-screen con camera ravvicinata, pitch e bearing;
- basemap vettoriale locale Catania via PMTiles;
- heatmap continua sui segmenti stradali vicini;
- marker segmento con bordo colorato in base al tipo di sosta e percentuale al centro;
- marker parcheggi/POI con animazione;
- click-to-drive sulla rete stradale;
- simulazione guida demo;
- bottom sheet parcheggi/preferiti/settings;
- tema chiaro/scuro;
- suggerimento automatico quando cambia segmento o percentuale;
- TTS mutabile dal pulsante volume.

Il frontend usa solo queste API interne:

```http
GET  /api/v1/segments/current
GET  /api/v1/segments/nearby
GET  /api/v1/road-network
GET  /api/v1/segment-heatmap
GET  /api/v1/tomtom/parking-pois
POST /api/v1/live-sessions/start
POST /api/v1/live-sessions/{id}/location
POST /api/v1/segment-reports
POST /ingestion/traffic/tomtom/publish
POST /ai/explain
POST /ai/tts
```

## Backend e responsabilita'

### API Gateway

`api-gateway` e' nginx. Espone una superficie unica su `localhost:8000` e instrada:

- `/api/v1/admin` -> `admin-service`;
- `/api/v1/live-sessions` -> `location-service`;
- `/api/v1/predictions` -> `prediction-service`;
- `/api/v1/segment-heatmap` -> `prediction-service`;
- `/api/v1/tomtom/*` -> `ingestion-service`;
- `/api/v1/*` generico -> `zone-service`;
- `/ingestion/*` -> `ingestion-service`;
- `/ai/*` -> `nemotron-service`.

### Zone Service

Gestisce il dominio geospaziale:

- segmenti stradali di parcheggio (`parking_segments`);
- rete di navigazione OSM (`road_edges`, `road_nodes`);
- parcheggi associati (`parking_lots`);
- report utente (`segment_reports`);
- consumer RabbitMQ per eventi traffico/citta/report;
- scrittura segnali temporanei in Redis (`segment:signals:*`);
- endpoint legacy `zones` ancora presenti per compatibilita'.

### Prediction Service

Calcola stime per singolo segmento e heatmap:

- parte da baseline per `parking_type`;
- applica correzioni da report recenti;
- applica segnali Redis da scenari demo o TomTom;
- considera fascia oraria/giorno;
- restituisce percentuale, confidence, status, trend e tempo stimato.

Stati visivi usati dalla UI:

```text
< 20%     molto difficile
20-39%    difficile
40-59%    incerto
60-79%    buono
>= 80%    favorevole
```

### Location Service

Gestisce la sessione live:

- crea `session_id` anonimo;
- salva posizione corrente in Redis;
- chiede a Zone Service il segmento corrente e i vicini;
- chiede a Prediction Service la prediction;
- pubblica `user.location.updated` su RabbitMQ;
- restituisce al frontend `current_segment`, `prediction`, `nearby_segments`.

### Ingestion Service

Inietta segnali esterni o sintetici:

- scenari demo (`/ingestion/scenarios/{id}/start`);
- TomTom Traffic Flow/Incidents tramite `/ingestion/traffic/tomtom/publish`;
- TomTom Search per parcheggi tramite `/api/v1/tomtom/parking-pois`;
- budget guard su Redis per non consumare troppe chiamate;
- cache TomTom per cella geografica.

Senza `TOMTOM_API_KEY`, gli endpoint TomTom non consumano nulla e la GUI resta su fallback/simulazioni.

### Admin Service

Espone:

- health delle fonti;
- eventi recenti;
- reset scenari demo;
- dashboard amministrativa minima.

### Nemotron Service

Genera suggerimenti e audio:

- con `NEMOTRON_API_KEY`, chiama `nvidia/nemotron-3-nano-30b-a3b`;
- senza key, ritorna `simulated-fallback`;
- con `ELEVENLABS_API_KEY`, genera audio ElevenLabs;
- senza ElevenLabs, il frontend usa la Web Speech API del browser.

## Modello dati

### PostgreSQL/PostGIS

Le tabelle principali sono:

| Tabella | Ruolo |
|---|---|
| `parking_segments` | entita' primaria: tratti stradali OSM fino a circa 120 m, con nome via, geometria LineString, tipo sosta, tariffa, fonte e confidence |
| `road_edges` | rete stradale OSM usata per snap/click-to-drive e navigazione demo |
| `road_nodes` | nodi/intersezioni della rete stradale |
| `parking_lots` | parcheggi strutturati/demo/POI collegati al segmento piu' vicino |
| `segment_reports` | segnalazioni utente segment-level |
| `zones` | zone legacy/demo ancora mantenute per compatibilita' e scenari |
| `user_reports` | report legacy zone-level |

`parking_segments.parking_type` usa valori come:

```text
blue           strisce blu / sosta tariffata nota
probable_free  probabile sosta libera, inferita
restricted     sosta limitata o critica
unknown        informazione non sufficiente
```

I dati OSM reali sono gia' versionati in:

```text
data/osm/catania_segments.sql
data/osm/catania_blue_overrides.sql
```

### Redis

Chiavi rilevanti:

| Pattern | Contenuto |
|---|---|
| `live_session:{session_id}` | posizione e stato sessione live |
| `segment:signals:{segment_id}` | segnali traffico/evento/report applicati al segmento |
| `segment-heatmap:{hash}` | cache heatmap |
| `prediction:{...}` | cache prediction |
| `rate_limit:report:{session_id}` | anti-spam report |
| `tomtom:budget:{month}:{service}` | contatori quota TomTom |
| `tomtom:estimate:{cell}:{radius}` | cache stima TomTom |
| `tomtom:parking-pois:{cell}:{radius}:{limit}` | cache POI parcheggi |
| `raw_events` | ultimi eventi consumati |

### RabbitMQ

Exchange:

```text
parcheggia.events
```

Eventi principali:

```text
traffic.snapshot.received
parkinglot.availability.updated
city.event.created
user.location.updated
user.report.created
```

Consumer principale:

```text
zone-service.events
```

## Flusso pratico: dal click sulla strada al suggerimento parlato

Esempio: l'utente apre la GUI e clicca su una strada vicina.

1. Il browser mostra la mappa MapLibre e ha gia' una sessione live creata con:

   ```http
   POST /api/v1/live-sessions/start
   ```

2. Il click viene snappato alla rete `road_edges` caricata da:

   ```http
   GET /api/v1/road-network?lat=...&lon=...&radius_m=700
   ```

3. Il frontend aggiorna la posizione e chiama:

   ```http
   POST /api/v1/live-sessions/{session_id}/location
   ```

4. API Gateway inoltra la richiesta al Location Service.

5. Location Service salva lo stato in Redis:

   ```text
   live_session:{session_id}
   ```

6. Location Service chiede al Zone Service il segmento corrente:

   ```http
   GET /segments/current?lat=...&lon=...
   GET /segments/nearby?lat=...&lon=...&radius_m=500
   ```

7. Zone Service interroga PostgreSQL/PostGIS:

   ```sql
   SELECT ...
   FROM parking_segments
   ORDER BY ST_Distance(geometry::geography, point::geography)
   ```

8. Location Service chiede al Prediction Service la stima del segmento.

9. Prediction Service combina:

   - baseline per `parking_type`;
   - report recenti da `segment_reports`;
   - segnali Redis `segment:signals:*`;
   - ora/giorno;
   - eventuale pressione TomTom se disponibile.

10. La risposta torna al frontend con:

    ```text
    current_segment
    prediction
    nearby_segments
    ```

11. Il frontend aggiorna:

    - chip centrale con via e percentuale;
    - marker segmenti;
    - heatmap MapLibre;
    - bottom sheet parcheggi;
    - eventuali target evidenziati.

12. Se il segmento/percentuale cambia, il frontend invia contesto a:

    ```http
    POST /ai/explain
    ```

13. Nemotron Service:

    - usa Nemotron live se `NEMOTRON_API_KEY` esiste;
    - altrimenti produce un suggerimento simulato coerente con i segmenti vicini.

14. Per la voce:

    ```http
    POST /ai/tts
    ```

    - se ElevenLabs e' configurato, torna audio;
    - se non e' configurato, il frontend usa `window.speechSynthesis`.

Il dato parte quindi da geometrie OSM/PostGIS e segnali Redis, passa dai microservizi via HTTP/RabbitMQ, e arriva alla GUI come colore, percentuale, suggerimento e voce.

## Flusso offline: da OSM alla GUI

1. `scripts/import_osm_segments.py` genera `data/osm/catania_segments.sql` da dati OSM/Overpass.
2. Il file crea o aggiorna:

   ```text
   road_nodes
   road_edges
   parking_segments
   ```

3. `data/osm/catania_blue_overrides.sql` applica override locali per strisce blu/tariffe.
4. In Docker Compose, `db-init` esegue:

   ```text
   services/zone-service/migrations/001_create_zones.sql
   data/osm/catania_segments.sql
   data/osm/catania_blue_overrides.sql
   ```

5. In Kubernetes locale, `scripts/k8s_import_osm_local.sh` importa gli stessi file nel pod PostgreSQL.
6. In AWS, `scripts/k8s_import_osm_cloud.sh` importa gli stessi file su RDS.
7. Zone Service legge PostGIS e serve segmenti/road network.
8. Prediction Service costruisce stime e heatmap.
9. MapLibre mostra marker e ribbon heatmap sui tratti reali.

## TomTom parsimonioso

La key TomTom resta backend-only. Non viene mai esposta in `frontend/app.js`, HTML o CSS.

Endpoint:

```http
GET  /ingestion/traffic/tomtom/probe?lat=37.507&lon=15.083&radius_m=500
POST /ingestion/traffic/tomtom/publish
GET  /api/v1/tomtom/parking-pois?lat=37.507&lon=15.083&radius_m=500
GET  /ingestion/traffic/tomtom/budget
```

Politica di consumo:

- raggio operativo: 500 m;
- cache prediction per cella circa 250 m;
- TTL stima traffico: 5 minuti;
- POI parcheggi: cache piu' lunga, perche' cambiano raramente;
- budget test default: 5% delle quote mensili;
- nessuna chiamata TomTom per ogni pressione tasto o ogni frame della simulazione;
- nessuna chiamata TomTom se `TOMTOM_API_KEY` e' vuota.

Con `.env` locale:

```bash
TOMTOM_API_KEY=...
TOMTOM_BUDGET_FRACTION=0.05
```

## Nemotron ed ElevenLabs

Configurazione opzionale `.env`:

```bash
NEMOTRON_API_KEY=...
NEMOTRON_BASE_URL=https://integrate.api.nvidia.com/v1
NEMOTRON_MODEL=nvidia/nemotron-3-nano-30b-a3b
NEMOTRON_TIMEOUT_SECONDS=45
NEMOTRON_CACHE_TTL_SECONDS=600

ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
ELEVENLABS_SIMILARITY_BOOST=0.50
ELEVENLABS_STYLE_EXAGGERATION=0.25
```

Comportamento:

- `/ai/explain` genera suggerimenti brevi e target evidenziabili;
- `/ai/tts` genera audio se ElevenLabs e' disponibile;
- se Nemotron manca, la modalita' e' `simulated-fallback`;
- se ElevenLabs manca, il browser legge il testo con Web Speech API.

## API principali

Base pubblica:

```text
http://localhost:8000/api/v1
```

Endpoint principali:

```http
GET  /health
GET  /ready
GET  /metrics

GET  /segments
GET  /segments/current?lat=37.507&lon=15.083
GET  /segments/nearby?lat=37.507&lon=15.083&radius_m=500
GET  /segments/{segment_id}
GET  /segments/{segment_id}/prediction
GET  /segment-heatmap?bbox=15.073,37.500,15.093,37.516&zoom=18
GET  /road-network?lat=37.507&lon=15.083&radius_m=700

POST /live-sessions/start
POST /live-sessions/{session_id}/location
GET  /live-sessions/{session_id}/nearby-segments
POST /live-sessions/{session_id}/stop

POST /segment-reports
POST /predictions
GET  /predictions/{prediction_id}

GET  /tomtom/parking-pois?lat=37.507&lon=15.083&radius_m=500

GET  /admin/source-health
GET  /admin/events
POST /admin/demo-scenarios/reset
```

Endpoint fuori da `/api/v1`:

```http
GET  /ingestion/scenarios
POST /ingestion/scenarios/{scenario_id}/start
GET  /ingestion/traffic/tomtom/budget
POST /ingestion/traffic/tomtom/publish
GET  /ai/ready
POST /ai/explain
POST /ai/tts
```

## Uso della GUI

1. Apri `http://localhost:8080`.
2. Consenti la posizione se vuoi usare il GPS browser; in alternativa usa click o simulazione.
3. Clicca su una strada per spostare l'utente nella demo desktop.
4. Guarda il marker del segmento:

   - bordo blu/colore sosta;
   - percentuale al centro;
   - heatmap attorno ai tratti vicini.

5. Apri `Parcheggi` per vedere segmenti e parcheggi vicini.
6. Usa `Settings` per tema, TTS, stato TomTom/AI.
7. Avvia `Simula guida 500 m` per mostrare un percorso demo.
8. Quando arriva un suggerimento, la card scende dall'alto e il TTS lo legge se non e' mutato.

## Test e quality gate

Controlli statici:

```bash
scripts/static_checks.sh
```

Smoke test con Docker Compose acceso:

```bash
scripts/smoke_test.sh
```

E2E demo:

```bash
scripts/e2e_demo_test.sh
```

Load test leggero:

```bash
ITERATIONS=30 scripts/load_test.sh
```

Gate completo:

```bash
scripts/run_checks.sh
```

Kubernetes smoke:

```bash
scripts/k8s_smoke_test.sh
```

## GitHub Actions

Workflow principali:

- build immagini Docker;
- check statici;
- Terraform plan/apply manuale;
- deploy EKS manuale;
- cloud down manuale.

I workflow cloud richiedono secrets AWS nel repository GitHub:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
PARCHEGGIA_DB_PASSWORD
PARCHEGGIA_MQ_PASSWORD
PARCHEGGIA_ECR_BASE
```

Le API key TomTom/Nemotron/ElevenLabs non sono obbligatorie per dimostrare il progetto.

## Troubleshooting

### Il primo avvio e' lento

Il primo `docker compose up -d --build` importa oltre 14.000 segmenti OSM, oltre 24.000 road edges e applica override strisce blu. Attendi che `db-init` termini:

```bash
docker compose ps
docker compose logs db-init
```

### La GUI e' vuota o vecchia

Fai hard refresh del browser:

```text
Cmd+Shift+R su macOS
Ctrl+Shift+R su Windows/Linux
```

Verifica che il frontend serva la versione corrente:

```bash
curl -fsS http://localhost:8080 | grep app.js
```

### Una porta e' occupata

Le porte usate da Docker Compose sono:

```text
5432, 6379, 5672, 15672, 8000-8006, 8080
```

Trova il processo:

```bash
lsof -i :8080
```

Oppure spegni lo stack:

```bash
docker compose down
```

### Un servizio non e' healthy

Controlla:

```bash
docker compose ps
docker compose logs <servizio>
```

Esempio:

```bash
docker compose logs zone-service
```

### Controllare AI fallback

```bash
curl http://localhost:8000/ai/ready
```

Senza key deve indicare `simulated-fallback`.

### Controllare TomTom budget

```bash
curl http://localhost:8000/ingestion/traffic/tomtom/budget
```

Senza key non vengono fatte chiamate reali.

### RabbitMQ management

```text
http://localhost:15672
user: parcheggia
pass: parcheggia
```

### Reset totale dei dati locali

```bash
docker compose down -v
docker compose up -d --build
```

## Struttura repo

```text
frontend/                         GUI MapLibre
services/api-gateway/             nginx gateway
services/zone-service/            geospaziale, segmenti, report, consumer eventi
services/prediction-service/      scoring e heatmap
services/location-service/        sessioni live
services/ingestion-service/       scenari demo e TomTom
services/admin-service/           admin/source health/eventi
services/nemotron-service/        suggerimenti AI e TTS
data/osm/                         SQL segmenti OSM e override
data/parking_overrides/           CSV strisce blu
infrastructure/k8s/               manifest Kubernetes locale/cloud
infrastructure/terraform/aws/     IaC AWS
infrastructure/ansible/           playbook didattici locali
scripts/                          automazioni operative
docs/                             documentazione di approfondimento
```

## Documentazione di approfondimento

- [Architettura](docs/architecture.md)
- [API](docs/api-spec.md)
- [Data model](docs/data-model.md)
- [Event flow](docs/event-flow.md)
- [Deployment view](docs/deployment-view.md)
- [Kubernetes locale](docs/kubernetes-local.md)
- [Cloud deployment](docs/cloud-deployment.md)
- [IaC e AWS](docs/iac-aws.md)
- [Test plan](docs/test-plan.md)
- [Privacy](docs/privacy.md)
- [Verification matrix](docs/verification-matrix.md)
- [Demo script](docs/demo-script.md)
- [Outline presentazione](docs/professor-presentation-outline.md)

## Stato del progetto

Implementato:

- GUI MapLibre Android-Auto style;
- segmenti OSM reali Catania;
- override strisce blu;
- prediction segment-level;
- heatmap continua;
- click-to-drive e simulazione guida;
- suggerimenti AI simulati/live;
- TTS browser/ElevenLabs;
- microservizi Docker Compose;
- simulazione cloud locale k3d;
- Terraform AWS;
- deploy EKS/RDS/ElastiCache/Amazon MQ/ECR;
- auto-spegnimento cloud;
- test statici, smoke ed E2E.

Limiti noti:

- routing reale non e' ancora implementato: la demo usa movimento/snapping e percorsi simulati;
- TomTom Parking Availability non e' incluso nel piano usato: Search trova POI parcheggi, non posti live;
- i suggerimenti senza API key sono simulati, non generati da Nemotron live;
- AWS reale genera costi: usare solo per demo brevi e spegnere sempre.
