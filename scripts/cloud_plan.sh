#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
PLAN_FILE="${PLAN_FILE:-cloud-up.tfplan}"
ENABLE_CLOUD_STACK="${ENABLE_CLOUD_STACK:-true}"
DB_PASSWORD_PARAMETER="${DB_PASSWORD_PARAMETER:-/parcheggia/dev/secrets/postgres-password}"
MQ_PASSWORD_PARAMETER="${MQ_PASSWORD_PARAMETER:-/parcheggia/dev/secrets/rabbitmq-password}"

export AWS_PROFILE AWS_REGION

aws sts get-caller-identity >/dev/null
export TF_VAR_enable_cloud_stack="$ENABLE_CLOUD_STACK"
if [ "$ENABLE_CLOUD_STACK" = "true" ]; then
  export TF_VAR_db_password="$(aws ssm get-parameter --name "$DB_PASSWORD_PARAMETER" --with-decryption --query Parameter.Value --output text)"
  export TF_VAR_mq_password="$(aws ssm get-parameter --name "$MQ_PASSWORD_PARAMETER" --with-decryption --query Parameter.Value --output text)"
fi
scripts/terraform_init.sh
terraform -chdir="$TF_DIR" validate
terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN_FILE"

echo "Plan salvato in $TF_DIR/$PLAN_FILE"
echo "Per applicarlo: CONFIRM_APPLY=apply-parcheggia-dev scripts/cloud_up.sh"
