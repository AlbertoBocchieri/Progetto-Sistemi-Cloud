#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
PLAN_FILE="${PLAN_FILE:-cloud-down.tfplan}"

if [ "${CONFIRM_DESTROY:-}" != "destroy-parcheggia-dev" ]; then
  echo "Bloccato: esporta CONFIRM_DESTROY=destroy-parcheggia-dev per distruggere risorse AWS." >&2
  exit 2
fi

export AWS_PROFILE AWS_REGION

aws sts get-caller-identity >/dev/null
export TF_VAR_enable_cloud_stack=false
terraform -chdir="$TF_DIR" init -input=false
terraform -chdir="$TF_DIR" validate
terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN_FILE"
terraform -chdir="$TF_DIR" apply -input=false "$PLAN_FILE"

echo "Cloud spento: lo stack costoso e' disabilitato. ECR, SSM e backend Terraform restano disponibili."
