#!/usr/bin/env sh
set -eu

CLUSTER_NAME="${CLUSTER_NAME:-parcheggia}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/parcheggia-cloud-sim}"
PIDS_FILE="$RUNTIME_DIR/port-forwards.pid"

if [ -f "$PIDS_FILE" ]; then
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill "$pid" 2>/dev/null || true
  done < "$PIDS_FILE"
  rm -f "$PIDS_FILE"
fi

if command -v k3d >/dev/null 2>&1 &&
  k3d cluster list "$CLUSTER_NAME" >/dev/null 2>&1; then
  k3d cluster delete "$CLUSTER_NAME"
fi

echo "Cloud simulation stopped."
