#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
PLAN_FILE="${PLAN_FILE:-cloud.tfplan}"

export AWS_PROFILE AWS_REGION

aws sts get-caller-identity >/dev/null
terraform -chdir="$TF_DIR" init -input=false
terraform -chdir="$TF_DIR" validate
terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN_FILE"

echo "Plan salvato in $TF_DIR/$PLAN_FILE"
echo "Per applicarlo: CONFIRM_APPLY=apply-parcheggia-dev scripts/cloud_up.sh"
