#!/bin/bash
# Reset user profile for fresh onboarding test

set -e

# Get phone number from argument or use default
PHONE_NUMBER="${1:-4917647009148}"

echo "Resetting profile for phone: $PHONE_NUMBER"

# Delete user profile
aws dynamodb delete-item \
  --table-name agrinexus-data \
  --key "{\"PK\":{\"S\":\"USER#${PHONE_NUMBER}\"},\"SK\":{\"S\":\"PROFILE\"}}"

echo "✓ Profile deleted"

# Delete all messages for this user
echo "Deleting messages..."
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values "{\":pk\":{\"S\":\"USER#${PHONE_NUMBER}\"},\":sk\":{\"S\":\"MSG#\"}}" \
  --projection-expression "PK, SK" \
  --output json | \
jq -r '.Items[] | @json' | \
while read item; do
  aws dynamodb delete-item \
    --table-name agrinexus-data \
    --key "$item" 2>/dev/null || true
done

echo "✓ Messages deleted"

# Delete all nudges for this user
echo "Deleting nudges..."
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values "{\":pk\":{\"S\":\"USER#${PHONE_NUMBER}\"},\":sk\":{\"S\":\"NUDGE#\"}}" \
  --projection-expression "PK, SK" \
  --output json | \
jq -r '.Items[] | @json' | \
while read item; do
  aws dynamodb delete-item \
    --table-name agrinexus-data \
    --key "$item" 2>/dev/null || true
done

echo "✓ Nudges deleted"

echo ""
echo "✅ User profile reset complete!"
echo ""
echo "Now you can:"
echo "1. Send 'Namaste' to WhatsApp to start fresh onboarding"
echo "2. Complete onboarding with consent=Yes"
echo "3. Run: ./scripts/trigger-nudge-test.sh $PHONE_NUMBER"
