#!/bin/bash
# Send reminder to the most recent active nudge
# Usage: bash scripts/send-reminder.sh [T+24h|T+48h]

PHONE="4917647009148"
REMINDER_TYPE="${1:-T+24h}"
REGION="us-east-1"

echo "Looking up latest active nudge for $PHONE..."

NUDGE_SK=$(aws dynamodb query \
  --table-name agrinexus-data \
  --region $REGION \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values "{\":pk\":{\"S\":\"USER#$PHONE\"},\":sk\":{\"S\":\"NUDGE#\"}}" \
  --query "Items[?Status!='DONE'] | Items[0].SK.S" --output text 2>/dev/null)

# Simpler fallback: just get the latest nudge SK
if [ -z "$NUDGE_SK" ] || [ "$NUDGE_SK" == "None" ] || [ "$NUDGE_SK" == "null" ]; then
  NUDGE_SK=$(aws dynamodb query \
    --table-name agrinexus-data \
    --region $REGION \
    --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
    --expression-attribute-values "{\":pk\":{\"S\":\"USER#$PHONE\"},\":sk\":{\"S\":\"NUDGE#\"}}" \
    --query "Items[-1].SK.S" --output text)
fi

if [ -z "$NUDGE_SK" ] || [ "$NUDGE_SK" == "None" ] || [ "$NUDGE_SK" == "null" ]; then
  echo "No nudge found. Fire the weather poller first."
  exit 1
fi

NUDGE_ID="${NUDGE_SK#NUDGE#}"
echo "Found nudge: $NUDGE_ID"
echo "Sending $REMINDER_TYPE reminder..."

aws lambda invoke \
  --function-name agrinexus-reminder-dev \
  --payload "{\"phone_number\":\"$PHONE\",\"nudge_id\":\"$NUDGE_ID\",\"reminder_type\":\"$REMINDER_TYPE\"}" \
  --cli-binary-format raw-in-base64-out \
  /tmp/reminder-out.json --region $REGION > /dev/null

cat /tmp/reminder-out.json
