# Event Flow

## Radar Continuo

```text
Frontend
  -> POST /api/v1/live-sessions/start
  -> POST /api/v1/live-sessions/{id}/location
Location Service
  -> Zone Service: zona corrente e nearby zones
  -> Prediction Service: prediction zona corrente
  -> Redis: live_session:{id}
  -> RabbitMQ: user.location.updated
Frontend
  <- zona corrente, prediction, nearby zones
```

## Scenario Demo

```text
Frontend admin
  -> POST /ingestion/scenarios/{scenario_id}/start
Ingestion Service
  -> RabbitMQ: traffic.snapshot.received
  -> RabbitMQ: parkinglot.availability.updated
  -> RabbitMQ: city.event.created
Zone Service consumer
  -> Redis: zone:signals:{zone_id}
  -> Redis: raw_events
  -> Redis: invalidazione prediction/heatmap
Prediction Service
  -> legge Redis + user_reports
  -> aggiorna prediction e heatmap
```

## Report Utente

```text
Frontend
  -> POST /api/v1/reports
Zone Service
  -> PostgreSQL: user_reports
  -> Redis: rate_limit:report:{session_id}
  -> RabbitMQ: user.report.created
  -> Redis: invalidazione cache zona
Prediction Service
  -> include report recenti nello score
```
