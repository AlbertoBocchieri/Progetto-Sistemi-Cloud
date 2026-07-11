# Cloud Deployment

## Mappatura Locale -> AWS

| Locale | AWS |
|---|---|
| Docker Compose | EKS |
| PostgreSQL/PostGIS | RDS PostgreSQL |
| Redis | ElastiCache Redis |
| RabbitMQ | Amazon MQ for RabbitMQ |
| Immagini Docker | ECR |
| Log container | CloudWatch |
| CI locale | GitHub Actions |

## Simulazione Cloud Senza AWS

Per mostrare la stessa topologia a microservizi su Kubernetes senza creare risorse cloud:

```bash
scripts/cloud_sim_local_up.sh
```

Questa modalita' usa k3d come sostituto locale di EKS e container locali al posto dei servizi gestiti AWS:

| Simulazione k3d | Servizio AWS reale |
|---|---|
| Deployment Kubernetes | EKS |
| Pod PostgreSQL/PostGIS | RDS PostgreSQL |
| Pod Redis | ElastiCache Redis |
| Pod RabbitMQ | Amazon MQ for RabbitMQ |
| Immagini Docker locali importate in k3d | ECR |

Non servono API key: TomTom, Nemotron ed ElevenLabs restano spenti e la demo usa dati/suggerimenti/TTS simulati.

Spegnimento:

```bash
scripts/cloud_sim_local_down.sh
```

## Sequenza Consigliata

1. Validare demo locale:

```bash
scripts/run_checks.sh
```

2. Creare ECR/Terraform plan:

```bash
cd infrastructure/terraform/aws
terraform init
terraform plan
```

La configurazione include ECR, CloudWatch log group per servizio, VPC, EKS, RDS, ElastiCache e Amazon MQ.

3. Abilitare risorse a costo continuo solo esplicitamente, con password via variabili sensitive:

```hcl
enable_cloud_stack = true
db_password = "..."
mq_password = "..."
```

4. Build/push immagini su ECR.

```bash
scripts/aws_ecr_push.sh
```

`scripts/cloud_demo_up.sh` esegue automaticamente questo step dopo Terraform. Usa `PUSH_IMAGES=false` solo se le immagini sono gia' state pubblicate da CI/CD.

5. Applicare manifest Kubernetes cloud adattato agli endpoint gestiti AWS.

```bash
scripts/k8s_cloud_config_from_aws.sh
kubectl -n parcheggia create configmap zone-migrations \
  --from-file=001_create_zones.sql=services/zone-service/migrations/001_create_zones.sql \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f infrastructure/k8s/cloud-demo.yaml
```

6. Eseguire smoke test via port-forward o ingress.

## GitHub Actions Manuali

- `terraform-plan.yml`: validate/plan su PR e manuale.
- `terraform-apply.yml`: apply solo da `workflow_dispatch` e solo digitando `APPLY`.
- `docker-build.yml`: build immagini.
- `deploy-local.yml`: deploy k3d manuale e smoke Kubernetes.
- `deploy-eks.yml`: deploy manuale su EKS usando immagini ECR.

Secrets attesi per i workflow cloud:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
PARCHEGGIA_DB_PASSWORD
PARCHEGGIA_MQ_PASSWORD
PARCHEGGIA_ECR_BASE
```

`PARCHEGGIA_ECR_BASE` deve avere forma:

```text
<account>.dkr.ecr.<region>.amazonaws.com/parcheggia-dev
```

## Segreti AWS

Per la demo cloud usiamo Systems Manager Parameter Store standard sotto `/parcheggia/dev`.
I valori sensibili sono `SecureString`, le opzioni non sensibili sono `String`.
Le API key esterne sono opzionali: se TomTom, Nemotron o ElevenLabs non sono presenti in SSM, il Secret Kubernetes viene creato con valori vuoti e l'app usa fallback/simulazioni.

Caricamento da `.env` locale senza stampare i valori:

```bash
export AWS_PROFILE=parcheggia-dev
export AWS_REGION=eu-south-1
scripts/aws_ssm_sync_env.sh
```

Controllo metadata, senza mostrare i valori:

```bash
scripts/aws_ssm_check_config.sh
```

Parametri principali:

```text
/parcheggia/dev/secrets/postgres-password   obbligatorio, generato se assente
/parcheggia/dev/secrets/rabbitmq-password   obbligatorio, generato se assente
/parcheggia/dev/secrets/tomtom-api-key      opzionale
/parcheggia/dev/secrets/nemotron-api-key    opzionale
/parcheggia/dev/secrets/elevenlabs-api-key  opzionale
```

Per generare un Secret Kubernetes da SSM quando il cluster e' attivo:

```bash
scripts/k8s_secret_from_ssm.sh
```

Per generare ConfigMap e Secret completi per il deploy cloud, usando output Terraform e SSM:

```bash
scripts/k8s_cloud_config_from_aws.sh
```

Validazione locale del manifest cloud senza creare risorse:

```bash
scripts/k8s_cloud_dry_run.sh
```

Lo script usa sempre `kubeconform` offline. Se un cluster e' raggiungibile, esegue anche `kubectl apply --dry-run=client`.

## Cost Guardrails

- Ambiente unico `dev`.
- `enable_cloud_stack=false` di default.
- RDS/Redis/MQ con tag `Project=parcheggia`.
- Eseguire `terraform destroy` dopo la demo cloud.
