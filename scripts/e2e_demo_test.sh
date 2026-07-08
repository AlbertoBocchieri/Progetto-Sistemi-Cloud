#!/usr/bin/env sh
set -eu

API_URL="${1:-http://localhost:8000/api/v1}"
INGESTION_URL="${2:-http://localhost:8000/ingestion}"
AI_URL="${3:-http://localhost:8000}"

SESSION_ID="$(
  curl -fsS -X POST "$API_URL/live-sessions/start" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["session_id"])'
)"

curl -fsS \
  -H "Content-Type: application/json" \
  -d '{"lat":37.525,"lon":15.071}' \
  "$API_URL/live-sessions/$SESSION_ID/location" | grep -q "current_segment"

SEGMENT_ID="$(
  curl -fsS "$API_URL/segments/current?lat=37.525&lon=15.071" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
)"

curl -fsS "$API_URL/segment-heatmap" | grep -q "$SEGMENT_ID"

curl -fsS \
  -H "Content-Type: application/json" \
  -d '{"segment_id":"'"$SEGMENT_ID"'","report_type":"full_zone","session_id":"'"$SESSION_ID"'"}' \
  "$API_URL/segment-reports" | grep -q "accepted"

curl -fsS -X POST "$INGESTION_URL/scenarios/cittadella_morning_peak/start" | grep -q "events_published"
sleep 1

curl -fsS "$API_URL/segments/$SEGMENT_ID/prediction" | grep -q "parkability_percent"

curl -fsS \
  -H "Content-Type: application/json" \
  -d '{"segment_id":"'"$SEGMENT_ID"'","segment_name":"Via Santa Sofia","parkability_percent":34,"status":"difficult","trend":"stable","confidence":0.69,"estimated_search_time_min":18,"recommendation":"Disponibilita bassa"}' \
  "$AI_URL/ai/explain" | grep -q "rule-based-fallback"

curl -fsS -X POST "$API_URL/live-sessions/$SESSION_ID/stop" | grep -q "stopped"

echo "E2E demo OK: $API_URL"
