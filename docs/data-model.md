# Data Model

## PostgreSQL/PostGIS

### `zones`

Contiene le zone urbane demo di Catania.

Campi principali:

- `id`: identificativo stabile della zona.
- `name`: nome mostrato in UI.
- `city`: citta.
- `zone_type`: categoria operativa.
- `baseline_capacity_estimate`: capacita stimata di base.
- `polygon`: geometria PostGIS `POLYGON, 4326`.
- `created_at`: timestamp di creazione.

Indice:

- `idx_zones_polygon` su `polygon` con GIST.

### `user_reports`

Contiene segnalazioni rapide della demo.

Campi:

- `id`: UUID testuale.
- `zone_id`: zona segnalata.
- `report_type`: `found_spot`, `full_zone`, `released_spot` o `parking_closed`.
- `session_id`: sessione anonima opzionale usata per rate limit breve.
- `created_at`: timestamp.

### `parking_lots`

Parcheggi demo associati alle zone.

Campi:

- `id`: identificativo stabile.
- `name`: nome mostrabile in UI/API.
- `operator`: gestore o fonte demo.
- `zone_id`: zona associata.
- `location`: punto PostGIS `POINT, 4326`.
- `total_capacity`: capacita stimata.
- `pricing_info`: metadati JSONB.
- `is_park_and_ride`: flag park-and-ride.

## Redis

Chiavi usate:

- `live_session:{session_id}`: stato sessione live.
- `zone:signals:{zone_id}`: ultimi segnali da ingestion/RabbitMQ.
- `prediction:{zone_id}:{hash}`: cache prediction.
- `heatmap:{hash}`: cache heatmap.
- `rate_limit:report:{session_id}`: anti-spam report con TTL 30 secondi.
- `raw_events`: ultimi eventi consumati.

## RabbitMQ

Exchange:

```text
parcheggia.events
```

Eventi attuali:

- `traffic.snapshot.received`
- `parkinglot.availability.updated`
- `city.event.created`
- `user.location.updated`
- `user.report.created`

Consumer:

- `zone-service.events`
