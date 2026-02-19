#!/bin/bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
REGION="${2:-us-east-1}"
DASHBOARD_NAME="AgriNexus-Operations-${ENVIRONMENT}"
TEMPLATE="$(dirname "$0")/../dashboards/cloudwatch-dashboard.json"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required to create the dashboard"
  exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

if [ ! -f "$TEMPLATE" ]; then
  echo "Dashboard template not found: $TEMPLATE"
  exit 1
fi

BODY=$(cat "$TEMPLATE" \
  | sed "s/\${ENV}/$ENVIRONMENT/g" \
  | sed "s/\${REGION}/$REGION/g" \
  | sed "s/\${ACCOUNT_ID}/$ACCOUNT_ID/g")

aws cloudwatch put-dashboard \
  --dashboard-name "$DASHBOARD_NAME" \
  --dashboard-body "$BODY" \
  --region "$REGION"

echo "Dashboard created/updated: $DASHBOARD_NAME ($REGION)"
