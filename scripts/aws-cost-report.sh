#!/usr/bin/env bash
# AgriNexus — AWS Cost Explorer report (account-wide; filter by service).
#
# Prerequisites:
#   - AWS CLI v2 configured (aws configure / env vars)
#   - Cost Explorer API enabled once per account:
#       https://console.aws.amazon.com/cost-management/home#/settings
#     ("Cost Explorer" → Get started — no extra charge for the API)
#
# Usage:
#   ./scripts/aws-cost-report.sh                 # last 30 days, by service
#   ./scripts/aws-cost-report.sh --days 7      # last 7 days
#   ./scripts/aws-cost-report.sh --days 90 --granularity MONTHLY
#   ./scripts/aws-cost-report.sh --json        # raw JSON for automation
#
set -euo pipefail

DAYS=30
GRANULARITY="DAILY"
JSON_OUT=false
# Cost Explorer API is only available from the us-east-1 endpoint (per AWS docs).
CE_REGION="us-east-1"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="$2"; shift 2 ;;
    --granularity) GRANULARITY="$2"; shift 2 ;;
    --json) JSON_OUT=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found. Install AWS CLI v2." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for date math and output formatting." >&2
  exit 1
fi

# Cost Explorer End date is exclusive (see AWS docs).
read -r START END < <(python3 <<PY
from datetime import date, timedelta
end = date.today() + timedelta(days=1)
start = date.today() - timedelta(days=int("${DAYS}"))
print(start.isoformat(), end.isoformat())
PY
)

ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
if [[ -z "$ACCOUNT" || "$ACCOUNT" == "None" ]]; then
  echo "ERROR: aws sts get-caller-identity failed. Check credentials." >&2
  exit 1
fi

echo "=== AWS Cost report ==="
echo "Account: $ACCOUNT  |  Cost Explorer API region: $CE_REGION"
echo "Period:  $START  →  $END (end exclusive)  |  Granularity: $GRANULARITY"
echo ""

if [[ "$GRANULARITY" != "DAILY" && "$GRANULARITY" != "MONTHLY" ]]; then
  echo "ERROR: --granularity must be DAILY or MONTHLY" >&2
  exit 1
fi

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

set +e
aws ce get-cost-and-usage \
  --region "$CE_REGION" \
  --time-period "Start=${START},End=${END}" \
  --granularity "$GRANULARITY" \
  --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --output json > "$TMP_JSON" 2>&1
AWS_ERR=$?
set -e

if [[ $AWS_ERR -ne 0 ]]; then
  echo "ERROR: Cost Explorer request failed." >&2
  cat "$TMP_JSON" >&2
  echo "" >&2
  echo "If you see 'RequestLimitExceeded' or CE not enabled, open:" >&2
  echo "  https://console.aws.amazon.com/cost-management/home#/cost-explorer" >&2
  exit 1
fi

if [[ "$JSON_OUT" == true ]]; then
  cat "$TMP_JSON"
  exit 0
fi

python3 - "$TMP_JSON" <<'PY'
import json, sys
from collections import defaultdict

path = sys.argv[1]
with open(path) as f:
    data = json.load(f)

results = data.get("ResultsByTime") or []
by_service = defaultdict(float)
daily_total = []

for block in results:
    t = block.get("TimePeriod", {}).get("Start", "?")
    day_sum = 0.0
    for group in block.get("Groups", []):
        keys = group.get("Keys") or []
        svc = keys[0] if keys else "No service dimension"
        amt = group.get("Metrics", {}).get("UnblendedCost", {})
        amt = float(amt.get("Amount") or 0)
        by_service[svc] += amt
        day_sum += amt
    daily_total.append((t, day_sum))

print("--- Daily totals (all services) ---")
for t, s in daily_total:
    print(f"  {t}  ${s:,.2f}")

print("")
print("--- Sum by service (period) ---")
for svc, s in sorted(by_service.items(), key=lambda x: -x[1]):
    if s < 0.000001:
        continue
    print(f"  {svc:50s}  ${s:>12,.2f}")

grand = sum(by_service.values())
print("")
print(f"  {'TOTAL (Unblended)':50s}  ${grand:>12,.2f}")
print("")
print("Note: Costs are estimates; final charges are on the AWS bill.")
print("      Filter by tags is not applied — add AWS Cost Allocation tags for per-project splits.")
PY
