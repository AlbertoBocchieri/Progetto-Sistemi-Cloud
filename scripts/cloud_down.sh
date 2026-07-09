#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"

if [ "${CONFIRM_DESTROY:-}" != "destroy-parcheggia-dev" ]; then
  echo "Bloccato: esporta CONFIRM_DESTROY=destroy-parcheggia-dev per distruggere risorse AWS." >&2
  exit 2
fi

export AWS_PROFILE AWS_REGION

aws sts get-caller-identity >/dev/null
terraform -chdir="$TF_DIR" destroy -input=false
