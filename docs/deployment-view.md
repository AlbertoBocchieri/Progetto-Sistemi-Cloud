# Deployment View

## Locale Docker Compose

```text
frontend:8080
api-gateway:8000
zone-service:8001
ingestion-service:8002
nemotron-service:8003
prediction-service:8004
location-service:8005
admin-service:8006
postgres:5432
redis:6379
rabbitmq:5672,15672
```

Il gateway espone il contratto pubblico e instrada verso i servizi interni.

## Kubernetes Locale

Namespace: `parcheggia`.

Workload:

- Deployment: frontend, api-gateway, zone-service, location-service, prediction-service, admin-service, ingestion-service, nemotron-service.
- Deployment demo stateful: postgres, redis, rabbitmq.
- Job: db-init.
- Service ClusterIP per ogni workload.
- Ingress demo `parcheggia.local`.
- HPA per `prediction-service`.
- ConfigMap: migrazione SQL PostGIS.
- Secret: credenziali demo.

## AWS

Mapping previsto:

- EKS per workload Kubernetes.
- ECR per immagini.
- RDS PostgreSQL con PostGIS.
- ElastiCache Redis.
- Amazon MQ for RabbitMQ.
- CloudWatch per log.

Il Terraform e' protetto da `enable_cloud_stack=false` per evitare costi accidentali.
