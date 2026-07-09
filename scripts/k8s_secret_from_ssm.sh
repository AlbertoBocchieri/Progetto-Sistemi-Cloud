#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
SSM_PREFIX="${SSM_PREFIX:-/parcheggia/dev}"
NAMESPACE="${NAMESPACE:-parcheggia}"
SECRET_NAME="${SECRET_NAME:-parcheggia-secrets}"

export AWS_PROFILE AWS_REGION

command -v kubectl >/dev/null 2>&1 || {
  echo "kubectl is required." >&2
  exit 1
}

aws sts get-caller-identity >/dev/null

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT INT TERM
chmod 600 "$tmp"

get_parameter() {
  aws ssm get-parameter \
    --name "$1" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text
}

{
  printf 'POSTGRES_DB=parcheggia\n'
  printf 'POSTGRES_USER=parcheggia\n'
  printf 'POSTGRES_PASSWORD=%s\n' "$(get_parameter "$SSM_PREFIX/secrets/postgres-password")"
  printf 'RABBITMQ_DEFAULT_USER=parcheggia\n'
  printf 'RABBITMQ_DEFAULT_PASS=%s\n' "$(get_parameter "$SSM_PREFIX/secrets/rabbitmq-password")"
  printf 'TOMTOM_API_KEY=%s\n' "$(get_parameter "$SSM_PREFIX/secrets/tomtom-api-key")"
  printf 'NEMOTRON_API_KEY=%s\n' "$(get_parameter "$SSM_PREFIX/secrets/nemotron-api-key")"
  printf 'ELEVENLABS_API_KEY=%s\n' "$(get_parameter "$SSM_PREFIX/secrets/elevenlabs-api-key")"
} >"$tmp"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
  --from-env-file="$tmp" \
  --dry-run=client \
  -o yaml | kubectl apply -f -

echo "Kubernetes secret $NAMESPACE/$SECRET_NAME synced from SSM"
