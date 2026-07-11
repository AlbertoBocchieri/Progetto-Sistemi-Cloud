#!/usr/bin/env sh
set -eu

NAMESPACE="${NAMESPACE:-parcheggia}"
OSM_SQL="${OSM_SQL:-data/osm/catania_segments.sql}"
OVERRIDES_SQL="${OVERRIDES_SQL:-data/osm/catania_blue_overrides.sql}"

if [ ! -f "$OSM_SQL" ]; then
  echo "Missing $OSM_SQL" >&2
  exit 1
fi

POSTGRES_POD="$(
  kubectl -n "$NAMESPACE" get pod -l app=postgres \
    -o jsonpath='{.items[0].metadata.name}'
)"

psql_cmd='PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
osm_count="$(
  printf "%s\n" "SELECT COUNT(*) FROM parking_segments WHERE id LIKE 'ct-osm-%';" |
    kubectl -n "$NAMESPACE" exec -i "$POSTGRES_POD" -c postgres -- sh -c "$psql_cmd -tA" |
    tr -d '[:space:]'
)"

if [ "$osm_count" = "0" ]; then
  echo "Importing OSM Catania segments into Kubernetes Postgres..."
  kubectl -n "$NAMESPACE" exec -i "$POSTGRES_POD" -c postgres -- sh -c \
    'cat >/tmp/catania_segments.sql' < "$OSM_SQL"
  kubectl -n "$NAMESPACE" exec "$POSTGRES_POD" -c postgres -- sh -c \
    "$psql_cmd -f /tmp/catania_segments.sql"
else
  echo "OSM Catania segments already present: $osm_count"
fi

if [ -f "$OVERRIDES_SQL" ]; then
  echo "Applying parking overrides..."
  kubectl -n "$NAMESPACE" exec -i "$POSTGRES_POD" -c postgres -- sh -c \
    'cat >/tmp/catania_blue_overrides.sql' < "$OVERRIDES_SQL"
  kubectl -n "$NAMESPACE" exec "$POSTGRES_POD" -c postgres -- sh -c \
    "$psql_cmd -f /tmp/catania_blue_overrides.sql"
fi
