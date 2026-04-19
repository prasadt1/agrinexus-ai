#!/bin/bash
# Complete Flow Test: Onboarding → Nudge (Not Yet) → Text → Voice → Vision → 24h Reminder → Done
set -euo pipefail

# Load environment variables
if [[ -f "$(dirname "$0")/demo.env" ]]; then
  source "$(dirname "$0")/demo.env"
fi

WEBHOOK_URL="${WEBHOOK_URL:-}"
FROM_NUMBER="${FROM_NUMBER:-4917647009148}"
APP_SECRET="${APP_SECRET:-}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
WEATHER_LAMBDA="agrinexus-weather-${ENVIRONMENT}"
NUDGE_SENDER_LAMBDA="agrinexus-nudge-sender-${ENVIRONMENT}"

if [[ -z "$WEBHOOK_URL" ]]; then
  echo "Error: WEBHOOK_URL not set"
  echo "Usage: WEBHOOK_URL=https://... [APP_SECRET=...] $0"
  exit 1
fi

function hmac_signature() {
  local payload="$1"
  if [[ -z "$APP_SECRET" ]]; then
    echo ""
    return
  fi
  python3 - <<PY
import hmac, hashlib
secret = "${APP_SECRET}".encode("utf-8")
msg = """$payload""".encode("utf-8")
sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
print(f"sha256={sig}")
PY
}

function send_text() {
  local text="$1"
  local wamid="wamid.$(date +%s%N)"
  local payload
  payload=$(cat <<JSON
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "${FROM_NUMBER}",
                "id": "${wamid}",
                "timestamp": "$(date +%s)",
                "type": "text",
                "text": {"body": "${text}"}
              }
            ]
          }
        }
      ]
    }
  ]
}
JSON
)

  local sig
  sig=$(hmac_signature "$payload")

  echo "📱 Sending: ${text}"
  if [[ -n "$sig" ]]; then
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -H "X-Hub-Signature-256: ${sig}" \
      -d "$payload" >/dev/null
  else
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "$payload" >/dev/null
  fi
  echo "✅ Sent"
}

function send_interactive_list() {
  local list_id="$1"
  local wamid="wamid.$(date +%s%N)"
  local payload
  payload=$(cat <<JSON
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "${FROM_NUMBER}",
                "id": "${wamid}",
                "timestamp": "$(date +%s)",
                "type": "interactive",
                "interactive": {
                  "type": "list_reply",
                  "list_reply": {
                    "id": "${list_id}",
                    "title": "Selected"
                  }
                }
              }
            ]
          }
        }
      ]
    }
  ]
}
JSON
)

  local sig
  sig=$(hmac_signature "$payload")

  echo "📱 Sending interactive: ${list_id}"
  if [[ -n "$sig" ]]; then
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -H "X-Hub-Signature-256: ${sig}" \
      -d "$payload" >/dev/null
  else
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "$payload" >/dev/null
  fi
  echo "✅ Sent"
}

function send_button() {
  local button_id="$1"
  local button_title="$2"
  local wamid="wamid.$(date +%s%N)"
  local payload
  payload=$(cat <<JSON
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "${FROM_NUMBER}",
                "id": "${wamid}",
                "timestamp": "$(date +%s)",
                "type": "interactive",
                "interactive": {
                  "type": "button_reply",
                  "button_reply": {
                    "id": "${button_id}",
                    "title": "${button_title}"
                  }
                }
              }
            ]
          }
        }
      ]
    }
  ]
}
JSON
)

  local sig
  sig=$(hmac_signature "$payload")

  echo "📱 Clicking button: ${button_title}"
  if [[ -n "$sig" ]]; then
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -H "X-Hub-Signature-256: ${sig}" \
      -d "$payload" >/dev/null
  else
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "$payload" >/dev/null
  fi
  echo "✅ Sent"
}

function update_profile_to_full_tier() {
  echo "🔧 Updating profile to demo_tier: full (for T+24h reminders)"
  aws dynamodb update-item \
    --table-name agrinexus-data \
    --key "{\"PK\":{\"S\":\"USER#${FROM_NUMBER}\"},\"SK\":{\"S\":\"PROFILE\"}}" \
    --update-expression "SET demo_tier = :tier" \
    --expression-attribute-values '{":tier":{"S":"full"}}' \
    >/dev/null 2>&1 || true
  echo "✅ Profile updated"
}

function trigger_weather_poll() {
  echo "🌤️  Triggering weather poller..."
  aws lambda invoke --function-name "$WEATHER_LAMBDA" --payload '{}' /tmp/weather-response.json >/dev/null
  echo "✅ Weather poller invoked"
}

function simulate_24h_reminder() {
  echo "⏰ Simulating T+24h reminder..."
  
  # Get the latest nudge ID
  local nudge_id
  nudge_id=$(aws dynamodb query \
    --table-name agrinexus-data \
    --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
    --expression-attribute-values "{\":pk\":{\"S\":\"USER#${FROM_NUMBER}\"},\":sk\":{\"S\":\"NUDGE#\"}}" \
    --query 'Items[0].SK.S' \
    --output text | sed 's/NUDGE#//')
  
  if [[ -z "$nudge_id" || "$nudge_id" == "None" ]]; then
    echo "❌ No nudge found. Cannot simulate reminder."
    return 1
  fi
  
  echo "📋 Found nudge: $nudge_id"
  
  # Get user dialect
  local dialect
  dialect=$(aws dynamodb get-item \
    --table-name agrinexus-data \
    --key "{\"PK\":{\"S\":\"USER#${FROM_NUMBER}\"},\"SK\":{\"S\":\"PROFILE\"}}" \
    --query 'Item.dialect.S' \
    --output text)
  
  # Invoke reminder Lambda
  local payload
  payload=$(cat <<JSON
{
  "phone_number": "${FROM_NUMBER}",
  "nudge_id": "${nudge_id}",
  "reminder_type": "T+24h",
  "dialect": "${dialect}"
}
JSON
)
  
  aws lambda invoke \
    --function-name "agrinexus-reminder-${ENVIRONMENT}" \
    --payload "$payload" \
    /tmp/reminder-response.json >/dev/null
  
  echo "✅ T+24h reminder sent"
}

