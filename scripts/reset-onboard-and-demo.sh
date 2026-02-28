#!/bin/bash
set -euo pipefail

if [[ -f "$(dirname "$0")/demo.env" ]]; then
  # shellcheck disable=SC1091
  source "$(dirname "$0")/demo.env"
fi

PHONE="${PHONE_NUMBER:-}"
LANG="hi"
DISTRICT="${DISTRICT:-Aurangabad}"
CROP="${CROP:-Cotton}"
CONSENT="${CONSENT:-Yes}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
APP_SECRET="${APP_SECRET:-}"
TABLE_NAME="${TABLE_NAME:-agrinexus-data}"
REGION="${AWS_REGION:-us-east-1}"
RUN_WEATHER_POLL="${RUN_WEATHER_POLL:-true}"
WEATHER_LAMBDA="${WEATHER_LAMBDA:-agrinexus-weather-dev}"
SEND_DONE="${SEND_DONE:-true}"
SEND_NOT_YET="${SEND_NOT_YET:-false}"

function usage() {
  echo "Usage: $0 --phone <E.164> [--lang hi|mr|te|en] [--district NAME] [--crop NAME] [--consent Yes|No]"
  echo "Required env: WEBHOOK_URL (and APP_SECRET if signature enabled)"
  echo "Optional env: TABLE_NAME, AWS_REGION, RUN_WEATHER_POLL, WEATHER_LAMBDA"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phone) PHONE="$2"; shift 2;;
    --lang) LANG="$2"; shift 2;;
    --district) DISTRICT="$2"; shift 2;;
    --crop) CROP="$2"; shift 2;;
    --consent) CONSENT="$2"; shift 2;;
    *) usage; exit 1;;
  esac
done

if [[ -z "$PHONE" || -z "$WEBHOOK_URL" ]]; then
  usage
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
                "from": "${PHONE}",
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

function reset_dynamodb_profile() {
  echo "Resetting onboarding state in DynamoDB for ${PHONE}"
  
  # Delete PROFILE using AWS CLI
  aws dynamodb delete-item \
    --table-name "${TABLE_NAME}" \
    --key "{\"PK\": {\"S\": \"USER#${PHONE}\"}, \"SK\": {\"S\": \"PROFILE\"}}" \
    --region "${REGION}" 2>/dev/null || true
  
  # Query and delete all NUDGEs
  local nudges
  nudges=$(aws dynamodb query \
    --table-name "${TABLE_NAME}" \
    --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
    --expression-attribute-values "{\":pk\": {\"S\": \"USER#${PHONE}\"}, \":sk\": {\"S\": \"NUDGE#\"}}" \
    --region "${REGION}" \
    --output json 2>/dev/null || echo '{"Items":[]}')
  
  echo "$nudges" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('Items', []):
    pk = item['PK']['S']
    sk = item['SK']['S']
    print(f'{pk}|{sk}')
" | while IFS='|' read -r pk sk; do
    aws dynamodb delete-item \
      --table-name "${TABLE_NAME}" \
      --key "{\"PK\": {\"S\": \"${pk}\"}, \"SK\": {\"S\": \"${sk}\"}}" \
      --region "${REGION}" 2>/dev/null || true
  done
  
  # Delete all MSG records
  local msgs
  msgs=$(aws dynamodb query \
    --table-name "${TABLE_NAME}" \
    --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
    --expression-attribute-values "{\":pk\": {\"S\": \"USER#${PHONE}\"}, \":sk\": {\"S\": \"MSG#\"}}" \
    --region "${REGION}" \
    --output json 2>/dev/null || echo '{"Items":[]}')
  
  echo "$msgs" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('Items', []):
    pk = item['PK']['S']
    sk = item['SK']['S']
    print(f'{pk}|{sk}')
" | while IFS='|' read -r pk sk; do
    aws dynamodb delete-item \
      --table-name "${TABLE_NAME}" \
      --key "{\"PK\": {\"S\": \"${pk}\"}, \"SK\": {\"S\": \"${sk}\"}}" \
      --region "${REGION}" 2>/dev/null || true
  done
  
  echo "Reset complete"
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

LANG_LABEL=""
case "$LANG" in
  hi) LANG_LABEL="हिंदी";;
  mr) LANG_LABEL="मराठी";;
  te) LANG_LABEL="తెలుగు";;
  en) LANG_LABEL="English";;
  *) echo "Unsupported lang: $LANG"; exit 1;;
 esac

reset_dynamodb_profile
sleep 1

# Onboarding
send_text "$LANG_LABEL"
sleep 2
send_text "$DISTRICT"
sleep 2
send_text "$CROP"
sleep 2
send_text "$CONSENT"
sleep 2

trigger_weather
sleep 2

if [[ "$SEND_DONE" == "true" ]]; then
  case "$LANG" in
    hi) send_text "हो गया";;
    mr) send_text "झाला";;
    te) send_text "అయ్యింది";;
    en) send_text "DONE";;
  esac
  sleep 2
fi

if [[ "$SEND_NOT_YET" == "true" ]]; then
  case "$LANG" in
    hi) send_text "अभी नहीं";;
    mr) send_text "नाही झाला";;
    te) send_text "ఇంకా లేదు";;
    en) send_text "NOT YET";;
  esac
  sleep 2
fi

echo "Reset + onboarding + nudge demo complete."
