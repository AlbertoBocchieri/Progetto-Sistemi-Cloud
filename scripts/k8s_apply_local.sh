#!/usr/bin/env sh
set -eu

NAMESPACE="${NAMESPACE:-parcheggia}"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" create configmap zone-migrations \
  --from-file=001_create_zones.sql=services/zone-service/migrations/001_create_zones.sql \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NAMESPACE" delete job db-init --ignore-not-found
kubectl apply -f infrastructure/k8s/local-demo.yaml

kubectl -n "$NAMESPACE" rollout status deployment/postgres --timeout=180s
kubectl -n "$NAMESPACE" wait --for=condition=complete job/db-init --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/redis --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/rabbitmq --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/zone-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/ingestion-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/nemotron-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/prediction-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/location-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/admin-service --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/api-gateway --timeout=180s
kubectl -n "$NAMESPACE" rollout status deployment/frontend --timeout=180s

kubectl -n "$NAMESPACE" get pods