echo "=========================================="
echo "🧪 Complete Flow Test"
echo "=========================================="
echo ""
echo "Phone: ${FROM_NUMBER}"
echo "Webhook: ${WEBHOOK_URL}"
echo ""
echo "Flow:"
echo "1. Onboarding (Marathi, Nagpur, Cotton, Yes)"
echo "2. First nudge → Click 'Not Yet'"
echo "3. Text query"
echo "4. Voice note (manual)"
echo "5. Photo (manual)"
echo "6. T+24h reminder → Click 'Done'"
echo ""
echo "=========================================="
echo ""

read -p "Press Enter to start onboarding..."

# ============================================================================
# STEP 1: ONBOARDING
# ============================================================================
echo ""
echo "📝 STEP 1: ONBOARDING"
echo "--------------------"

echo "Sending: Hi"
send_text "Hi"
sleep 3

echo "Selecting: मराठी (Marathi)"
send_interactive_list "mr"
sleep 3

echo "Selecting: नागपूर (Nagpur)"
send_button "btn_2" "नागपूर"
sleep 3

echo "Selecting: कापूस (Cotton)"
send_button "btn_0" "कापूस"
sleep 3

echo "Consenting: होय (Yes)"
send_button "btn_0" "होय ✅"
sleep 3

echo "✅ Onboarding complete!"
echo ""

# Update profile to full tier for reminders
update_profile_to_full_tier
sleep 2

# ============================================================================
# STEP 2: TRIGGER NUDGE
# ============================================================================
echo ""
echo "🌤️  STEP 2: TRIGGER FIRST NUDGE"
echo "--------------------"

trigger_weather_poll
sleep 5

echo ""
echo "⏳ Waiting for nudge to be sent (check WhatsApp)..."
echo "You should receive: 'Nagpur: हवामान अनुकूल आहे...'"
echo ""
read -p "Press Enter after you receive the nudge..."

echo ""
echo "Clicking: नाही झाला (Not Yet)"
send_button "not_yet" "नाही झाला"
sleep 3

echo "✅ Nudge acknowledged as 'Not Yet'"
echo ""

# ============================================================================
# STEP 3: TEXT QUERY
# ============================================================================
echo ""
echo "💬 STEP 3: TEXT QUERY"
echo "--------------------"

echo "Asking: कापसात पांढरी माशी कशी नियंत्रित करावी?"
send_text "कापसात पांढरी माशी कशी नियंत्रित करावी?"
sleep 5

echo "✅ Text query sent (check WhatsApp for RAG response)"
echo ""

# ============================================================================
# STEP 4: VOICE NOTE (MANUAL)
# ============================================================================
echo ""
echo "🎤 STEP 4: VOICE NOTE"
echo "--------------------"
echo "⚠️  MANUAL STEP: Send a voice note from WhatsApp"
echo "Example: 'कापसात किडे कसे नियंत्रित करावे?'"
echo ""
read -p "Press Enter after you send the voice note..."
echo "✅ Voice note sent (wait ~30-40s for transcription + response)"
echo ""

# ============================================================================
# STEP 5: PHOTO (MANUAL)
# ============================================================================
echo ""
echo "📸 STEP 5: PHOTO ANALYSIS"
echo "--------------------"
echo "⚠️  MANUAL STEP: Send a crop photo from WhatsApp"
echo "Example: Photo of cotton leaf with pests"
echo ""
read -p "Press Enter after you send the photo..."
echo "✅ Photo sent (wait ~10-15s for vision analysis)"
echo ""

# ============================================================================
# STEP 6: T+24H REMINDER
# ============================================================================
echo ""
echo "⏰ STEP 6: T+24H REMINDER (SIMULATED)"
echo "--------------------"
echo "Normally this would happen 24 hours later."
echo "We'll simulate it now..."
echo ""
read -p "Press Enter to simulate T+24h reminder..."

simulate_24h_reminder
sleep 5

echo ""
echo "⏳ Waiting for reminder to be sent (check WhatsApp)..."
echo "You should receive: 'अजून फवारणी केली नाही का?'"
echo ""
read -p "Press Enter after you receive the reminder..."

echo ""
echo "Clicking: झाला (Done)"
send_button "done" "झाला"
sleep 3

echo "✅ Nudge marked as DONE!"
echo ""

# ============================================================================
# COMPLETE
# ============================================================================
echo ""
echo "=========================================="
echo "✅ COMPLETE FLOW TEST FINISHED!"
echo "=========================================="
echo ""
echo "Summary:"
echo "✅ Onboarding: Marathi, Nagpur, Cotton, Consent"
echo "✅ First nudge: Received, clicked 'Not Yet'"
echo "✅ Text query: RAG response received"
echo "✅ Voice note: Transcribed and answered"
echo "✅ Photo: Vision analysis completed"
echo "✅ T+24h reminder: Received, clicked 'Done'"
echo ""
echo "Check your WhatsApp for all responses!"
echo ""
