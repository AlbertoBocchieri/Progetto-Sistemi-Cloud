#!/usr/bin/env sh
set -eu

CPU="${CPU:-2}"
MEMORY="${MEMORY:-3}"
DISK="${DISK:-20}"

if ! command -v colima >/dev/null 2>&1; then
  echo "colima is required. Install it with: brew install colima" >&2
  exit 1
fi

colima start --cpu "$CPU" --memory "$MEMORY" --disk "$DISK" --runtime docker --arch aarch64
