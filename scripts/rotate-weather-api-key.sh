#!/bin/bash
# Script to rotate OpenWeatherMap API key and move to Secrets Manager

set -e

echo "=== OpenWeatherMap API Key Rotation ==="
echo ""
echo "IMPORTANT: Before running this script:"
echo "1. Go to https://openweathermap.org/api_keys"
echo "2. Delete the old API key: f00ea294289b451f4d8e43a325fcf5ca"
echo "3. Generate a NEW API key"
echo "4. Copy the new key"
echo ""
read -p "Enter your NEW OpenWeatherMap API key: " NEW_API_KEY

if [ -z "$NEW_API_KEY" ]; then
    echo "Error: API key cannot be empty"
    exit 1
fi

echo ""
echo "Creating secret in AWS Secrets Manager..."

# Create or update the secret
aws secretsmanager create-secret \
    --name agrinexus/weather/api-key \
    --description "OpenWeatherMap API key for weather polling" \
    --secret-string "$NEW_API_KEY" \
    --region us-east-1 2>/dev/null || \
aws secretsmanager update-secret \
    --secret-id agrinexus/weather/api-key \
    --secret-string "$NEW_API_KEY" \
    --region us-east-1

echo "✅ Secret created/updated: agrinexus/weather/api-key"
echo ""
echo "Next steps:"
echo "1. Update template-week2.yaml to read from Secrets Manager"
echo "2. Remove WeatherApiKey from samconfig-week2.toml"
echo "3. Deploy with: sam build && sam deploy"
echo "4. Commit changes (without the API key)"
