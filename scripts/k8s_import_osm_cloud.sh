#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-parcheggia}"
OSM_SQL="${OSM_SQL:-data/osm/catania_segments.sql}"
OVERRIDES_SQL="${OVERRIDES_SQL:-data/osm/catania_blue_overrides.sql}"

test -f "$OSM_SQL"
test -f "$OVERRIDES_SQL"

POSTGRES_HOST="$(kubectl -n "$NAMESPACE" get configmap parcheggia-runtime -o jsonpath='{.data.POSTGRES_HOST}')"
POSTGRES_PASSWORD="$(kubectl -n "$NAMESPACE" get secret parcheggia-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 --decode)"

cat "$OSM_SQL" "$OVERRIDES_SQL" | kubectl -n "$NAMESPACE" run psql-osm-import \
  --rm \
  -i \
  --restart=Never \
  --image=postgres:16-alpine \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  --command -- \
  psql -h "$POSTGRES_HOST" -U parcheggia -d parcheggia -v ON_ERROR_STOP=1
