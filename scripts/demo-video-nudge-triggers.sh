#!/usr/bin/env bash
# Automate demo nudge invokes so you can record on phone without copy-pasting NUDGE_ID.
# Prereq: AWS CLI configured, same account/region as Lambdas.
#
# Set PHONE to your WhatsApp E.164 digits without + (same as Dynamo PK USER#...).
# Optional local cheat-sheet (gitignored): docs/demo/TRIGGER-COMMANDS.md
# Default PROFILE demo_tier after onboarding is often "public" (one contextual nudge);
# cmd_profile() sets "full" for closed-loop reminder demos.
#
# Usage:
#   ./scripts/demo-video-nudge-triggers.sh profile # Latur + Wheat + full tier (optional)
#   ./scripts/demo-video-nudge-triggers.sh first      # first nudge → check WhatsApp
#   ./scripts/demo-video-nudge-triggers.sh 24         # T+24h (uses latest NUDGE# for your phone)
#   ./scripts/demo-video-nudge-triggers.sh 48         # T+48h
#   ./scripts/demo-video-nudge-triggers.sh guided # first → wait Enter → 24 → wait Enter → 48
#
# Env overrides:
#   PHONE=1555123456789  REGION=us-east-1  ENV=dev
#   TABLE=agrinexus-data
#   NUDGE_FN=agrinexus-nudge-sender-dev#   REMINDER_FN=agrinexus-reminder-dev

set -euo pipefail

PHONE="${PHONE:-}"
REGION="${REGION:-us-east-1}"
ENV="${ENV:-dev}"
TABLE="${TABLE:-agrinexus-data}"
NUDGE_FN="${NUDGE_FN:-agrinexus-nudge-sender-${ENV}}"
REMINDER_FN="${REMINDER_FN:-agrinexus-reminder-${ENV}}"

PK="USER#${PHONE}"

die() { echo "ERROR: $*" >&2; exit 1; }

require_phone() {
  [[ -n "$PHONE" ]] || die "Set PHONE to WhatsApp E.164 digits without + (example: export PHONE=1555123456789)"
}

require_aws() {
  command -v aws >/dev/null 2>&1 || die "aws CLI not found"
}

cmd_profile() {
  require_phone
  require_aws
  echo "Updating PROFILE for $PK (Latur, Wheat, full)..."
  aws dynamodb update-item \
    --table-name "$TABLE" \
    --key "{\"PK\":{\"S\":\"$PK\"},\"SK\":{\"S\":\"PROFILE\"}}" \
    --update-expression "SET district = :dist, crop = :crop, demo_tier = :tier, #loc = :loc" \
    --expression-attribute-names '{"#loc":"location"}' \
    --expression-attribute-values "{\":dist\":{\"S\":\"Latur\"},\":crop\":{\"S\":\"Wheat\"},\":tier\":{\"S\":\"full\"},\":loc\":{\"S\":\"Latur\"}}" \
    --region "$REGION"
  echo "OK."
}

cmd_first() {
  require_phone
  require_aws
  echo "Invoking $NUDGE_FN (first nudge, Latur)..."
  aws lambda invoke \
    --function-name "$NUDGE_FN" \
    --cli-binary-format raw-in-base64-out \
    --payload '{"location":"Latur","activity":"spray","weather":{"temp":28,"humidity":65,"wind_speed":8,"conditions":"clear"}}' \
    --region "$REGION" \
    /tmp/nudge-response.json >/dev/null
  cat /tmp/nudge-response.json
  echo ""
  echo "Check WhatsApp on +$PHONE in ~10–30s."
}

latest_nudge_id() {
  require_phone
  require_aws
  local sk
  sk="$(aws dynamodb query \
    --table-name "$TABLE" \
    --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
    --expression-attribute-values "{\":pk\":{\"S\":\"$PK\"},\":sk\":{\"S\":\"NUDGE#\"}}" \
    --region "$REGION" \
    --query 'Items[-1].SK.S' \
    --output text 2>/dev/null || true)"
  if [[ -z "$sk" || "$sk" == "None" ]]; then
    die "No NUDGE# item for $PK. Run: $0 first   (and ensure user is allowlisted / on LOCATION#Latur)"
  fi
  echo "${sk#NUDGE#}"
}

cmd_reminder() {
  local rtype="$1"
  require_aws
  local nid
  nid="$(latest_nudge_id)"
  echo "Using nudge_id: $nid"
  echo "Invoking $REMINDER_FN ($rtype)..."
  aws lambda invoke \
    --function-name "$REMINDER_FN" \
    --cli-binary-format raw-in-base64-out \
    --payload "{\"phone_number\":\"$PHONE\",\"nudge_id\":\"$nid\",\"reminder_type\":\"$rtype\",\"dialect\":\"hi\",\"district\":\"Latur\",\"crop\":\"Wheat\"}" \
    --region "$REGION" \
    /tmp/reminder-response.json >/dev/null
  cat /tmp/reminder-response.json
  echo ""
  echo "Check WhatsApp."
}

cmd_guided() {
  cmd_first
  echo ""
  read -r -p "Record text/voice/vision, then press Enter to send T+24h reminder..."
  cmd_reminder "T+24h"
  echo ""
  read -r -p "Press Enter to send T+48h reminder (or Ctrl+C to skip)..."
  cmd_reminder "T+48h"
}

usage() {
  cat <<EOF
Demo video nudge triggers (phone: $PHONE)

 profile   Set DynamoDB PROFILE: Latur, Wheat, demo_tier=full
  first     Send first nudge (direct nudge-sender invoke)
  24        Send T+24h reminder (latest NUDGE# for this phone)
  48 Send T+48h reminder
  guided    first → wait Enter → 24 → wait Enter → 48

Override: PHONE=... REGION=us-east-1 ENV=dev $0 first
EOF
}

main() {
  case "${1:-}" in
    profile) cmd_profile ;;
    first|1) cmd_first ;;
    24|t24|T+24h) cmd_reminder "T+24h" ;;
    48|t48|T+48h) cmd_reminder "T+48h" ;;
    guided|guide|g) cmd_guided ;;
    ""|-h|--help|help) usage ;;
    *) die "Unknown command: $1. Try: $0 help" ;;
  esac
}

main "$@"
