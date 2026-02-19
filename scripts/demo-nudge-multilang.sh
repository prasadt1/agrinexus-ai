#!/bin/bash
set -euo pipefail

if [[ -f "$(dirname "$0")/demo.env" ]]; then
  # shellcheck disable=SC1091
  source "$(dirname "$0")/demo.env"
fi

WEBHOOK_URL="${WEBHOOK_URL:-}"
FROM_NUMBER="${PHONE_NUMBER:-${FROM_NUMBER:-}}"
FROM_NUMBERS="${FROM_NUMBERS:-}"
APP_SECRET="${APP_SECRET:-}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
RUN_WEATHER_POLL="${RUN_WEATHER_POLL:-true}"
WEATHER_LAMBDA="${WEATHER_LAMBDA:-agrinexus-weather-${ENVIRONMENT}}"
DISTRICT="${DISTRICT:-Aurangabad}"
CROP="${CROP:-Cotton}"
CONSENT="${CONSENT:-Yes}"

if [[ -z "$WEBHOOK_URL" ]]; then
  echo "Usage: WEBHOOK_URL=... FROM_NUMBER=... [APP_SECRET=...] $0"
  echo "Optional: FROM_NUMBERS=hi,mr,te,en (comma-separated phone numbers)"
  exit 1
fi

LANG_KEYS=(hi mr te en)
LANG_LABELS=("हिंदी" "मराठी" "తెలుగు" "English")

IFS=',' read -r -a NUMBERS <<< "$FROM_NUMBERS"

function get_number_for_index() {
  local idx=$1
  if [[ -n "$FROM_NUMBERS" && ${#NUMBERS[@]} -ge 4 ]]; then
    echo "${NUMBERS[$idx]}"
  else
    echo "$FROM_NUMBER"
  fi
}

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
  local to_number="$1"
  local text="$2"
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
                "from": "${to_number}",
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

  echo "Sending to ${to_number}: ${text}"
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

function trigger_weather() {
  if [[ "$RUN_WEATHER_POLL" == "true" ]]; then
    if command -v aws >/dev/null 2>&1; then
      echo "Triggering weather poller: $WEATHER_LAMBDA"
      aws lambda invoke --function-name "$WEATHER_LAMBDA" --payload '{}' /tmp/response.json >/dev/null
    else
      echo "AWS CLI not found; skipping weather poller invocation."
    fi
  fi
}

for idx in "${!LANG_KEYS[@]}"; do
  lang_label="${LANG_LABELS[$idx]}"
  phone="$(get_number_for_index $idx)"

  if [[ -z "$phone" ]]; then
    echo "Missing FROM_NUMBER (or FROM_NUMBERS[$idx]) for $lang_label"
    exit 1
  fi

  echo "--- Onboarding ${lang_label} (${phone}) ---"
  send_text "$phone" "$lang_label"
  sleep 2
  send_text "$phone" "$DISTRICT"
  sleep 2
  send_text "$phone" "$CROP"
  sleep 2
  send_text "$phone" "$CONSENT"
  sleep 2

  trigger_weather
  sleep 2

  echo "--- DONE response (${lang_label}) ---"
  case "$lang_label" in
    "हिंदी") send_text "$phone" "हो गया" ;;
    "मराठी") send_text "$phone" "झाला" ;;
    "తెలుగు") send_text "$phone" "అయ్యింది" ;;
    "English") send_text "$phone" "DONE" ;;
  esac
  sleep 2

done

echo "Multi-language nudge demo complete."
