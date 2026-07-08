#!/usr/bin/env sh
set -eu

API_URL="${1:-http://localhost:8000/api/v1}"
ITERATIONS="${ITERATIONS:-30}"
SEGMENT_ID="$(
  curl -fsS "$API_URL/segments/current?lat=37.507&lon=15.083" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
)"

i=1
while [ "$i" -le "$ITERATIONS" ]; do
  curl -fsS "$API_URL/ready" >/dev/null
  curl -fsS "$API_URL/segments/$SEGMENT_ID/prediction" >/dev/null
  curl -fsS "$API_URL/segment-heatmap" >/dev/null
  i=$((i + 1))
done

echo "Load test OK: ${ITERATIONS} iterations"
