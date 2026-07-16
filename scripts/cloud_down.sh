#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE-}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
PLAN_FILE="${PLAN_FILE:-cloud-down.tfplan}"
CLUSTER_NAME="${CLUSTER_NAME:-parcheggia-dev}"
NAMESPACE="${NAMESPACE:-parcheggia}"

if [ "${CONFIRM_DESTROY:-}" != "destroy-parcheggia-dev" ]; then
  echo "Bloccato: esporta CONFIRM_DESTROY=destroy-parcheggia-dev per distruggere risorse AWS." >&2
  exit 2
fi

if [ -z "$AWS_PROFILE" ] && { [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; }; then
  AWS_PROFILE="parcheggia-dev"
fi

if [ -n "$AWS_PROFILE" ]; then
  export AWS_PROFILE
else
  unset AWS_PROFILE
fi
export AWS_REGION

aws sts get-caller-identity >/dev/null

if [ -x scripts/cloud_schedule_auto_down.sh ]; then
  scripts/cloud_schedule_auto_down.sh cancel || true
fi

if [ "${AUTO_DOWN_CHILD:-}" != "true" ] && [ -x scripts/cloud_auto_down.sh ]; then
  scripts/cloud_auto_down.sh cancel || true
fi

if command -v kubectl >/dev/null 2>&1 \
  && aws eks describe-cluster --name "$CLUSTER_NAME" --query 'cluster.status' --output text >/dev/null 2>&1; then
  echo "Pulizia Load Balancer Kubernetes prima dello spegnimento..."
  aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME" >/dev/null
  kubectl -n "$NAMESPACE" delete service frontend --ignore-not-found --wait=true || true
  sleep 45
fi

export TF_VAR_enable_cloud_stack=false
scripts/terraform_init.sh
terraform -chdir="$TF_DIR" validate
terraform -chdir="$TF_DIR" plan -input=false -out="$PLAN_FILE"
terraform -chdir="$TF_DIR" apply -input=false "$PLAN_FILE"

echo "Cloud spento: lo stack costoso e' disabilitato. ECR, SSM e backend Terraform restano disponibili."
