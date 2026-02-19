#!/bin/bash
set -euo pipefail

PHONE=""
LANG="hi"
DISTRICT="Aurangabad"
CROP="Cotton"
CONSENT="Yes"
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
except Exception as e:
    print(f"PROFILE delete failed: {e}")

# Delete all NUDGEs for user
resp = table.query(
    KeyConditionExpression=Key('PK').eq(f'USER#{phone}') & Key('SK').begins_with('NUDGE#')
)
items = resp.get('Items', [])
while True:
    for item in items:
        table.delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
    if 'LastEvaluatedKey' in resp:
        resp = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{phone}') & Key('SK').begins_with('NUDGE#'),
            ExclusiveStartKey=resp['LastEvaluatedKey']
        )
        items = resp.get('Items', [])
    else:
        break

print("Reset complete")
PY
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
