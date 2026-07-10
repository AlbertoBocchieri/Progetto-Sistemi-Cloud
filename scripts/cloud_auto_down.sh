#!/usr/bin/env sh
set -eu

AWS_PROFILE="${AWS_PROFILE:-parcheggia-dev}"
AWS_REGION="${AWS_REGION:-eu-south-1}"
AFTER_SECONDS="${AUTO_DOWN_AFTER_SECONDS:-14400}"
PID_FILE="${AUTO_DOWN_PID_FILE:-/tmp/parcheggia-cloud-auto-down.pid}"
LOG_FILE="${AUTO_DOWN_LOG_FILE:-/tmp/parcheggia-cloud-auto-down.log}"
COMMAND="${1:-schedule}"
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"

cancel_existing() {
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "Auto-spegnimento precedente annullato: pid $pid"
    fi
    rm -f "$PID_FILE"
  fi
}

case "$COMMAND" in
  schedule)
    cancel_existing
    (
      sleep "$AFTER_SECONDS"
      cd "$REPO_DIR"
      echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') auto-spegnimento avviato"
      AUTO_DOWN_CHILD=true AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" CONFIRM_DESTROY=destroy-parcheggia-dev scripts/cloud_down.sh
    ) >>"$LOG_FILE" 2>&1 &
    echo "$!" >"$PID_FILE"
    echo "Auto-spegnimento programmato tra $AFTER_SECONDS secondi. Log: $LOG_FILE"
    ;;
  cancel)
    cancel_existing
    ;;
  status)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "Auto-spegnimento attivo: pid $(cat "$PID_FILE"). Log: $LOG_FILE"
    else
      echo "Nessun auto-spegnimento attivo."
    fi
    ;;
  *)
    echo "Uso: $0 [schedule|cancel|status]" >&2
    exit 2
    ;;
esac
