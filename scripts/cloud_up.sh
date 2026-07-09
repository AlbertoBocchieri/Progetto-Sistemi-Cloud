#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
PLAN_FILE="${PLAN_FILE:-cloud.tfplan}"

if [ "${CONFIRM_APPLY:-}" != "apply-parcheggia-dev" ]; then
  echo "Bloccato: esporta CONFIRM_APPLY=apply-parcheggia-dev per creare risorse AWS." >&2
  exit 2
fi

export AWS_PROFILE AWS_REGION

aws sts get-caller-identity >/dev/null
terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN_FILE"
terraform -chdir="$TF_DIR" apply -input=false "$PLAN_FILE"

echo "Cloud applicato. Quando hai finito: CONFIRM_DESTROY=destroy-parcheggia-dev scripts/cloud_down.sh"
