#!/bin/bash
# Update WhatsApp Business profile picture

set -e

# Check if image file is provided
if [ -z "$1" ]; then
  echo "Usage: ./update-whatsapp-profile-pic.sh <image-file-path>"
  echo "Example: ./update-whatsapp-profile-pic.sh agrinexus-logo.jpg"
  exit 1
fi

IMAGE_FILE="$1"

# Check if file exists
if [ ! -f "$IMAGE_FILE" ]; then
  echo "Error: File not found: $IMAGE_FILE"
  exit 1
fi

echo "Updating WhatsApp Business profile picture..."

# Get WhatsApp credentials from Secrets Manager
WHATSAPP_SECRETS=$(aws secretsmanager get-secret-value \
  --secret-id agrinexus/whatsapp/access-token \
  --query SecretString \
  --output text)

ACCESS_TOKEN=$(echo $WHATSAPP_SECRETS | jq -r '.access_token')
PHONE_NUMBER_ID=$(echo $WHATSAPP_SECRETS | jq -r '.phone_number_id')

# Step 1: Upload the image to WhatsApp
echo "Uploading image..."
UPLOAD_RESPONSE=$(curl -s -X POST \
  "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/media" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -F "file=@${IMAGE_FILE}" \
  -F "type=image/jpeg" \
  -F "messaging_product=whatsapp")

echo "Upload response: $UPLOAD_RESPONSE"

# Extract media ID
MEDIA_ID=$(echo $UPLOAD_RESPONSE | jq -r '.id')

if [ "$MEDIA_ID" == "null" ] || [ -z "$MEDIA_ID" ]; then
  echo "Error: Failed to upload image"
  echo "Response: $UPLOAD_RESPONSE"
  exit 1
fi

echo "Image uploaded successfully. Media ID: $MEDIA_ID"

# Step 2: Set the profile picture
echo "Setting profile picture..."
PROFILE_RESPONSE=$(curl -s -X POST \
  "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/whatsapp_business_profile" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"messaging_product\": \"whatsapp\",
    \"profile_picture_handle\": \"${MEDIA_ID}\"
  }")

echo "Profile update response: $PROFILE_RESPONSE"

# Check if successful
SUCCESS=$(echo $PROFILE_RESPONSE | jq -r '.success')

if [ "$SUCCESS" == "true" ]; then
  echo ""
  echo "✅ Profile picture updated successfully!"
  echo ""
  echo "Note: It may take a few minutes for the change to appear in WhatsApp."
else
  echo ""
  echo "❌ Failed to update profile picture"
  echo "Response: $PROFILE_RESPONSE"
  exit 1
fi
