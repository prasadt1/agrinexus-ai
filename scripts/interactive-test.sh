#!/bin/bash
set -euo pipefail

# Interactive test script for AgriNexus AI
# Tests full onboarding → nudge → response cycle in any language

if [[ -f "$(dirname "$0")/demo.env" ]]; then
  source "$(dirname "$0")/demo.env"
fi

PHONE="${PHONE_NUMBER:-}"
LANG="hi"
TABLE_NAME="${TABLE_NAME:-agrinexus-data}"
REGION="${AWS_REGION:-us-east-1}"
WEATHER_LAMBDA="${WEATHER_LAMBDA:-agrinexus-weather-dev}"
STATE_MACHINE_ARN="${STATE_MACHINE_ARN:-}"

function usage() {
  echo "Usage: $0 --phone <E.164> --lang <hi|mr|te|en>"
  echo "Example: $0 --phone +4917647009148 --lang hi"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phone) PHONE="$2"; shift 2;;
    --lang) LANG="$2"; shift 2;;
    *) usage;;
  esac
done

if [[ -z "$PHONE" ]]; then
  usage
fi

# Language-specific messages
case "$LANG" in
  hi)
    HELLO="नमस्ते or हिंदी"
    DONE="हो गया"
    NOT_YET="अभी नहीं"
    SAMPLE_Q="कपास में गुलाबी सुंडी का इलाज क्या है?"
    ;;
  mr)
    HELLO="नमस्कार or मराठी"
    DONE="झाला"
    NOT_YET="नाही झाला"
    SAMPLE_Q="कापसात गुलाबी अळी नियंत्रण कसे करावे?"
    ;;
  te)
    HELLO="నమస్కారం or తెలుగు"
    DONE="అయ్యింది"
    NOT_YET="ఇంకా లేదు"
    SAMPLE_Q="పత్తిలో గులాబీ పురుగు నియంత్రణ ఎలా చేయాలి?"
    ;;
  en)
    HELLO="Hello or English"
    DONE="DONE"
    NOT_YET="NOT YET"
    SAMPLE_Q="How to control pink bollworm in cotton?"
    ;;
  *)
    echo "Unsupported language: $LANG"
    exit 1
    ;;
esac

function reset_user_data() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🔄 STEP 1: Resetting user data for ${PHONE}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  python3 - <<PY
import boto3
from boto3.dynamodb.conditions import Key

phone = "${PHONE}"
table_name = "${TABLE_NAME}"
region = "${REGION}"

session = boto3.session.Session(region_name=region)
dynamodb = session.resource('dynamodb')
table = dynamodb.Table(table_name)

# Delete PROFILE
try:
    table.delete_item(Key={'PK': f'USER#{phone}', 'SK': 'PROFILE'})
    print(f"✓ Deleted PROFILE")
except Exception as e:
    print(f"  (No existing PROFILE)")

# Delete all NUDGEs
resp = table.query(
    KeyConditionExpression=Key('PK').eq(f'USER#{phone}') & Key('SK').begins_with('NUDGE#')
)
items = resp.get('Items', [])
count = 0
while True:
    for item in items:
        table.delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
        count += 1
    if 'LastEvaluatedKey' in resp:
        resp = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{phone}') & Key('SK').begins_with('NUDGE#'),
            ExclusiveStartKey=resp['LastEvaluatedKey']
        )
        items = resp.get('Items', [])
    else:
        break

if count > 0:
    print(f"✓ Deleted {count} nudge(s)")
else:
    print(f"  (No existing nudges)")

print(f"\n✓ User data reset complete")
PY
  
  echo ""
  read -p "Press ENTER to continue..."
}

function prompt_onboarding() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📱 STEP 2: Complete onboarding via WhatsApp"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Open WhatsApp on ${PHONE} and send these messages:"
  echo ""
  echo "  1️⃣  Send: Hello or Namaste"
  echo "      (Bot will show welcome with language buttons)"
  echo ""
  echo "  2️⃣  Send: Your district name (e.g., Aurangabad)"
  echo "      (Bot will ask for district)"
  echo ""
  echo "  3️⃣  Send: Cotton"
  echo "      (Bot will ask for crop)"
  echo ""
  echo "  4️⃣  Send: Yes"
  echo "      (Bot will confirm onboarding complete)"
  echo ""
  read -p "Press ENTER when onboarding is complete..."
}

