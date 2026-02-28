#!/bin/bash
# Reset DynamoDB user profile for a phone number so you can run onboarding again
# (e.g. to test a different language with the same WhatsApp number).
# Requires: AWS CLI configured, TABLE_NAME (default agrinexus-data).
set -euo pipefail

if [[ -f "$(dirname "$0")/demo.env" ]]; then
  # shellcheck disable=SC1091
  source "$(dirname "$0")/demo.env"
fi

PHONE="${1:-${PHONE_NUMBER:-}}"
TABLE_NAME="${TABLE_NAME:-agrinexus-data}"
REGION="${AWS_REGION:-us-east-1}"

if [[ -z "$PHONE" ]]; then
  echo "Usage: $0 <E.164 phone number>"
  echo "   or: PHONE_NUMBER=+4917647009148 $0"
  echo ""
  echo "Resets DynamoDB profile for this number so you can onboard again (e.g. another language)."
  echo "Optional env: TABLE_NAME (default agrinexus-data), AWS_REGION (default us-east-1)."
  exit 1
fi

# Normalize: remove spaces and ensure + prefix if it looks like international
PHONE="${PHONE// /}"
[[ "$PHONE" =~ ^[0-9]{10,}$ && "$PHONE" != 4* ]] && PHONE="+${PHONE}"

echo "Resetting profile for: ${PHONE}"
echo "Table: ${TABLE_NAME} (${REGION})"
echo ""

# 1. Delete PROFILE
aws dynamodb delete-item \
  --table-name "${TABLE_NAME}" \
  --key "{\"PK\": {\"S\": \"USER#${PHONE}\"}, \"SK\": {\"S\": \"PROFILE\"}}" \
  --region "${REGION}" 2>/dev/null || true
echo "  Deleted PROFILE (if present)."

# 2. Delete all NUDGE# items
NUDGES=$(aws dynamodb query \
  --table-name "${TABLE_NAME}" \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values "{\":pk\": {\"S\": \"USER#${PHONE}\"}, \":sk\": {\"S\": \"NUDGE#\"}}" \
  --region "${REGION}" \
  --output json 2>/dev/null || echo '{"Items":[]}')

COUNT=0
echo "$NUDGES" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('Items', []):
    print(item['PK']['S'] + '|' + item['SK']['S'])
" 2>/dev/null | while IFS='|' read -r pk sk; do
  [[ -z "$pk" || -z "$sk" ]] && continue
  aws dynamodb delete-item \
    --table-name "${TABLE_NAME}" \
    --key "{\"PK\": {\"S\": \"${pk}\"}, \"SK\": {\"S\": \"${sk}\"}}" \
    --region "${REGION}" 2>/dev/null || true
done
echo "  Deleted NUDGE# items."

# 3. Delete all MSG# items
MSGS=$(aws dynamodb query \
  --table-name "${TABLE_NAME}" \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values "{\":pk\": {\"S\": \"USER#${PHONE}\"}, \":sk\": {\"S\": \"MSG#\"}}" \
  --region "${REGION}" \
  --output json 2>/dev/null || echo '{"Items":[]}')

echo "$MSGS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('Items', []):
    print(item['PK']['S'] + '|' + item['SK']['S'])
" 2>/dev/null | while IFS='|' read -r pk sk; do
  [[ -z "$pk" || -z "$sk" ]] && continue
  aws dynamodb delete-item \
    --table-name "${TABLE_NAME}" \
    --key "{\"PK\": {\"S\": \"${pk}\"}, \"SK\": {\"S\": \"${sk}\"}}" \
    --region "${REGION}" 2>/dev/null || true
done
echo "  Deleted MSG# items."

echo ""
echo "Done. You can now onboard again from WhatsApp (e.g. send हिंदी / मराठी / తెలుగు / English)."
