#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
SSM_PREFIX="${SSM_PREFIX:-/parcheggia/dev}"

export AWS_PROFILE AWS_REGION

aws sts get-caller-identity >/dev/null
aws ssm get-parameters-by-path \
  --path "$SSM_PREFIX" \
  --recursive \
  --query 'Parameters[].{Name:Name,Type:Type,Version:Version,LastModifiedDate:LastModifiedDate}' \
  --output table
