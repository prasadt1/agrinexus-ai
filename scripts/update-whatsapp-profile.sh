#!/bin/bash
# Update WhatsApp Business profile (about, description, etc.)

set -e

echo "Updating WhatsApp Business profile..."

# Get WhatsApp credentials from Secrets Manager
WHATSAPP_SECRETS=$(aws secretsmanager get-secret-value \
  --secret-id agrinexus/whatsapp/access-token \
  --query SecretString \
  --output text)

ACCESS_TOKEN=$(echo $WHATSAPP_SECRETS | jq -r '.access_token')
PHONE_NUMBER_ID=$(echo $WHATSAPP_SECRETS | jq -r '.phone_number_id')

# Update profile
RESPONSE=$(curl -s -X POST \
  "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/whatsapp_business_profile" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "about": "AgriNexus AI - Your AI-powered agricultural advisor for cotton farming. Get expert advice on pest management, weather, and best practices. 🌱",
    "description": "AgriNexus AI provides personalized agricultural guidance to cotton farmers using AI and local expertise. Available in English, Hindi, Marathi, and Telugu.",
    "vertical": "AGRICULTURE",
    "email": "support@agrinexus.ai",
    "websites": ["https://agrinexus.ai"],
    "address": "India"
  }')

echo "Response: $RESPONSE"

# Check if successful
SUCCESS=$(echo $RESPONSE | jq -r '.success')

if [ "$SUCCESS" == "true" ]; then
  echo ""
  echo "✅ Profile updated successfully!"
else
  echo ""
  echo "❌ Failed to update profile"
  echo "Response: $RESPONSE"
fi
