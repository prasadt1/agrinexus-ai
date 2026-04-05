#!/bin/bash
# Script to rotate OpenWeatherMap API key and move to Secrets Manager

set -e

echo "=== OpenWeatherMap API Key Rotation ==="
echo ""
echo "IMPORTANT: Before running this script:"
echo "1. Go to https://openweathermap.org/api_keys"
echo "2. In the OpenWeatherMap dashboard, revoke/delete any key that was ever committed to git"
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
echo "1. Confirm template-week2.yaml Weather Lambda uses WEATHER_API_KEY_SECRET (Secrets Manager)"
echo "2. Do not put API keys in samconfig-week2.toml or markdown"
echo "3. Deploy with: sam build -t template-week2.yaml && sam deploy --config-file samconfig-week2.toml"
echo "4. Commit only code/config changes (never the secret value)"
