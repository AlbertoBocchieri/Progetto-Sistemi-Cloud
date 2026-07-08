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

5. Applicare manifest Kubernetes adattati agli endpoint gestiti AWS.

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

## Cost Guardrails

- Ambiente unico `dev`.
- `enable_cloud_stack=false` di default.
- RDS/Redis/MQ con tag `Project=parcheggia`.
- Eseguire `terraform destroy` dopo la demo cloud.
