#!/usr/bin/env sh
set -eu

NAMESPACE="${NAMESPACE:-parcheggia}"
ITERATIONS="${ITERATIONS:-30}"
PIDS=""

cleanup() {
  for pid in $PIDS; do
    kill "$pid" 2>/dev/null || true
  done
}

trap cleanup EXIT INT TERM

port_forward() {
  service="$1"
  mapping="$2"
  log="/tmp/parcheggia-pf-${service}.log"
  kubectl -n "$NAMESPACE" port-forward "svc/${service}" "$mapping" >"$log" 2>&1 &
  PIDS="$PIDS $!"
}

port_forward api-gateway 8000:80
port_forward frontend 8080:80
port_forward prediction-service 8004:8000
port_forward location-service 8005:8000
port_forward admin-service 8006:8000
port_forward nemotron-service 8003:8000

for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/api/v1/ready >/dev/null 2>&1 &&
    curl -fsS http://localhost:8080 >/dev/null 2>&1; then
    break
  fi
  sleep 1
  test "$i" -lt 60
done

scripts/smoke_test.sh
scripts/e2e_demo_test.sh
ITERATIONS="$ITERATIONS" scripts/load_test.sh
