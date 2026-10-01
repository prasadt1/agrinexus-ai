#!/usr/bin/env bash
# Scripted re:Invent visitor acceptance run (English).
# Uses the owner number AFTER --as-visitor (reset number, not a virgin MSISDN).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
if [[ -f "$ROOT/demo.env" ]]; then
  source "$ROOT/demo.env"
fi

FROM_NUMBER="${FROM_NUMBER:-${PHONE_NUMBER:-}}"
FROM_NUMBER="${FROM_NUMBER#+}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
APP_SECRET="${APP_SECRET:-}"

if [[ -z "$FROM_NUMBER" || -z "$WEBHOOK_URL" ]]; then
  echo "Set FROM_NUMBER/PHONE_NUMBER and WEBHOOK_URL" >&2
  exit 1
fi

hmac_signature() {
  local payload="$1"
  if [[ -z "$APP_SECRET" ]]; then
    echo ""
    return
  fi
  python3 -c 'import hmac,hashlib,sys; secret=sys.argv[1].encode(); msg=sys.argv[2].encode(); print("sha256="+hmac.new(secret,msg,hashlib.sha256).hexdigest())' \
    "$APP_SECRET" "$payload"
}

send_text() {
  local text="$1"
  local wamid="wamid.$(date +%s%N)"
  local payload
  payload=$(cat <<JSON
{
  "object": "whatsapp_business_account",
  "entry": [{"changes": [{"value": {"messages": [{
    "from": "${FROM_NUMBER}",
    "id": "${wamid}",
    "timestamp": "$(date +%s)",
    "type": "text",
    "text": {"body": "${text}"}
  }]}}]}]
}
JSON
)
  local sig
  sig=$(hmac_signature "$payload")
  echo "→ ${text}"
  if [[ -n "$sig" ]]; then
    curl -s -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" \
      -H "X-Hub-Signature-256: ${sig}" -d "$payload" >/dev/null
  else
    curl -s -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d "$payload" >/dev/null
  fi
}

echo "Visitor acceptance — reset number ${FROM_NUMBER} (not a new MSISDN)"
send_text "Hi from re:Invent"
sleep 5
send_text "How do I control whitefly on cotton?"
sleep 8
send_text "DELETE"
sleep 3
echo "Check WhatsApp, then: ./scripts/reset-onboard-and-demo.sh --phone ${FROM_NUMBER} --restore"
