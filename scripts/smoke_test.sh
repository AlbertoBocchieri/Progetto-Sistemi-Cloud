#!/usr/bin/env sh
set -eu

API_URL="${1:-http://localhost:8000/api/v1}"
INGESTION_URL="${2:-http://localhost:8000/ingestion}"
AI_URL="${3:-http://localhost:8000}"
PREDICTION_URL="${4:-http://localhost:8004}"
LOCATION_URL="${5:-http://localhost:8005}"
ADMIN_URL="${6:-http://localhost:8006}"
NEMOTRON_URL="${7:-http://localhost:8003}"

curl -fsS "$API_URL/ready" >/dev/null
curl -fsS "$API_URL/metrics" | grep -q "parcheggia_http_requests_total"
curl -fsS "$INGESTION_URL/ready" >/dev/null
curl -fsS "$INGESTION_URL/traffic/tomtom/budget" | grep -q "traffic_flow"
curl -fsS "$AI_URL/ai/ready" >/dev/null
curl -fsS "$PREDICTION_URL/ready" >/dev/null
curl -fsS "$LOCATION_URL/ready" >/dev/null
curl -fsS "$ADMIN_URL/ready" >/dev/null
curl -fsS "$PREDICTION_URL/metrics" | grep -q "parcheggia_http_requests_total"
curl -fsS "$LOCATION_URL/metrics" | grep -q "parcheggia_http_requests_total"
curl -fsS "$ADMIN_URL/metrics" | grep -q "parcheggia_http_requests_total"
curl -fsS "$INGESTION_URL/metrics" | grep -q "parcheggia_http_requests_total"
curl -fsS "$NEMOTRON_URL/metrics" | grep -q "parcheggia_http_requests_total"
curl -fsS -X POST "$API_URL/admin/demo-scenarios/reset" | grep -q "reset"
curl -fsS "$API_URL/segments" | grep -q "Via Etnea"
SEGMENT_ID="$(
  curl -fsS "$API_URL/segments/current?lat=37.507&lon=15.083" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
)"
SCENARIO_SEGMENT_ID="$SEGMENT_ID"
curl -fsS "$API_URL/segments/$SEGMENT_ID" | grep -q "parking_lots"
TOMTOM_POIS_CODE="$(
  curl -sS -o /tmp/parcheggia-tomtom-parking-pois.txt -w "%{http_code}" \
    "$API_URL/tomtom/parking-pois"
)"
test "$TOMTOM_POIS_CODE" = "422"
curl -fsS "$API_URL/segments/current?lat=37.507&lon=15.083" | grep -q "street_name"
curl -fsS "$API_URL/segments/nearby?lat=37.507&lon=15.083&radius_m=500" | grep -q "distance_m"
curl -fsS "$API_URL/road-network?lat=37.507&lon=15.083&radius_m=700" | grep -q "edges"
curl -fsS "$API_URL/segments/$SEGMENT_ID/prediction" | grep -q "parkability_percent"
curl -fsS "$API_URL/segments/$SCENARIO_SEGMENT_ID/prediction" | grep -q "parkability_percent"
curl -fsS "$API_URL/segment-heatmap?bbox=15.073,37.500,15.093,37.516&zoom=18" | grep -q "heatmap_intensity"
SESSION_ID="$(
  curl -fsS -X POST "$API_URL/live-sessions/start" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["session_id"])'
)"
curl -fsS \
  -H "Content-Type: application/json" \
  -d '{"lat":37.507,"lon":15.083}' \
  "$API_URL/live-sessions/$SESSION_ID/location" | grep -q "nearby_segments"
curl -fsS \
  -X POST \
  "$INGESTION_URL/scenarios/via_etnea_evening_event/start" | grep -q "events_published"

SCENARIO_OK=0
for _ in 1 2 3 4 5; do
  if curl -fsS "$API_URL/segments/$SCENARIO_SEGMENT_ID/prediction" |
    grep -qi "scenario demo attivo"; then
    SCENARIO_OK=1
    break
  fi
  sleep 1
done

test "$SCENARIO_OK" -eq 1
curl -fsS "$API_URL/admin/events" | grep -q "traffic.snapshot.received"
curl -fsS "http://localhost:8080" | grep -q "Dashboard admin"
curl -fsS \
  -H "Content-Type: application/json" \
  -d '{"segment_id":"'"$SEGMENT_ID"'","segment_name":"Via Etnea","parkability_percent":28,"status":"difficult","trend":"worse","confidence":0.72,"estimated_search_time_min":22,"recommendation":"Tratto difficile"}' \
  "$AI_URL/ai/explain" | grep -q "model"
curl -fsS \
  -H "Content-Type: application/json" \
  -d '{"segment_id":"'"$SEGMENT_ID"'","report_type":"full_zone","session_id":"'"$SESSION_ID"'"}' \
  "$API_URL/segment-reports" | grep -q "accepted"
RATE_CODE="$(
  curl -sS -o /tmp/parcheggia-rate-limit.txt -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -d '{"segment_id":"'"$SEGMENT_ID"'","report_type":"full_zone","session_id":"'"$SESSION_ID"'"}' \
    "$API_URL/segment-reports"
)"
test "$RATE_CODE" = "429"
curl -fsS -X POST "$API_URL/live-sessions/$SESSION_ID/stop" | grep -q "stopped"

echo "Smoke test OK: $API_URL"
