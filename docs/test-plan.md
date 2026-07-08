# Test Plan

## Gate Locale

```bash
scripts/run_checks.sh
```

Copre:

- compilazione Python;
- validazione scenari sintetici;
- validazione contratti OpenAPI/schema;
- `docker compose config`;
- readiness API;
- readiness prediction-service e location-service;
- readiness admin-service;
- validazione manifest Kubernetes offline quando `kubeconform` e' installato;
- metriche `/metrics`;
- request id e log JSON applicativi;
- query PostGIS;
- seed parcheggi e associazione zona;
- nearby zones;
- heatmap;
- live session;
- ingestion-service;
- RabbitMQ consumer;
- Redis update/cache;
- Nemotron fallback;
- dashboard admin servita dal frontend.
- rate limit report per sessione.

## Gate Statico

```bash
scripts/static_checks.sh
```

Copre senza avviare container:

- compilazione Python;
- unit check scoring;
- audit struttura requisiti;
- validazione scenari sintetici;
- validazione contratti OpenAPI/schema;
- validazione statica frontend/UX;
- validazione manifest Kubernetes con `kubeconform`;
- validazione Terraform quando inizializzato;
- syntax-check Ansible;
- parse workflow GitHub Actions.

## Smoke Test

```bash
scripts/smoke_test.sh
```

Esegue il flusso minimo end-to-end con i container avviati.

## E2E Demo

```bash
scripts/e2e_demo_test.sh
```

Copre sessione, posizione Borgo/Cittadella, report, scenario ingestion, prediction e AI fallback.

## Load Test Base

```bash
ITERATIONS=30 scripts/load_test.sh
```

Esegue richieste ripetute su readiness, prediction e heatmap.

## Kubernetes Locale

```bash
scripts/colima_start.sh
scripts/k3d_prepare_local.sh
scripts/k8s_apply_local.sh
scripts/k8s_smoke_test.sh
k3d cluster delete parcheggia
colima stop
```

Copre deploy k3d, job `db-init`, rollout deployment, port-forward, smoke, E2E e load test base.

## CI

Workflow:

```text
.github/workflows/ci.yml
.github/workflows/docker-build.yml
.github/workflows/deploy-local.yml
.github/workflows/terraform-plan.yml
.github/workflows/terraform-apply.yml
.github/workflows/deploy-eks.yml
```

Su push/PR:

- compila Python;
- valida scenari;
- valida contratti;
- valida manifest Kubernetes;
- valida Compose;
- avvia Compose;
- esegue smoke test;
- esegue E2E demo;
- stampa log se fallisce.

## Test Manuale Demo

1. Aprire `http://localhost:8080`.
2. Cambiare posizione demo.
3. Avviare scenario `Evento serale centro storico`.
4. Verificare score peggiorato e ultimi eventi admin.
5. Cliccare `Spiegazione AI`.
6. Inviare `Zona piena` e verificare refresh.