function trigger_nudge() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🔔 STEP 3: Triggering weather-based nudge"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Invoking weather poller to generate nudge..."
  
  aws lambda invoke \
    --function-name "$WEATHER_LAMBDA" \
    --payload '{}' \
    /tmp/weather-response.json >/dev/null 2>&1
  
  echo "✓ Weather poller invoked"
  echo ""
  echo "⏳ Waiting 5 seconds for nudge to be sent..."
  sleep 5
  
  echo ""
  echo "📱 Check WhatsApp - you should receive a nudge message"
  echo "   (e.g., 'Spray recommended for pink bollworm control')"
  echo ""
  read -p "Press ENTER when you receive the nudge..."
}

function prompt_done_response() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "✅ STEP 4: Testing DONE response"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Send this message via WhatsApp:"
  echo ""
  echo "  📤 Send: ${DONE}"
  echo ""
  echo "Expected: Bot confirms task completion, no more reminders"
  echo ""
  read -p "Press ENTER after sending DONE..."
  
  echo ""
  echo "⏳ Waiting 3 seconds for response detector to process..."
  sleep 3
  
  echo "✓ DONE response should be processed"
  echo "  Check WhatsApp for confirmation message"
}

function prompt_not_yet_response() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "⏰ STEP 4 (Alternative): Testing NOT YET response"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Send this message via WhatsApp:"
  echo ""
  echo "  📤 Send: ${NOT_YET}"
  echo ""
  echo "Expected: Bot acknowledges, will send reminder in 24h"
  echo ""
  read -p "Press ENTER after sending NOT YET..."
  
  echo ""
  echo "⏳ Waiting 3 seconds for response detector to process..."
  sleep 3
  
  echo "✓ NOT YET response should be processed"
  echo "  Check WhatsApp for acknowledgment"
  echo ""
  echo "To test reminder (without waiting 24h):"
  echo "  Run: aws lambda invoke --function-name agrinexus-reminder-dev --payload '{}' /tmp/out.json"
}

function prompt_question() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "❓ STEP 5: Testing RAG question-answering"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Send a farming question via WhatsApp:"
  echo ""
  echo "  📤 Example: ${SAMPLE_Q}"
  echo ""
  echo "Expected: Bot provides detailed answer with source citations"
  echo ""
  read -p "Press ENTER after sending question..."
  
  echo ""
  echo "⏳ Waiting for RAG processing (may take 5-10 seconds)..."
  sleep 3
  
  echo "✓ Question should be processed"
  echo "  Check WhatsApp for detailed answer"
}

function show_summary() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "✅ TEST COMPLETE"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "You have tested:"
  echo "  ✓ User data reset"
  echo "  ✓ Onboarding flow (language → district → crop → consent)"
  echo "  ✓ Weather-based nudge generation"
  echo "  ✓ DONE/NOT YET response handling"
  echo "  ✓ RAG-based question answering"
  echo ""
  echo "To test in another language, run:"
  echo "  $0 --phone ${PHONE} --lang <hi|mr|te|en>"
  echo ""
  echo "To view CloudWatch metrics:"
  echo "  Open: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AgriNexus-Operations-dev"
  echo ""
}

# Main flow
clear
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║         AgriNexus AI - Interactive Test Script                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Phone: ${PHONE}"
echo "Language: ${LANG}"
echo ""

reset_user_data
prompt_onboarding
trigger_nudge

echo ""
echo "Choose response type:"
echo "  1) DONE (task completed)"
echo "  2) NOT YET (will do later)"
read -p "Enter choice (1 or 2): " choice

case "$choice" in
  1) prompt_done_response;;
  2) prompt_not_yet_response;;
  *) echo "Invalid choice, skipping response test";;
esac

prompt_question
show_summary
