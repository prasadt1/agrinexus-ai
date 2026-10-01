#!/usr/bin/env bash
# Reset WhatsApp demo user and optionally run as a re:Invent visitor (unknown number).
#
# Usage:
#   ./scripts/reset-onboard-and-demo.sh --phone 4917647009148
#   ./scripts/reset-onboard-and-demo.sh --phone 49176... --as-visitor
#   ./scripts/reset-onboard-and-demo.sh --phone 49176... --restore
#
# --as-visitor
#   Deletes PROFILE / MSG / NUDGE / visitor counters for the number, removes the
#   DynamoDB allowlist row, and strips the number from live Lambda env
#   BETA_PHONES and RATE_LIMIT_BYPASS_PHONES (webhook + processors).
#   Does NOT run sam deploy. Mutates live function configuration.
#
# --restore
#   Re-adds the number to allowlist and to BETA_PHONES / RATE_LIMIT_BYPASS_PHONES
#   on webhook + processors (merges with existing lists).
#
# Required env (or scripts/demo.env): WEBHOOK_URL optional for onboard send;
# AWS credentials for DynamoDB + Lambda UpdateFunctionConfiguration.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
if [[ -f "$ROOT/demo.env" ]]; then
  source "$ROOT/demo.env"
fi

PHONE="${PHONE_NUMBER:-}"
MODE="reset"
ENVIRONMENT="${ENVIRONMENT:-dev}"
REGION="${AWS_REGION:-us-east-1}"
TABLE_NAME="${TABLE_NAME:-agrinexus-data}"
WEBHOOK_FN="agrinexus-webhook-${ENVIRONMENT}"
PROCESSOR_FN="agrinexus-processor-${ENVIRONMENT}"
PROCESSOR_BETA_FN="agrinexus-processor-beta-${ENVIRONMENT}"

usage() {
  echo "Usage: $0 --phone <digits> [--as-visitor|--restore]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phone) PHONE="$2"; shift 2;;
    --as-visitor) MODE="as-visitor"; shift;;
    --restore) MODE="restore"; shift;;
    -h|--help) usage; exit 0;;
    *) usage; exit 1;;
  esac
done

PHONE="${PHONE#+}"
if [[ -z "$PHONE" ]]; then
  usage
  exit 1
fi

delete_user_rows() {
  echo "Deleting DynamoDB rows for USER#${PHONE} ..."
  DELETE_CONFIRM=yes "$ROOT/delete-user-data.sh" --yes "$PHONE"
  # visitor counters for today
  DAY=$(date -u +%Y-%m-%d)
  aws dynamodb delete-item --region "$REGION" --table-name "$TABLE_NAME" \
    --key "{\"PK\":{\"S\":\"COUNTER#visitor#${PHONE}\"},\"SK\":{\"S\":\"DAY#${DAY}\"}}" >/dev/null 2>&1 || true
}

remove_allowlist() {
  echo "Removing allowlist row ..."
  aws dynamodb delete-item --region "$REGION" --table-name "$TABLE_NAME" \
    --key "{\"PK\":{\"S\":\"ALLOWLIST\"},\"SK\":{\"S\":\"USER#${PHONE}\"}}" >/dev/null
}

add_allowlist() {
  echo "Adding allowlist row ..."
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  aws dynamodb put-item --region "$REGION" --table-name "$TABLE_NAME" \
    --item "{\"PK\":{\"S\":\"ALLOWLIST\"},\"SK\":{\"S\":\"USER#${PHONE}\"},\"approved\":{\"BOOL\":true},\"approved_at\":{\"S\":\"${NOW}\"}}" >/dev/null
}

# Remove PHONE from a comma-separated env value
strip_phone_from_csv() {
  local csv="$1"
  python3 - "$PHONE" "$csv" <<'PY'
import sys
phone, csv = sys.argv[1], sys.argv[2]
parts = [p.strip() for p in (csv or "").split(",") if p.strip() and p.strip() != phone]
print(",".join(parts))
PY
}

add_phone_to_csv() {
  local csv="$1"
  python3 - "$PHONE" "$csv" <<'PY'
import sys
phone, csv = sys.argv[1], sys.argv[2]
parts = [p.strip() for p in (csv or "").split(",") if p.strip()]
if phone not in parts:
    parts.append(phone)
print(",".join(parts))
PY
}

update_lambda_lists() {
  local fn="$1"
  local op="$2"  # strip|add
  echo "Updating Lambda env on ${fn} (${op}) ..."
  local conf
  conf=$(aws lambda get-function-configuration --region "$REGION" --function-name "$fn" --output json)
  local beta bypass
  beta=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Environment"]["Variables"].get("BETA_PHONES",""))' <<<"$conf")
  bypass=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Environment"]["Variables"].get("RATE_LIMIT_BYPASS_PHONES",""))' <<<"$conf")
  if [[ "$op" == "strip" ]]; then
    beta=$(strip_phone_from_csv "$beta")
    bypass=$(strip_phone_from_csv "$bypass")
  else
    beta=$(add_phone_to_csv "$beta")
    bypass=$(add_phone_to_csv "$bypass")
  fi
  # Merge into full Variables map
  python3 - "$conf" "$beta" "$bypass" > /tmp/agrinexus-lambda-env.json <<'PY'
import json, sys
conf = json.loads(sys.argv[1])
vars = dict(conf.get("Environment", {}).get("Variables") or {})
vars["BETA_PHONES"] = sys.argv[2]
vars["RATE_LIMIT_BYPASS_PHONES"] = sys.argv[3]
json.dump({"Variables": vars}, sys.stdout)
PY
  aws lambda update-function-configuration --region "$REGION" --function-name "$fn" \
    --environment "file:///tmp/agrinexus-lambda-env.json" >/dev/null
  rm -f /tmp/agrinexus-lambda-env.json
}

case "$MODE" in
  reset)
    delete_user_rows
    echo "Reset complete. Send a WhatsApp message to re-onboard as a farmer."
    ;;
  as-visitor)
    delete_user_rows
    remove_allowlist
    update_lambda_lists "$WEBHOOK_FN" strip
    update_lambda_lists "$PROCESSOR_FN" strip || true
    update_lambda_lists "$PROCESSOR_BETA_FN" strip || true
    echo ""
    echo "Visitor mode ready for ${PHONE}."
    echo "NOTE: This is a reset number, not a brand-new MSISDN."
    echo "WARNING: Do not run sam deploy between --as-visitor and --restore."
    echo "         A deploy restores BETA_PHONES / RATE_LIMIT_BYPASS_PHONES from"
    echo "         template parameters and silently re-allowlists this number,"
    echo "         which invalidates the visitor acceptance run."
    echo "From WhatsApp send: Hi from re:Invent"
    echo "When finished: $0 --phone ${PHONE} --restore"
    ;;
  restore)
    add_allowlist
    update_lambda_lists "$WEBHOOK_FN" add
    update_lambda_lists "$PROCESSOR_FN" add || true
    update_lambda_lists "$PROCESSOR_BETA_FN" add || true
    echo "Restored allowlist + BETA_PHONES + RATE_LIMIT_BYPASS_PHONES for ${PHONE}."
    ;;
esac
