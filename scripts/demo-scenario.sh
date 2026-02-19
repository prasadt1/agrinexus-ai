#!/bin/bash
set -euo pipefail

WEBHOOK_URL="${WEBHOOK_URL:-}"
FROM_NUMBER="${FROM_NUMBER:-}"
APP_SECRET="${APP_SECRET:-}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
RUN_WEATHER_POLL="${RUN_WEATHER_POLL:-false}"
WEATHER_LAMBDA="${WEATHER_LAMBDA:-agrinexus-weather-${ENVIRONMENT}}"

if [[ -z "$WEBHOOK_URL" || -z "$FROM_NUMBER" ]]; then
  echo "Usage: WEBHOOK_URL=... FROM_NUMBER=... [APP_SECRET=...] $0"
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

  echo "Sending: ${text}"
  if [[ -n "$sig" ]]; then
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -H "X-Hub-Signature-256: ${sig}" \
      -d "$payload" >/dev/null
  else
    echo "Warning: APP_SECRET not set; signature header omitted."
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "$payload" >/dev/null
  fi
}

# Onboarding flow (English path)
send_text "English"
sleep 2
send_text "Aurangabad"
sleep 2
send_text "Cotton"
sleep 2
send_text "Yes"
sleep 2

# Basic interaction
send_text "HELP"
sleep 2
send_text "How to control cotton pests?"
sleep 2

# Simulate DONE response for nudge loop
send_text "DONE"

if [[ "$RUN_WEATHER_POLL" == "true" ]]; then
  if command -v aws >/dev/null 2>&1; then
    echo "Triggering weather poller: $WEATHER_LAMBDA"
    aws lambda invoke --function-name "$WEATHER_LAMBDA" --payload '{}' /tmp/response.json >/dev/null
    echo "Weather poller invoked."
  else
    echo "AWS CLI not found; skipping weather poller invocation."
  fi
fi

echo "Demo scenario complete."
