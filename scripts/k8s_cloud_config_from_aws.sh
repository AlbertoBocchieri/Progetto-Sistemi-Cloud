#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
SSM_PREFIX="${SSM_PREFIX:-/parcheggia/dev}"
NAMESPACE="${NAMESPACE:-parcheggia}"
CONFIG_NAME="${CONFIG_NAME:-parcheggia-runtime}"
SECRET_NAME="${SECRET_NAME:-parcheggia-secrets}"

export AWS_PROFILE AWS_REGION

command -v aws >/dev/null 2>&1 || {
  echo "aws CLI is required." >&2
  exit 1
}
command -v terraform >/dev/null 2>&1 || {
  echo "terraform is required." >&2
  exit 1
}
command -v kubectl >/dev/null 2>&1 || {
  echo "kubectl is required." >&2
  exit 1
}

aws sts get-caller-identity >/dev/null

get_ssm() {
  aws ssm get-parameter \
    --name "$1" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text
}

get_ssm_optional() {
  name="$1"
  default="$2"
  aws ssm get-parameter \
    --name "$name" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || printf '%s' "$default"
}

tf_raw() {
  terraform -chdir="$TF_DIR" output -raw "$1" 2>/dev/null || true
}

rds_endpoint="$(tf_raw rds_endpoint)"
redis_endpoint="$(tf_raw redis_endpoint)"
rabbitmq_endpoint_json="$(terraform -chdir="$TF_DIR" output -json rabbitmq_endpoint 2>/dev/null || printf 'null')"

rabbitmq_endpoint="$(
  printf '%s' "$rabbitmq_endpoint_json" |
    python3 -c 'import json,sys; v=json.load(sys.stdin); print((v[0] if isinstance(v, list) and v else v) or "")'
)"

if [ -z "$rds_endpoint" ] || [ "$rds_endpoint" = "null" ]; then
  echo "RDS endpoint missing. Run Terraform with enable_cloud_stack=true first." >&2
  exit 2
fi
if [ -z "$redis_endpoint" ] || [ "$redis_endpoint" = "null" ]; then
  echo "Redis endpoint missing. Run Terraform with enable_cloud_stack=true first." >&2
  exit 2
fi
if [ -z "$rabbitmq_endpoint" ] || [ "$rabbitmq_endpoint" = "null" ]; then
  echo "RabbitMQ endpoint missing. Run Terraform with enable_cloud_stack=true first." >&2
  exit 2
fi

postgres_password="$(get_ssm "$SSM_PREFIX/secrets/postgres-password")"
rabbitmq_password="$(get_ssm "$SSM_PREFIX/secrets/rabbitmq-password")"

database_url="$(
  POSTGRES_PASSWORD="$postgres_password" POSTGRES_HOST="$rds_endpoint" python3 - <<'PY'
import os
from urllib.parse import quote

password = quote(os.environ["POSTGRES_PASSWORD"], safe="")
host = os.environ["POSTGRES_HOST"]
print(f"postgresql+psycopg://parcheggia:{password}@{host}:5432/parcheggia")
PY
)"

rabbitmq_url="$(
  RABBITMQ_PASSWORD="$rabbitmq_password" RABBITMQ_ENDPOINT="$rabbitmq_endpoint" python3 - <<'PY'
import os
from urllib.parse import quote, urlparse

password = quote(os.environ["RABBITMQ_PASSWORD"], safe="")
endpoint = os.environ["RABBITMQ_ENDPOINT"]
parsed = urlparse(endpoint)
scheme = parsed.scheme or "amqps"
hostport = parsed.netloc or parsed.path
print(f"{scheme}://parcheggia:{password}@{hostport}/%2F")
PY
)"

config_tmp="$(mktemp)"
secret_tmp="$(mktemp)"
trap 'rm -f "$config_tmp" "$secret_tmp"' EXIT INT TERM
chmod 600 "$config_tmp" "$secret_tmp"

