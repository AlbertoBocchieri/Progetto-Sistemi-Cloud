# Verification matrix

Audit del 2026-07-07 rispetto a:

- `/Users/albertobocchieri/Downloads/ParcheggIA_Piano_Operativo.md`
- `/Users/albertobocchieri/Downloads/StrutturaProgettoCloud.md`

## Gate eseguiti

Ultimo gate locale eseguito con stack Docker attivo:

```bash
scripts/run_checks.sh && ITERATIONS=30 scripts/load_test.sh
```

Esito:

```text
Scenario checks OK
Contract checks OK
Kubernetes manifest valid: 28 resources
Smoke test OK
E2E demo OK
All checks OK
Load test OK: 30 iterations
```

Validazioni aggiuntive gia' eseguite:

- `terraform -chdir=infrastructure/terraform/aws fmt -check -recursive`
- `terraform -chdir=infrastructure/terraform/aws validate`
- `ansible-playbook --syntax-check` sui playbook locali
- parse YAML dei workflow GitHub Actions e playbook Ansible
- `sh -n scripts/*.sh`
- scoring unit checks con `scripts/check_scoring.py`
- requirement structure audit con `scripts/audit_requirements.py`
- frontend static/UX contract checks con `scripts/check_frontend.py`
- static gate senza container con `scripts/static_checks.sh`
- deploy Kubernetes locale su `k3d` con runtime `colima`
- smoke/E2E/load via port-forward Kubernetes, codificato in `scripts/k8s_smoke_test.sh`
- workflow manuali `deploy-local.yml`, `terraform-apply.yml` e `deploy-eks.yml` validati come YAML
- script `scripts/aws_ecr_push.sh` validato con shell syntax

Toolchain verificata su macOS 15.7.7 Sequoia arm64:

- Docker CLI 29.6.1, Docker Compose v5.2.0
- Colima 0.10.3, Lima 2.1.4
- k3d 5.9.0, k3s 1.36.2
- kubectl 1.36.2, Helm 4.2.2
- Terraform 1.15.7
- Ansible 14.1.0 / ansible-core 2.21.1
- AWS CLI 2.35.16
- Python 3.14.6
- Node LTS 24.18.0 via nvm

## Requisiti prodotto

| Requisito | Evidenza repo | Stato |
|---|---|---|
| Live Radar | frontend, location-service, `/live-sessions/*` | OK, verificato da smoke/E2E |
| Heatmap | prediction-service `/heatmap`, frontend layer zone | OK, verificato da smoke/E2E |
| Zone Catania | PostGIS seed in `001_create_zones.sql` | OK |
| Top 3 zone vicine | `/nearby-zones`, frontend cards | OK |
| Segnalazioni rapide | `POST /reports`, 4 tipi report, rate limit 30s | OK |
| Dettaglio zona | `/zones/{id}` con predizione e parcheggi | OK |
| Ricerca destinazione opzionale | select destinazione nel frontend | OK per demo |
| Dashboard admin | admin-service + pannello frontend | OK |
| Demo mode | scenari sintetici e script E2E | OK |

## Requisiti backend e dati

| Requisito | Evidenza repo | Stato |
|---|---|---|
| API Gateway | nginx gateway su `8000` | OK |
| Zone Service | FastAPI + PostGIS | OK |
| Location Service | FastAPI + Redis + RabbitMQ | OK |
| Prediction Service | formula rule-based + Redis cache | OK |
| Ingestion Service | scenari sintetici + publish eventi | OK |
| Admin Service | health fonti, eventi, reset scenari | OK |
| Nemotron Service | fallback rule-based JSON | OK; modello reale non incluso |
| Health/ready/metrics | endpoint sui servizi | OK, verificato da smoke |
| OpenAPI e schema eventi | `shared/openapi`, `shared/schemas` | OK, verificato da contract check |
| PostgreSQL/PostGIS | compose + migrazioni | OK |
| Redis | compose + session/cache/rate limit | OK |
| RabbitMQ | compose + eventi applicativi | OK |
| MongoDB | opzionale nel piano | Non implementato, non richiesto come vincolo forte |
| Seed parcheggi | tabella `parking_lots` + dati demo | OK |
| Scenari sintetici | `data/synthetic/demo_scenarios.json` | OK |
| Raw events | tabella/eventi admin | OK per demo |

## Cloud e DevOps

| Requisito | Evidenza repo | Stato |
|---|---|---|
| Dockerfile servizi | frontend + servizi backend | OK |
| Docker Compose | `docker-compose.yml` | OK, verificato da `docker compose config` e smoke |
| Kubernetes manifest | `infrastructure/k8s/local-demo.yaml` | OK, validato con kubeconform |
| Multipass/k3s | playbook Multipass + fallback k3d | k3d verificato su Colima; Multipass richiede password admin nella sessione locale |
| Terraform AWS | `infrastructure/terraform/aws` | OK, `terraform validate` |
| Ansible locale | `infrastructure/ansible` | OK, syntax-check |
| ECR/EKS/RDS/ElastiCache/Amazon MQ | moduli/risorse Terraform | OK come IaC; non applicato senza credenziali AWS |
| GitHub Actions | `.github/workflows` | OK, workflow parse e comandi definiti |

## Test

| Requisito | Evidenza repo | Stato |
|---|---|---|
| Unit/contract checks | py_compile, scoring check, scenario check, contract check | OK per MVP |
| Integration test | smoke su compose con PostGIS/Redis/RabbitMQ | OK |
| E2E test | `scripts/e2e_demo_test.sh` | OK |
| Load test base | `scripts/load_test.sh` | OK, 30 iterazioni |
| Smoke Docker | `scripts/smoke_test.sh` | OK |
| Smoke Kubernetes | `scripts/k3d_prepare_local.sh`, `scripts/k8s_apply_local.sh`, port-forward | OK su k3d/Colima |
| Smoke AWS | Terraform validato | Non eseguito senza credenziali/costi AWS |
| Privacy | `docs/privacy.md`, session anonime, coordinate approssimate | OK per demo |
| UX | frontend mobile/statico, controlli grandi, demo senza GPS reale, static check | OK per demo; non Playwright visual |

## Limiti espliciti

- Nessun deploy AWS reale e nessuno smoke post-deploy cloud: richiedono credenziali, budget e una decisione esplicita sul ciclo `terraform apply/destroy`.
- La repo ora contiene workflow manuali per `terraform apply`, push ECR e deploy EKS; non sono stati eseguiti per assenza di credenziali AWS.
- Nemotron reale non e' invocato: il servizio produce fallback rule-based coerente e testabile.
- Multipass 1.16.3 e' disponibile per Sequoia, ma l'installer richiede password admin e non puo' essere completato in questa shell non interattiva.
- Docker Desktop 4.81.0 e' installato, ma il primo avvio post-update richiede privilegi amministratore GUI per configurare port mapping/socket. I gate runtime sono stati eseguiti con Colima.
- Il load test e' volutamente base: misura stabilita' dello scenario demo, non capacita' produttiva.
