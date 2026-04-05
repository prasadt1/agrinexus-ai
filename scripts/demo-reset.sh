#!/bin/bash
# ─────────────────────────────────────────────────────────────
# AgriNexus AI — Demo Reset Script
# Run this before EACH video recording (Video 1 and Video 2)
# Usage: bash scripts/demo-reset.sh
# ─────────────────────────────────────────────────────────────

set -euo pipefail

PHONE="4917647009148"
TABLE="agrinexus-data"
REGION="us-east-1"
MESSAGE_QUEUE="https://sqs.us-east-1.amazonaws.com/043624892076/agrinexus-messages-dev.fifo"
VOICE_QUEUE="https://sqs.us-east-1.amazonaws.com/043624892076/agrinexus-voice-dev.fifo"
WEATHER_LAMBDA="agrinexus-weather-dev"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║      AgriNexus AI — Demo Reset               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── STEP 1: Delete PROFILE ─────────────────────────────────
echo "▶ Step 1/5 — Deleting user profile..."
aws dynamodb delete-item \
  --table-name "$TABLE" \
  --region "$REGION" \
  --key "{\"PK\":{\"S\":\"USER#${PHONE}\"},\"SK\":{\"S\":\"PROFILE\"}}" \
  2>/dev/null && echo "  ✓ PROFILE deleted" || echo "  ✓ No profile found (already clean)"

# ── STEP 2: Delete all MSG + NUDGE records ─────────────────
echo ""
echo "▶ Step 2/5 — Cleaning MSG and NUDGE records..."
RECORDS=$(aws dynamodb query \
  --table-name "$TABLE" \
  --region "$REGION" \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values "{\":pk\":{\"S\":\"USER#${PHONE}\"}}" \
  --query "Items[*].SK.S" \
  --output json 2>/dev/null || echo "[]")

COUNT=$(echo "$RECORDS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

if [ "$COUNT" -gt 0 ]; then
  echo "$RECORDS" | python3 -c "
import json, sys, subprocess
sks = json.load(sys.stdin)
for sk in sks:
    subprocess.run([
        'aws', 'dynamodb', 'delete-item',
        '--table-name', '${TABLE}',
        '--region', '${REGION}',
        '--key', json.dumps({'PK':{'S':'USER#${PHONE}'},'SK':{'S':sk}})
    ], capture_output=True)
print(f'  ✓ Deleted {len(sks)} records')
"
else
  echo "  ✓ No records found (already clean)"
fi

# ── STEP 3: Purge SQS queues ───────────────────────────────
echo ""
echo "▶ Step 3/5 — Purging SQS queues..."
aws sqs purge-queue \
  --queue-url "$MESSAGE_QUEUE" \
  --region "$REGION" 2>/dev/null && echo "  ✓ Message queue purged" || echo "  ⚠ Message queue purge failed (may need 60s cooldown)"

aws sqs purge-queue \
  --queue-url "$VOICE_QUEUE" \
  --region "$REGION" 2>/dev/null && echo "  ✓ Voice queue purged" || echo "  ⚠ Voice queue purge failed (may need 60s cooldown)"

# ── STEP 4: Verify clean state ─────────────────────────────
echo ""
echo "▶ Step 4/5 — Verifying clean state..."
REMAINING=$(aws dynamodb query \
  --table-name "$TABLE" \
  --region "$REGION" \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values "{\":pk\":{\"S\":\"USER#${PHONE}\"}}" \
  --query "Count" \
  --output text 2>/dev/null || echo "?")

if [ "$REMAINING" = "0" ]; then
  echo "  ✓ DynamoDB clean — 0 records for this number"
else
  echo "  ⚠ Warning: $REMAINING records still found — check manually"
fi

# ── STEP 5: Confirm Lambda is live ─────────────────────────
echo ""
echo "▶ Step 5/5 — Confirming system is live..."
RESULT=$(aws lambda invoke \
  --function-name "$WEATHER_LAMBDA" \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  --region "$REGION" \
  /tmp/agrinexus-health-check.json 2>/dev/null && cat /tmp/agrinexus-health-check.json)

if echo "$RESULT" | grep -q "favorable"; then
  echo "  ✓ WeatherPoller live — Latur conditions favorable for nudge demo"
elif echo "$RESULT" | grep -q "statusCode"; then
  echo "  ✓ Lambda responding"
else
  echo "  ⚠ Lambda check inconclusive — check manually"
fi

# ── DONE ───────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅  Ready to record!                        ║"
echo "║                                              ║"
echo "║  1. Open WhatsApp Web → web.whatsapp.com     ║"
echo "║  2. Open AWS Console → Step Functions        ║"
echo "║  3. Open Terminal in project root            ║"
echo "║  4. QuickTime → New Screen Recording         ║"
echo "║  5. Do Not Disturb ON on Mac + iPhone        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
