#!/usr/bin/env sh
set -eu

CLUSTER_NAME="${CLUSTER_NAME:-parcheggia}"

if ! command -v k3d >/dev/null 2>&1; then
  echo "k3d is required. Install it with: brew install k3d" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker must be running before creating a k3d cluster." >&2
  exit 1
fi

if ! k3d cluster list "$CLUSTER_NAME" >/dev/null 2>&1; then
  k3d cluster create "$CLUSTER_NAME" --servers 1 --agents 0 --wait
fi

k3d kubeconfig merge "$CLUSTER_NAME" --kubeconfig-switch-context >/dev/null
kubectl config use-context "k3d-$CLUSTER_NAME" >/dev/null

docker compose build

IMAGES="
  progetto-sistemi-cloud-api-gateway:latest \
  progetto-sistemi-cloud-frontend:latest \
  progetto-sistemi-cloud-zone-service:latest \
  progetto-sistemi-cloud-ingestion-service:latest \
  progetto-sistemi-cloud-nemotron-service:latest \
  progetto-sistemi-cloud-prediction-service:latest \
  progetto-sistemi-cloud-location-service:latest \
  progetto-sistemi-cloud-admin-service:latest
"
k3d image import $IMAGES -c "$CLUSTER_NAME"

echo "k3d cluster ready: $CLUSTER_NAME"
