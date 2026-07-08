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

docker compose build

for image in \
  progetto-sistemi-cloud-api-gateway:latest \
  progetto-sistemi-cloud-frontend:latest \
  progetto-sistemi-cloud-zone-service:latest \
  progetto-sistemi-cloud-ingestion-service:latest \
  progetto-sistemi-cloud-nemotron-service:latest \
  progetto-sistemi-cloud-prediction-service:latest \
  progetto-sistemi-cloud-location-service:latest \
  progetto-sistemi-cloud-admin-service:latest
do
  k3d image import "$image" -c "$CLUSTER_NAME"
done

echo "k3d cluster ready: $CLUSTER_NAME"
