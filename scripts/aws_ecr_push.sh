#!/usr/bin/env sh
set -eu

AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required." >&2
  exit 1
fi

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker-compatible runtime must be running." >&2
  exit 1
fi

ECR_JSON="$(terraform -chdir="$TF_DIR" output -json ecr_repository_urls)"
REGISTRY="$(printf '%s' "$ECR_JSON" | python3 -c 'import json,sys; print(next(iter(json.load(sys.stdin).values())).split("/")[0])')"

aws ecr get-login-password --region "$AWS_REGION" |
  docker login --username AWS --password-stdin "$REGISTRY"

docker compose build

for service in \
  api-gateway \
  frontend \
  zone-service \
  ingestion-service \
  nemotron-service \
  prediction-service \
  location-service \
  admin-service
do
  repo="$(printf '%s' "$ECR_JSON" | SERVICE="$service" python3 -c 'import json,os,sys; print(json.load(sys.stdin)[os.environ["SERVICE"]])')"
  local_image="progetto-sistemi-cloud-${service}:latest"
  remote_image="${repo}:${IMAGE_TAG}"
  docker tag "$local_image" "$remote_image"
  docker push "$remote_image"
done
