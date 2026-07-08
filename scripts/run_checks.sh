#!/usr/bin/env sh
set -eu

scripts/static_checks.sh
scripts/smoke_test.sh
scripts/e2e_demo_test.sh

echo "All checks OK"
