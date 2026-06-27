#!/usr/bin/env bash
# Toggle SQS-triggered Lambda consumers to save SQS free-tier API calls when idle.
#
# Idle dev processors poll empty queues 24/7 (~850K SQS requests/month across 4 queues).
# Disable when not actively developing; re-enable before testing message/voice flows.
#
# Usage (from repo root):
#   ./scripts/sqs-consumers.sh stop          # disable all SQS consumers
#   ./scripts/sqs-consumers.sh start         # enable all SQS consumers
#   ./scripts/sqs-consumers.sh status        # show current state
#   ENV=dev ./scripts/sqs-consumers.sh stop  # default ENV is dev
#
# Affected Lambdas (per environment):
#   agrinexus-processor-{ENV}
#   agrinexus-processor-beta-{ENV}
#   agrinexus-voice-{ENV}
#   agrinexus-dlq-{ENV}

set -euo pipefail

ENV="${ENV:-dev}"
REGION="${AWS_REGION:-us-east-1}"

FUNCTIONS=(
  "agrinexus-processor-${ENV}"
  "agrinexus-processor-beta-${ENV}"
  "agrinexus-voice-${ENV}"
  "agrinexus-dlq-${ENV}"
)

usage() {
  echo "Usage: $0 {start|stop|status}" >&2
  exit 1
}

mapping_uuids() {
  local fn="$1"
  aws lambda list-event-source-mappings \
    --function-name "$fn" \
    --region "$REGION" \
    --query 'EventSourceMappings[?contains(EventSourceArn, `:sqs:`)].UUID' \
    --output text
}

set_enabled() {
  local enabled="$1" # true or false
  local action="$2"  # start or stop

  for fn in "${FUNCTIONS[@]}"; do
    uuids="$(mapping_uuids "$fn" || true)"
    if [[ -z "${uuids// }" ]]; then
      echo "  $fn: no SQS mapping found (skipped)"
      continue
    fi

    for uuid in $uuids; do
      if [[ "$enabled" == "true" ]]; then
        aws lambda update-event-source-mapping \
          --uuid "$uuid" \
          --enabled \
          --region "$REGION" \
          --query '{Function:FunctionArn,Queue:EventSourceArn,State:State}' \
          --output json
      else
        aws lambda update-event-source-mapping \
          --uuid "$uuid" \
          --no-enabled \
          --region "$REGION" \
          --query '{Function:FunctionArn,Queue:EventSourceArn,State:State}' \
          --output json
      fi
      echo "  $fn ($uuid): ${action}"
    done
  done
}

show_status() {
  for fn in "${FUNCTIONS[@]}"; do
    aws lambda list-event-source-mappings \
      --function-name "$fn" \
      --region "$REGION" \
      --query 'EventSourceMappings[?contains(EventSourceArn, `:sqs:`)].{Function:FunctionArn,Queue:EventSourceArn,State:State}' \
      --output table 2>/dev/null || echo "  $fn: not found"
    echo
  done
}

[[ $# -eq 1 ]] || usage

case "$1" in
  start)
    echo "Enabling SQS consumers (ENV=$ENV, region=$REGION)..."
    set_enabled true start
    ;;
  stop)
    echo "Disabling SQS consumers (ENV=$ENV, region=$REGION)..."
    set_enabled false stop
    ;;
  status)
    echo "SQS consumer status (ENV=$ENV, region=$REGION):"
    show_status
    ;;
  *)
    usage
    ;;
esac
