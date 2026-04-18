#!/usr/bin/env bash
# Pre-demo smoke: validate SAM template, fast unit tests, optional Bedrock golden + web chat curl.
# Usage (from repo root):
#   ./scripts/e2e-smoke.sh
# Optional env:
#   KNOWLEDGE_BASE_ID   — if set, runs tests/test_golden_questions.py (live AWS Bedrock KB)
#   WEB_CHAT_URL        — e.g. https://xxx.execute-api.us-east-1.amazonaws.com/dev/chat
#   WEB_CHAT_MESSAGE    — default: "How to control cotton pests?"
#   WEB_CHAT_LANG       — default: en

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== 1) SAM template validation =="
if command -v sam >/dev/null 2>&1; then
  sam validate --template-file template-week2.yaml --lint 2>/dev/null || sam validate --template-file template-week2.yaml
else
  echo "   (skip: sam CLI not installed)"
fi

echo "== 2) Pytest — fast tests (no live KB) =="
python3 -m pytest tests/test_nudge_flow.py tests/test_district_helplines.py -q

if [[ -n "${KNOWLEDGE_BASE_ID:-}" ]]; then
  echo "== 3) Pytest — golden KB (KNOWLEDGE_BASE_ID set) =="
  python3 -m pytest tests/test_golden_questions.py -q --maxfail=2
else
  echo "== 3) Golden KB tests skipped (export KNOWLEDGE_BASE_ID to enable) =="
fi

if [[ -n "${WEB_CHAT_URL:-}" ]]; then
  echo "== 4) Web chat HTTP smoke =="
  MSG="${WEB_CHAT_MESSAGE:-How to control cotton pests?}"
  LANG="${WEB_CHAT_LANG:-en}"
  BODY=$(python3 -c "import json,sys; print(json.dumps({'message':sys.argv[1],'language':sys.argv[2],'client_id':'e2e-smoke-00000000-0000-4000-8000-000000000001'}))" "$MSG" "$LANG")
  curl -sS -f -X POST "$WEB_CHAT_URL" \
    -H "Content-Type: application/json" \
    -d "$BODY" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('reply'), d; print('reply_len', len(d['reply']))"
  echo "   OK"
else
  echo "== 4) Web chat curl skipped (set WEB_CHAT_URL to API Gateway .../chat) =="
fi

echo "== e2e-smoke.sh done =="
