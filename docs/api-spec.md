# API Demo

Base URL locale:

```text
http://localhost:8000/api/v1
```

Il gateway instrada zone/report al `zone-service`, prediction/heatmap al `prediction-service`, live session al `location-service` e admin all'`admin-service`.

## Health

```http
GET /health
GET /ready
GET /metrics
```

## Zone

```http
GET /zones
GET /zones/{zone_id}
GET /zones/current?lat=37.507&lon=15.083
GET /zones/nearby?lat=37.507&lon=15.083&radius_m=2200
```

Le risposte zona includono `parking_lots` con parcheggi demo associati.

## Live Session

```http
POST /live-sessions/start
POST /live-sessions/{session_id}/location
GET  /live-sessions/{session_id}/nearby-zones
POST /live-sessions/{session_id}/stop
```

Payload posizione:

```json
{
  "lat": 37.507,
  "lon": 15.083
}
```

## Prediction e Heatmap

```http
POST /predictions
GET /predictions/{prediction_id}
GET /zones/{zone_id}/prediction
GET /heatmap?bbox=15.06,37.49,15.12,37.54&zoom=14
```

## Report

```http
POST /reports
Content-Type: application/json

{
  "zone_id": "ct-via-etnea-stesicoro",
  "report_type": "full_zone",
  "session_id": "opzionale"
}
```

`report_type` accetta `found_spot`, `full_zone`, `released_spot` o `parking_closed`.

## Admin Demo

```http
GET  /admin/source-health
GET  /admin/events
POST /admin/demo-scenarios/reset
```

## Ingestion Service

Base URL locale:

```text
http://localhost:8000/ingestion
```

```http
GET  /health
GET  /ready
GET  /scenarios
POST /scenarios/{scenario_id}/start
```

Scenari disponibili:

- `cittadella_morning_peak`
- `via_etnea_evening_event`
- `sanzio_relief`

## Nemotron Service

Base URL locale:

```text
http://localhost:8000
```

```http
GET  /health
GET  /ready
POST /ai/explain
```

La demo usa `rule-based-fallback`; il servizio non inventa dati esterni.
