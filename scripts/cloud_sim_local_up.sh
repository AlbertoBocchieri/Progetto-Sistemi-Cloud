#!/usr/bin/env sh
set -eu

CLUSTER_NAME="${CLUSTER_NAME:-parcheggia}"
NAMESPACE="${NAMESPACE:-parcheggia}"
FRONTEND_PORT="${FRONTEND_PORT:-18080}"
API_PORT="${API_PORT:-18000}"
PREDICTION_PORT="${PREDICTION_PORT:-18004}"
LOCATION_PORT="${LOCATION_PORT:-18005}"
ADMIN_PORT="${ADMIN_PORT:-18006}"
NEMOTRON_PORT="${NEMOTRON_PORT:-18003}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/parcheggia-cloud-sim}"
PIDS_FILE="$RUNTIME_DIR/port-forwards.pid"

cleanup() {
  if [ -f "$PIDS_FILE" ]; then
    while IFS= read -r pid; do
      [ -n "$pid" ] || continue
      kill "$pid" 2>/dev/null || true
    done < "$PIDS_FILE"
    rm -f "$PIDS_FILE"
  fi
}

trap cleanup EXIT INT TERM

port_must_be_free() {
  port="$1"
  if nc -z 127.0.0.1 "$port" >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop the other process or override the port env var." >&2
    exit 1
  fi
}

start_port_forward() {
  service="$1"
  local_port="$2"
  remote_port="$3"
  log="$RUNTIME_DIR/${service}.log"
  port_must_be_free "$local_port"
  kubectl -n "$NAMESPACE" port-forward "svc/${service}" "$local_port:$remote_port" >"$log" 2>&1 &
  echo "$!" >> "$PIDS_FILE"
}

mkdir -p "$RUNTIME_DIR"
cleanup
: > "$PIDS_FILE"

CLUSTER_NAME="$CLUSTER_NAME" scripts/k3d_prepare_local.sh
NAMESPACE="$NAMESPACE" scripts/k8s_apply_local.sh

start_port_forward api-gateway "$API_PORT" 80
start_port_forward frontend "$FRONTEND_PORT" 80
start_port_forward prediction-service "$PREDICTION_PORT" 8000
start_port_forward location-service "$LOCATION_PORT" 8000
start_port_forward admin-service "$ADMIN_PORT" 8000
start_port_forward nemotron-service "$NEMOTRON_PORT" 8000

for i in $(seq 1 60); do
  if curl -fsS "http://localhost:$API_PORT/api/v1/ready" >/dev/null 2>&1 &&
    curl -fsS "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  test "$i" -lt 60
done

scripts/smoke_test.sh \
  "http://localhost:$API_PORT/api/v1" \
  "http://localhost:$API_PORT/ingestion" \
  "http://localhost:$API_PORT" \
  "http://localhost:$PREDICTION_PORT" \
  "http://localhost:$LOCATION_PORT" \
  "http://localhost:$ADMIN_PORT" \
  "http://localhost:$NEMOTRON_PORT" \
  "http://localhost:$FRONTEND_PORT"

cat <<EOF
Cloud simulation ready.
Frontend: http://localhost:$FRONTEND_PORT
API:      http://localhost:$API_PORT/api/v1
Keep this terminal open. Stop with Ctrl+C or: scripts/cloud_sim_local_down.sh
EOF

wait
