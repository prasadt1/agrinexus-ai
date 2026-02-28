#!/bin/bash
# End-to-end test: onboarding, Q&A, optional nudge trigger + DONE.
# Voice and vision E2E require manual steps in WhatsApp - see docs/E2E-TEST-GUIDE.md.
set -euo pipefail

if [[ -f "$(dirname "$0")/demo.env" ]]; then
  # shellcheck disable=SC1091
  source "$(dirname "$0")/demo.env"
fi

WEBHOOK_URL="${WEBHOOK_URL:-}"
APP_SECRET="${APP_SECRET:-}"
PHONE="${PHONE_NUMBER:-}"
LANG="en"
DO_RESET="true"
DO_NUDGE="true"
TABLE_NAME="${TABLE_NAME:-agrinexus-data}"
REGION="${AWS_REGION:-us-east-1}"
WEATHER_LAMBDA="${WEATHER_LAMBDA:-agrinexus-weather-dev}"

function usage() {
  echo "Usage: $0 --phone <E.164> [--lang hi|mr|te|en] [--no-reset] [--no-nudge]"
  echo "Required env: WEBHOOK_URL. Optional: APP_SECRET, PHONE_NUMBER."
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phone)  PHONE="$2"; shift 2;;
    --lang)   LANG="$2"; shift 2;;
    --no-reset) DO_RESET="false"; shift;;
    --no-nudge) DO_NUDGE="false"; shift;;
    *) usage;;
  esac
done

if [[ -z "$PHONE" || -z "$WEBHOOK_URL" ]]; then
  usage
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
  echo "  -> $text"
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
}

function reset_dynamodb_profile() {
  echo "Resetting profile for ${PHONE}..."
  aws dynamodb delete-item \
    --table-name "${TABLE_NAME}" \
    --key "{\"PK\": {\"S\": \"USER#${PHONE}\"}, \"SK\": {\"S\": \"PROFILE\"}}" \
    --region "${REGION}" 2>/dev/null || true
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
" 2>/dev/null | while IFS='|' read -r pk sk; do
    aws dynamodb delete-item \
      --table-name "${TABLE_NAME}" \
      --key "{\"PK\": {\"S\": \"${pk}\"}, \"SK\": {\"S\": \"${sk}\"}}" \
      --region "${REGION}" 2>/dev/null || true
  done
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
" 2>/dev/null | while IFS='|' read -r pk sk; do
    aws dynamodb delete-item \
      --table-name "${TABLE_NAME}" \
      --key "{\"PK\": {\"S\": \"${pk}\"}, \"SK\": {\"S\": \"${sk}\"}}" \
      --region "${REGION}" 2>/dev/null || true
  done
  echo "  Reset done."
}

case "$LANG" in
  hi) LANG_LABEL='हिंदी';  SAMPLE_QUESTION='कपास में कीट कैसे नियंत्रित करें?';;
  mr) LANG_LABEL='मराठी';  SAMPLE_QUESTION='कापूसात कीट कसे नियंत्रित करावे?';;
  te) LANG_LABEL='తెలుగు';  SAMPLE_QUESTION='పత్తిలో చీడపీడలను ఎలా నియంత్రించాలి?';;
  en) LANG_LABEL='English'; SAMPLE_QUESTION='How to control cotton pests?';;
  *) echo "Unsupported lang: $LANG"; exit 1;;
esac

case "$LANG" in
  hi) DONE_MSG='हो गया';;
  mr) DONE_MSG='झाला';;
  te) DONE_MSG='అయ్యింది';;
  en) DONE_MSG='DONE';;
esac

echo "=============================================="
echo "E2E Test: $LANG | phone ${PHONE} | reset=$DO_RESET | nudge=$DO_NUDGE"
echo "=============================================="

if [[ "$DO_RESET" == "true" ]]; then
  reset_dynamodb_profile
  sleep 1
fi

echo "[1/4] Onboarding"
send_text "$LANG_LABEL"
sleep 2
send_text "Aurangabad"
sleep 2
send_text "Cotton"
sleep 2
send_text "Yes"
sleep 2

echo "[2/4] Q&A: HELP + sample question"
send_text "HELP"
sleep 3
send_text "$SAMPLE_QUESTION"
sleep 5

if [[ "$DO_NUDGE" == "true" ]]; then
  echo "[3/4] Triggering weather poller"
  if command -v aws >/dev/null 2>&1; then
    aws lambda invoke --function-name "$WEATHER_LAMBDA" --payload '{}' /tmp/e2e-weather.json >/dev/null 2>&1 || true
    echo "  Weather poller invoked."
  fi
  sleep 2
  echo "[4/4] Sending DONE"
  send_text "$DONE_MSG"
else
  echo "[3/4] Skipped - no-nudge"
  echo "[4/4] Skipped"
fi

echo ""
echo "=============================================="
echo "Automated E2E steps finished."
echo "Manual: Voice = send voice note; Vision = send crop photo. See docs/E2E-TEST-GUIDE.md"
echo "=============================================="
