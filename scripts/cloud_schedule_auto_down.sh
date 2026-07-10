#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE-}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
TF_DIR="${TF_DIR:-infrastructure/terraform/aws}"
AFTER_SECONDS="${AUTO_DOWN_AFTER_SECONDS:-14400}"
SCHEDULE_NAME="${AUTO_DOWN_SCHEDULE_NAME:-parcheggia-dev-auto-down}"
COMMAND="${1:-schedule}"

if [ -z "$AWS_PROFILE" ] && { [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; }; then
  AWS_PROFILE="parcheggia-dev"
fi

if [ -n "$AWS_PROFILE" ]; then
  export AWS_PROFILE
else
  unset AWS_PROFILE
fi
export AWS_REGION

delete_schedule() {
  aws scheduler delete-schedule --name "$SCHEDULE_NAME" >/dev/null 2>&1 || true
}

case "$COMMAND" in
  schedule)
    command -v aws >/dev/null 2>&1 || { echo "aws CLI is required." >&2; exit 1; }
    command -v terraform >/dev/null 2>&1 || { echo "terraform is required." >&2; exit 1; }
    command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

    lambda_arn="$(terraform -chdir="$TF_DIR" output -raw auto_down_lambda_arn)"
    role_arn="$(terraform -chdir="$TF_DIR" output -raw auto_down_scheduler_role_arn)"
    run_at="$(AUTO_DOWN_AFTER_SECONDS="$AFTER_SECONDS" python3 - <<'PY'
from datetime import datetime, timedelta, timezone
import os

seconds = int(os.environ["AUTO_DOWN_AFTER_SECONDS"])
print((datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S"))
PY
)"

    target_file="$(mktemp)"
    trap 'rm -f "$target_file"' EXIT
    python3 - "$lambda_arn" "$role_arn" "$AFTER_SECONDS" >"$target_file" <<'PY'
import json
import sys

print(json.dumps({
    "Arn": sys.argv[1],
    "RoleArn": sys.argv[2],
    "Input": json.dumps({
        "source": "parcheggia-cloud-demo",
        "after_seconds": int(sys.argv[3]),
    }),
}))
PY

    delete_schedule
    aws scheduler create-schedule \
      --name "$SCHEDULE_NAME" \
      --schedule-expression "at($run_at)" \
      --schedule-expression-timezone "UTC" \
      --flexible-time-window Mode=OFF \
      --action-after-completion DELETE \
      --target "file://$target_file" >/dev/null

    echo "Auto-spegnimento AWS programmato alle $run_at UTC con EventBridge Scheduler."
    ;;
  cancel)
    delete_schedule
    echo "Auto-spegnimento AWS annullato se presente."
    ;;
  status)
    if ! aws scheduler get-schedule --name "$SCHEDULE_NAME" \
      --query '{Name:Name,State:State,ScheduleExpression:ScheduleExpression,Target:Target.Arn}' \
      --output table; then
      echo "Nessun auto-spegnimento AWS attivo."
    fi
    ;;
  *)
    echo "Uso: $0 [schedule|cancel|status]" >&2
    exit 2
    ;;
esac
