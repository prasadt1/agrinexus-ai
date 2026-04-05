#!/bin/bash
# Test WhatsApp Business profile and account

set -e

echo "Testing WhatsApp Business Account..."
echo ""

# Get WhatsApp credentials from Secrets Manager
WHATSAPP_SECRETS=$(aws secretsmanager get-secret-value \
  --secret-id agrinexus/whatsapp/access-token \
  --query SecretString \
  --output text)

ACCESS_TOKEN=$(echo $WHATSAPP_SECRETS | jq -r '.access_token')
PHONE_NUMBER_ID=$(echo $WHATSAPP_SECRETS | jq -r '.phone_number_id')

echo "Phone Number ID: $PHONE_NUMBER_ID"
echo ""

# Get current profile
echo "Fetching current profile..."
PROFILE=$(curl -s -X GET \
  "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/whatsapp_business_profile?fields=about,address,description,email,profile_picture_url,websites,vertical" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

echo "Current Profile:"
echo "$PROFILE" | jq '.'
echo ""

# Get phone number details
echo "Fetching phone number details..."
PHONE_DETAILS=$(curl -s -X GET \
  "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}?fields=verified_name,display_phone_number,quality_rating" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

echo "Phone Number Details:"
echo "$PHONE_DETAILS" | jq '.'
echo ""

echo "✅ Test complete!"
