#!/bin/bash
# Deploy AgriNexus with Real Weather API
set -e

echo "=================================================="
echo "AgriNexus AI - Deployment with Real Weather API"
echo "=================================================="
echo ""

# Check if weather API key is provided
if [ -z "$WEATHER_API_KEY" ]; then
    echo "❌ Error: WEATHER_API_KEY environment variable not set"
    echo ""
    echo "Get your free API key:"
    echo "1. Sign up at https://openweathermap.org/api"
    echo "2. Get key from https://home.openweathermap.org/api_keys"
    echo "3. Wait 10-15 minutes for activation"
    echo ""
    echo "Then run:"
    echo "  export WEATHER_API_KEY=your_key_here"
    echo "  ./scripts/deploy-with-weather.sh"
    exit 1
fi

echo "✅ Weather API key found"
echo ""

# Load other required parameters from demo.env if it exists
if [ -f scripts/demo.env ]; then
    echo "📋 Loading parameters from scripts/demo.env..."
    source scripts/demo.env
    echo "✅ Parameters loaded"
else
    echo "⚠️  Warning: scripts/demo.env not found"
    echo "   Make sure you have the required parameters set:"
    echo "   - TABLE_NAME"
    echo "   - TABLE_STREAM_ARN"
    echo "   - KNOWLEDGE_BASE_ID"
    echo ""
fi

# Build
echo ""
echo "🔨 Building SAM application..."
sam build -t template-week2.yaml

# Deploy
echo ""
echo "🚀 Deploying with real weather API..."
sam deploy \
    --config-file samconfig-week2.toml \
    --parameter-overrides \
        WeatherApiKey="$WEATHER_API_KEY" \
        TableName="${TABLE_NAME:-agrinexus-data}" \
        TableStreamArn="${TABLE_STREAM_ARN}" \
        KnowledgeBaseId="${KNOWLEDGE_BASE_ID}" \
        GuardrailId="${GUARDRAIL_ID:-}" \
        GuardrailVersion="${GUARDRAIL_VERSION:-1}"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🧪 Test the weather poller:"
echo "  aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' response.json && cat response.json"
echo ""
echo "Look for \"mock_mode\": false to confirm real weather is active"
