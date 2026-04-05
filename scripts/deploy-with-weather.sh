#!/bin/bash
# Deploy AgriNexus Week 2 stack and load OpenWeatherMap key into Secrets Manager.
# The SAM template does NOT take WeatherApiKey — see WEATHER-API-SETUP.md.
set -e

echo "=================================================="
echo "AgriNexus AI — deploy + weather secret"
echo "=================================================="
echo ""

if [ -z "${WEATHER_API_KEY:-}" ]; then
    echo "❌ Set WEATHER_API_KEY to your OpenWeatherMap key (not committed to git)."
    echo "   export WEATHER_API_KEY=your_key"
    echo "   ./scripts/deploy-with-weather.sh"
    echo ""
    echo "Or skip this script: put the key in Secrets Manager yourself, then:"
    echo "   sam build -t template-week2.yaml && sam deploy --config-file samconfig-week2.toml"
    exit 1
fi

REGION="${AWS_REGION:-us-east-1}"
SECRET_ID="${WEATHER_API_SECRET_ID:-agrinexus/weather/api-key}"

echo "📦 Writing weather key to Secrets Manager: $SECRET_ID ($REGION)..."
aws secretsmanager put-secret-value \
    --secret-id "$SECRET_ID" \
    --secret-string "$WEATHER_API_KEY" \
    --region "$REGION" 2>/dev/null || \
aws secretsmanager create-secret \
    --name "$SECRET_ID" \
    --secret-string "$WEATHER_API_KEY" \
    --region "$REGION"

echo "✅ Secret updated"
echo ""

if [ -f scripts/demo.env ]; then
    echo "📋 Loading scripts/demo.env..."
    # shellcheck source=/dev/null
    source scripts/demo.env
fi

echo "🔨 sam build..."
sam build -t template-week2.yaml

echo "🚀 sam deploy..."
sam deploy \
    --config-file samconfig-week2.toml \
    --parameter-overrides \
        "TableName=${TABLE_NAME:-agrinexus-data}" \
        "TableStreamArn=${TABLE_STREAM_ARN}" \
        "KnowledgeBaseId=${KNOWLEDGE_BASE_ID}" \
        "GuardrailId=${GUARDRAIL_ID:-}" \
        "GuardrailVersion=${GUARDRAIL_VERSION:-1}"

echo ""
echo "✅ Done. Weather Lambda reads the key via WEATHER_API_KEY_SECRET → $SECRET_ID"
echo "🧪  aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' response.json && cat response.json"