{
  printf 'POSTGRES_DB=parcheggia\n'
  printf 'POSTGRES_USER=parcheggia\n'
  printf 'POSTGRES_HOST=%s\n' "$rds_endpoint"
  printf 'REDIS_URL=redis://%s:6379/0\n' "$redis_endpoint"
  printf 'EVENT_EXCHANGE=parcheggia.events\n'
  printf 'ZONE_SERVICE_URL=http://zone-service:8000/api/v1\n'
  printf 'PREDICTION_SERVICE_URL=http://prediction-service:8000/api/v1\n'
  printf 'TOMTOM_BUDGET_FRACTION=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/tomtom-budget-fraction" "0.05")"
  printf 'TOMTOM_MONTHLY_LIMIT_TRAFFIC_FLOW=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/tomtom-monthly-limit-traffic-flow" "200000")"
  printf 'TOMTOM_MONTHLY_LIMIT_TRAFFIC_INCIDENTS=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/tomtom-monthly-limit-traffic-incidents" "2500")"
  printf 'TOMTOM_MONTHLY_LIMIT_SEARCH=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/tomtom-monthly-limit-search" "2500")"
  printf 'TOMTOM_MONTHLY_LIMIT_ROUTING=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/tomtom-monthly-limit-routing" "20000")"
  printf 'NEMOTRON_BASE_URL=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/nemotron-base-url" "https://integrate.api.nvidia.com/v1")"
  printf 'NEMOTRON_MODEL=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/nemotron-model" "nvidia/nemotron-3-nano-30b-a3b")"
  printf 'NEMOTRON_TIMEOUT_SECONDS=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/nemotron-timeout-seconds" "45")"
  printf 'NEMOTRON_CACHE_TTL_SECONDS=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/nemotron-cache-ttl-seconds" "600")"
  printf 'ELEVENLABS_BASE_URL=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/elevenlabs-base-url" "https://api.elevenlabs.io/v1")"
  printf 'ELEVENLABS_VOICE_ID=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/elevenlabs-voice-id" "EXAVITQu4vr4xnSDxMaL")"
  printf 'ELEVENLABS_MODEL_ID=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/elevenlabs-model-id" "eleven_flash_v2_5")"
  printf 'ELEVENLABS_OUTPUT_FORMAT=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/elevenlabs-output-format" "mp3_22050_32")"
  printf 'ELEVENLABS_TIMEOUT_SECONDS=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/elevenlabs-timeout-seconds" "20")"
  printf 'ELEVENLABS_SIMILARITY_BOOST=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/elevenlabs-similarity-boost" "0.50")"
  printf 'ELEVENLABS_STYLE_EXAGGERATION=%s\n' "$(get_ssm_optional "$SSM_PREFIX/config/elevenlabs-style-exaggeration" "0.25")"
} >"$config_tmp"

{
  printf 'POSTGRES_PASSWORD=%s\n' "$postgres_password"
  printf 'DATABASE_URL=%s\n' "$database_url"
  printf 'RABBITMQ_DEFAULT_USER=parcheggia\n'
  printf 'RABBITMQ_DEFAULT_PASS=%s\n' "$rabbitmq_password"
  printf 'RABBITMQ_URL=%s\n' "$rabbitmq_url"
  printf 'TOMTOM_API_KEY=%s\n' "$(get_ssm "$SSM_PREFIX/secrets/tomtom-api-key")"
  printf 'NEMOTRON_API_KEY=%s\n' "$(get_ssm "$SSM_PREFIX/secrets/nemotron-api-key")"
  printf 'ELEVENLABS_API_KEY=%s\n' "$(get_ssm "$SSM_PREFIX/secrets/elevenlabs-api-key")"
} >"$secret_tmp"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" create configmap "$CONFIG_NAME" \
  --from-env-file="$config_tmp" \
  --dry-run=client \
  -o yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
  --from-env-file="$secret_tmp" \
  --dry-run=client \
  -o yaml | kubectl apply -f -

echo "Kubernetes ConfigMap $NAMESPACE/$CONFIG_NAME and Secret $NAMESPACE/$SECRET_NAME synced from AWS"
