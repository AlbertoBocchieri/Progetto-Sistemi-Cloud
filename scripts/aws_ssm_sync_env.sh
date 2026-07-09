#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
ENV_FILE="${ENV_FILE:-.env}"
SSM_PREFIX="${SSM_PREFIX:-/parcheggia/dev}"

export AWS_PROFILE AWS_REGION

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

TOMTOM_BUDGET_FRACTION="${TOMTOM_BUDGET_FRACTION:-0.05}"
TOMTOM_MONTHLY_LIMIT_TRAFFIC_FLOW="${TOMTOM_MONTHLY_LIMIT_TRAFFIC_FLOW:-200000}"
TOMTOM_MONTHLY_LIMIT_TRAFFIC_INCIDENTS="${TOMTOM_MONTHLY_LIMIT_TRAFFIC_INCIDENTS:-2500}"
TOMTOM_MONTHLY_LIMIT_SEARCH="${TOMTOM_MONTHLY_LIMIT_SEARCH:-2500}"
TOMTOM_MONTHLY_LIMIT_ROUTING="${TOMTOM_MONTHLY_LIMIT_ROUTING:-20000}"
NEMOTRON_BASE_URL="${NEMOTRON_BASE_URL:-https://integrate.api.nvidia.com/v1}"
NEMOTRON_MODEL="${NEMOTRON_MODEL:-nvidia/nemotron-3-nano-30b-a3b}"
NEMOTRON_TIMEOUT_SECONDS="${NEMOTRON_TIMEOUT_SECONDS:-45}"
NEMOTRON_CACHE_TTL_SECONDS="${NEMOTRON_CACHE_TTL_SECONDS:-600}"
ELEVENLABS_BASE_URL="${ELEVENLABS_BASE_URL:-https://api.elevenlabs.io/v1}"
ELEVENLABS_VOICE_ID="${ELEVENLABS_VOICE_ID:-EXAVITQu4vr4xnSDxMaL}"
ELEVENLABS_MODEL_ID="${ELEVENLABS_MODEL_ID:-eleven_flash_v2_5}"
ELEVENLABS_OUTPUT_FORMAT="${ELEVENLABS_OUTPUT_FORMAT:-mp3_22050_32}"
ELEVENLABS_TIMEOUT_SECONDS="${ELEVENLABS_TIMEOUT_SECONDS:-20}"
ELEVENLABS_SIMILARITY_BOOST="${ELEVENLABS_SIMILARITY_BOOST:-0.50}"
ELEVENLABS_STYLE_EXAGGERATION="${ELEVENLABS_STYLE_EXAGGERATION:-0.25}"

aws sts get-caller-identity >/dev/null

json_put_parameter() {
  name="$1"
  type="$2"
  value="$3"
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT INT TERM
  PARAM_NAME="$name" PARAM_TYPE="$type" PARAM_VALUE="$value" python3 - "$tmp" <<'PY'
import json
import os
import sys

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(
        {
            "Name": os.environ["PARAM_NAME"],
            "Type": os.environ["PARAM_TYPE"],
            "Value": os.environ["PARAM_VALUE"],
            "Overwrite": True,
        },
        handle,
    )
PY
  aws ssm put-parameter --cli-input-json "file://$tmp" >/dev/null
  rm -f "$tmp"
  trap - EXIT INT TERM
  echo "stored $name"
}

put_if_set() {
  var_name="$1"
  parameter_name="$2"
  type="$3"
  value="$(eval "printf '%s' \"\${$var_name:-}\"")"
  if [ -n "$value" ]; then
    json_put_parameter "$parameter_name" "$type" "$value"
  else
    echo "skipped $parameter_name ($var_name empty)"
  fi
}

ensure_password() {
  var_name="$1"
  parameter_name="$2"
  value="$(eval "printf '%s' \"\${$var_name:-}\"")"
  if [ -n "$value" ]; then
    json_put_parameter "$parameter_name" SecureString "$value"
    return
  fi
  if aws ssm get-parameter --name "$parameter_name" >/dev/null 2>&1; then
    echo "kept $parameter_name"
    return
  fi
  generated="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
  json_put_parameter "$parameter_name" SecureString "$generated"
}

put_if_set TOMTOM_API_KEY "$SSM_PREFIX/secrets/tomtom-api-key" SecureString
put_if_set NEMOTRON_API_KEY "$SSM_PREFIX/secrets/nemotron-api-key" SecureString
put_if_set ELEVENLABS_API_KEY "$SSM_PREFIX/secrets/elevenlabs-api-key" SecureString

ensure_password POSTGRES_PASSWORD "$SSM_PREFIX/secrets/postgres-password"
ensure_password RABBITMQ_DEFAULT_PASS "$SSM_PREFIX/secrets/rabbitmq-password"

put_if_set TOMTOM_BUDGET_FRACTION "$SSM_PREFIX/config/tomtom-budget-fraction" String
put_if_set TOMTOM_MONTHLY_LIMIT_TRAFFIC_FLOW "$SSM_PREFIX/config/tomtom-monthly-limit-traffic-flow" String
put_if_set TOMTOM_MONTHLY_LIMIT_TRAFFIC_INCIDENTS "$SSM_PREFIX/config/tomtom-monthly-limit-traffic-incidents" String
put_if_set TOMTOM_MONTHLY_LIMIT_SEARCH "$SSM_PREFIX/config/tomtom-monthly-limit-search" String
put_if_set TOMTOM_MONTHLY_LIMIT_ROUTING "$SSM_PREFIX/config/tomtom-monthly-limit-routing" String
put_if_set NEMOTRON_BASE_URL "$SSM_PREFIX/config/nemotron-base-url" String
put_if_set NEMOTRON_MODEL "$SSM_PREFIX/config/nemotron-model" String
put_if_set NEMOTRON_TIMEOUT_SECONDS "$SSM_PREFIX/config/nemotron-timeout-seconds" String
put_if_set NEMOTRON_CACHE_TTL_SECONDS "$SSM_PREFIX/config/nemotron-cache-ttl-seconds" String
put_if_set ELEVENLABS_BASE_URL "$SSM_PREFIX/config/elevenlabs-base-url" String
put_if_set ELEVENLABS_VOICE_ID "$SSM_PREFIX/config/elevenlabs-voice-id" String
put_if_set ELEVENLABS_MODEL_ID "$SSM_PREFIX/config/elevenlabs-model-id" String
put_if_set ELEVENLABS_OUTPUT_FORMAT "$SSM_PREFIX/config/elevenlabs-output-format" String
put_if_set ELEVENLABS_TIMEOUT_SECONDS "$SSM_PREFIX/config/elevenlabs-timeout-seconds" String
put_if_set ELEVENLABS_SIMILARITY_BOOST "$SSM_PREFIX/config/elevenlabs-similarity-boost" String
put_if_set ELEVENLABS_STYLE_EXAGGERATION "$SSM_PREFIX/config/elevenlabs-style-exaggeration" String

echo "SSM sync completed under $SSM_PREFIX"
