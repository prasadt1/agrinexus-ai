#!/bin/bash
# Trigger nudge for a specific user (for testing)

set -e

PHONE_NUMBER="${1:-4917647009148}"

echo "Testing nudge system for phone: $PHONE_NUMBER"
echo ""

# Check if user profile exists and has consent
echo "1. Checking user profile..."
PROFILE=$(aws dynamodb get-item \
  --table-name agrinexus-data \
  --key "{\"PK\":{\"S\":\"USER#${PHONE_NUMBER}\"},\"SK\":{\"S\":\"PROFILE\"}}" \
  --output json)

if [ "$(echo $PROFILE | jq -r '.Item')" == "null" ]; then
  echo "❌ User profile not found. Please complete onboarding first."
  exit 1
fi

ONBOARDING=$(echo $PROFILE | jq -r '.Item.onboarding_complete.BOOL')
CONSENT=$(echo $PROFILE | jq -r '.Item.consent.BOOL')
LOCATION=$(echo $PROFILE | jq -r '.Item.location.S')
DIALECT=$(echo $PROFILE | jq -r '.Item.dialect.S')

echo "   Onboarding complete: $ONBOARDING"
echo "   Consent given: $CONSENT"
echo "   Location: $LOCATION"
echo "   Dialect: $DIALECT"
echo ""

if [ "$ONBOARDING" != "true" ]; then
  echo "❌ Onboarding not complete. Please complete onboarding first."
  exit 1
fi

if [ "$CONSENT" != "true" ]; then
  echo "❌ User has not given consent for nudges."
  exit 1
fi

# Trigger weather poller
echo "2. Triggering weather poller..."
aws lambda invoke \
  --function-name agrinexus-weather-dev \
  --payload '{}' \
  /tmp/weather-response.json > /dev/null

RESPONSE=$(cat /tmp/weather-response.json)
echo "   Response: $RESPONSE"
echo ""

# Check if nudge was created
echo "3. Checking for nudges..."
sleep 2
NUDGES=$(aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values "{\":pk\":{\"S\":\"USER#${PHONE_NUMBER}\"},\":sk\":{\"S\":\"NUDGE#\"}}" \
  --output json)

NUDGE_COUNT=$(echo $NUDGES | jq -r '.Items | length')
echo "   Found $NUDGE_COUNT nudge(s)"

if [ "$NUDGE_COUNT" -gt 0 ]; then
  echo ""
  echo "✅ Nudge system working!"
  echo ""
  echo "Latest nudge:"
  echo $NUDGES | jq -r '.Items[0] | {id: .SK.S, status: .status.S, activity: .activity.S, message: .message.S}'
  echo ""
  echo "Check your WhatsApp for the nudge message!"
else
  echo ""
  echo "⚠️  No nudge created. Checking logs..."
  echo ""
  echo "Weather poller logs:"
  aws logs tail /aws/lambda/agrinexus-weather-dev --since 5m --format short
  echo ""
  echo "Nudge sender logs:"
  aws logs tail /aws/lambda/agrinexus-nudge-sender-dev --since 5m --format short
fi
