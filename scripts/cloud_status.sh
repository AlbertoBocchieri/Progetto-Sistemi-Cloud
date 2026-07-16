#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
PROJECT="${PROJECT:-parcheggia}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

export AWS_PROFILE AWS_REGION

echo "AWS identity:"
aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output table

echo
echo "Terraform state:"
terraform -chdir="$TF_DIR" state list 2>/dev/null || echo "Nessuno state Terraform locale trovato."

echo
echo "Terraform backend:"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT}-${ENVIRONMENT}-terraform-state-${ACCOUNT_ID}-${AWS_REGION}}"
aws s3api head-bucket --bucket "$STATE_BUCKET" >/dev/null 2>&1 &&
  echo "S3 state bucket: $STATE_BUCKET" ||
  echo "S3 state bucket: missing"

echo
echo "ECR repositories:"
aws ecr describe-repositories \
  --query 'repositories[?starts_with(repositoryName, `parcheggia-dev/`)].repositoryName' \
  --output table

echo
echo "EKS clusters:"
aws eks list-clusters --query 'clusters[?contains(@, `parcheggia`)]' --output table

echo
echo "RDS instances:"
aws rds describe-db-instances \
  --query 'DBInstances[?contains(DBInstanceIdentifier, `parcheggia`)].DBInstanceIdentifier' \
  --output table 2>/dev/null || true

echo
echo "ElastiCache clusters:"
aws elasticache describe-cache-clusters \
  --query 'CacheClusters[?contains(CacheClusterId, `parcheggia`)].CacheClusterId' \
  --output table 2>/dev/null || true

echo
echo "Amazon MQ brokers:"
aws mq list-brokers \
  --query 'BrokerSummaries[?contains(BrokerName, `parcheggia`)].BrokerName' \
  --output table 2>/dev/null || true
