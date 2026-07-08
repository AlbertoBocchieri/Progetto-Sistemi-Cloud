# Presentation Outline

## 1. Problema

Trovare parcheggio in centro e in zone universitarie e' incerto, lento e dipende da segnali frammentati.

## 2. Idea

ParcheggIA e' un radar di parcheggiabilita: mentre l'utente si muove, mostra zone vicine, score, trend e tempo stimato.

## 3. Architettura

- Frontend statico.
- Zone service FastAPI.
- Prediction service FastAPI.
- Location service FastAPI.
- Admin service FastAPI.
- PostgreSQL/PostGIS.
- Redis.
- RabbitMQ.
- Ingestion service.
- Nemotron fallback service.
- Docker Compose.
- Kubernetes locale.
- Terraform/Ansible per cloud/IaC.

## 4. Demo

1. Aprire frontend.
2. Mostrare radar attivo.
3. Cambiare posizione.
4. Lanciare scenario RabbitMQ.
5. Mostrare score che cambia.
6. Mostrare dashboard admin.
7. Cliccare Spiegazione AI.
8. Eseguire smoke test.

## 5. Cloud

Mostrare mapping locale -> AWS:

- EKS;
- RDS;
- ElastiCache;
- Amazon MQ;
- ECR;
- GitHub Actions.

## 6. Limiti e sviluppi

- Aggiungere modello AI reale.
- Deploy AWS completo.
- Ingress e osservabilita avanzata.
