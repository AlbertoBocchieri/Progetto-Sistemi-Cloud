#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
PROJECT="${PROJECT:-parcheggia}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
ACCOUNT_ID="${ACCOUNT_ID:-$(AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" aws sts get-caller-identity --query Account --output text)}"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT}-${ENVIRONMENT}-terraform-state-${ACCOUNT_ID}-${AWS_REGION}}"

export AWS_PROFILE AWS_REGION

aws sts get-caller-identity >/dev/null

if aws s3api head-bucket --bucket "$STATE_BUCKET" >/dev/null 2>&1; then
  echo "S3 bucket exists: $STATE_BUCKET"
else
  if [ "$AWS_REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$STATE_BUCKET" >/dev/null
  else
    aws s3api create-bucket \
      --bucket "$STATE_BUCKET" \
      --create-bucket-configuration "LocationConstraint=$AWS_REGION" >/dev/null
  fi
  echo "S3 bucket created: $STATE_BUCKET"
fi

aws s3api put-public-access-block \
  --bucket "$STATE_BUCKET" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" >/dev/null

aws s3api put-bucket-versioning \
  --bucket "$STATE_BUCKET" \
  --versioning-configuration Status=Enabled >/dev/null

aws s3api put-bucket-encryption \
  --bucket "$STATE_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}' >/dev/null

aws s3api put-bucket-lifecycle-configuration \
  --bucket "$STATE_BUCKET" \
  --lifecycle-configuration \
  '{"Rules":[{"ID":"expire-old-terraform-state-versions","Status":"Enabled","Filter":{"Prefix":""},"NoncurrentVersionExpiration":{"NoncurrentDays":30}}]}' >/dev/null

echo
echo "Backend ready:"
echo "  bucket: $STATE_BUCKET"
echo "  lock: S3 native lockfile"
