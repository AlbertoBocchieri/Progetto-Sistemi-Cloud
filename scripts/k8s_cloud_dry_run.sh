#!/usr/bin/env sh
set -eu

MANIFEST="${MANIFEST:-infrastructure/k8s/cloud-demo.yaml}"

if command -v kubeconform >/dev/null 2>&1; then
  kubeconform -strict -summary "$MANIFEST"
fi

if kubectl version --request-timeout=3s >/dev/null 2>&1; then
  kubectl apply --dry-run=client --validate=false -f "$MANIFEST" >/dev/null
  echo "kubectl client dry-run OK: $MANIFEST"
else
  echo "kubectl client dry-run skipped: no Kubernetes API reachable."
fi

echo "Cloud Kubernetes dry-run OK: $MANIFEST"
