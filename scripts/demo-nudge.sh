#!/bin/bash
# AgriNexus AI — Nudge Demo Script
# Single terminal, sequential steps, press ENTER to advance
# CloudWatch tail runs in background, output prints inline

PHONE="4917647009148"
REGION="us-east-1"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pause() {
  echo ""
  echo -e "${YELLOW}▶ $1${NC}"
  read -p "   Press ENTER when ready..."
  echo ""
}

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}   AgriNexus AI — Nudge Loop Demo${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── STEP 1: Start CloudWatch tail in background ──
echo ""
echo -e "${GREEN}[1/4] Starting CloudWatch live tail in background...${NC}"
aws logs tail /aws/lambda/agrinexus-response-detector-dev \
  --follow --region $REGION &
CW_PID=$!
sleep 2
echo -e "${GREEN}      ✓ Tail running (PID $CW_PID) — output will appear below${NC}"

# ── STEP 2: Fire weather poller ──
pause "STEP 2 — Fire WeatherPoller → nudge will arrive on WhatsApp"

echo -e "${GREEN}[2/4] Invoking WeatherPoller...${NC}"
aws lambda invoke --function-name agrinexus-weather-dev \
  --payload '{}' --cli-binary-format raw-in-base64-out \
  /tmp/w.json --region $REGION > /dev/null
cat /tmp/w.json
echo ""
echo -e "${GREEN}      ✓ Nudge sent — check WhatsApp now${NC}"

# ── STEP 3: Send reminder ──
pause "STEP 3 — Simulate T+24h reminder (farmer didn't respond)"

echo -e "${GREEN}[3/4] Sending T+24h reminder...${NC}"
NUDGE_SK=$(aws dynamodb query \
  --table-name agrinexus-data \
  --region $REGION \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values "{\":pk\":{\"S\":\"USER#$PHONE\"},\":sk\":{\"S\":\"NUDGE#\"}}" \
  --query "Items[-1].SK.S" --output text)

NUDGE_ID="${NUDGE_SK#NUDGE#}"
echo "   Nudge ID: $NUDGE_ID"

aws lambda invoke \
  --function-name agrinexus-reminder-dev \
  --payload "{\"phone_number\":\"$PHONE\",\"nudge_id\":\"$NUDGE_ID\",\"reminder_type\":\"T+24h\"}" \
  --cli-binary-format raw-in-base64-out \
  /tmp/reminder-out.json --region $REGION > /dev/null
cat /tmp/reminder-out.json
echo ""
echo -e "${GREEN}      ✓ Reminder sent — check WhatsApp now${NC}"

# ── STEP 4: Wait for Done ──
pause "STEP 4 — Tap DONE on WhatsApp now, watch CloudWatch output below"

echo -e "${GREEN}[4/4] Watching for DONE response via CloudWatch tail...${NC}"
echo -e "${CYAN}      (CloudWatch output will appear below in real time)${NC}"
echo ""
sleep 10

# ── Cleanup ──
echo ""
echo -e "${GREEN}✓ Demo complete. Stopping CloudWatch tail...${NC}"
kill $CW_PID 2>/dev/null
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
