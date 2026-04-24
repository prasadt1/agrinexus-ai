#!/bin/bash
set -e

# Configuration
ENV="dev"
REGION="us-east-1"
ACCOUNT_ID="043624892076"
DASHBOARD_NAME="AgriNexus-Enhanced-Dashboard-${ENV}"

echo "🚀 Deploying Enhanced CloudWatch Dashboard..."
echo "   Dashboard: ${DASHBOARD_NAME}"
echo "   Environment: ${ENV}"
echo "   Region: ${REGION}"
echo ""

# Read the dashboard JSON and substitute variables
DASHBOARD_BODY=$(cat dashboards/cloudwatch-dashboard-enhanced.json | \
  sed "s/\${ENV}/${ENV}/g" | \
  sed "s/\${REGION}/${REGION}/g" | \
  sed "s/\${ACCOUNT_ID}/${ACCOUNT_ID}/g")

# Deploy the dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "${DASHBOARD_NAME}" \
  --dashboard-body "${DASHBOARD_BODY}" \
  --region "${REGION}"

echo ""
echo "✅ Dashboard deployed successfully!"
echo ""
echo "📊 View your dashboard:"
echo "   https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_NAME}"
echo ""
echo "📸 To take a screenshot for your article:"
echo "   1. Open the dashboard URL above"
echo "   2. Set time range to 'Last 7 days'"
echo "   3. Click 'Actions' → 'View in full screen'"
echo "   4. Take screenshot (Cmd+Shift+4 on Mac)"
echo "   5. Save as 'agrinexus-dashboard-enhanced.png'"
echo ""
