#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE-}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
PROJECT="${PROJECT:-parcheggia}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"

if [ -z "$AWS_PROFILE" ] && { [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; }; then
  AWS_PROFILE="parcheggia-dev"
fi

if [ -n "$AWS_PROFILE" ]; then
  export AWS_PROFILE
else
  unset AWS_PROFILE
fi
export AWS_REGION

ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT}-${ENVIRONMENT}-terraform-state-${ACCOUNT_ID}-${AWS_REGION}}"

if ! aws s3api head-bucket --bucket "$STATE_BUCKET" >/dev/null 2>&1; then
  echo "Backend S3 non trovato: $STATE_BUCKET" >&2
  echo "Crealo prima con: scripts/terraform_backend_bootstrap.sh" >&2
  exit 1
fi

terraform -chdir="$TF_DIR" init -input=false -reconfigure \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="region=$AWS_REGION"
