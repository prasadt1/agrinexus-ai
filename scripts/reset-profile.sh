#!/usr/bin/env bash
# Reset WhatsApp user profile and related DynamoDB items (same as delete-user-data, non-interactive).
# Usage:
#   ./scripts/reset-profile.sh 1555123456789
#   ./scripts/reset-profile.sh   # uses PHONE_NUMBER from scripts/demo.env (digits, no +)
#
# Keys use the same format as WhatsApp (typically country code + number, no leading +).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
if [[ -f "$ROOT/demo.env" ]]; then
  source "$ROOT/demo.env"
fi

RAW="${1:-${PHONE_NUMBER:-}}"
if [[ -z "$RAW" ]]; then
  echo "Usage: $0 <phone_e164_digits>" >&2
  echo "Example: $0 1555123456789" >&2
  echo "Or set PHONE_NUMBER in scripts/demo.env" >&2
  exit 1
fi
PHONE="${RAW#+}"

export DELETE_CONFIRM=yes
exec "$ROOT/delete-user-data.sh" "$PHONE"
