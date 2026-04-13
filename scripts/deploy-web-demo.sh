#!/bin/bash
# Deploy AgriNexus AI Web Demo
# This script deploys the backend and provides instructions for frontend deployment

set -e

echo "🚀 Deploying AgriNexus AI Web Demo"
echo "===================================="
echo ""

# Check if we're in the right directory
if [ ! -f "template-week2.yaml" ]; then
    echo "❌ Error: template-week2.yaml not found"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Step 1: Build and deploy backend
echo "📦 Step 1: Building SAM application..."
sam build --template-file template-week2.yaml

echo ""
echo "🚀 Step 2: Deploying to AWS..."
sam deploy --config-file samconfig-week2.toml --template-file template-week2.yaml

# Extract API URL from CloudFormation outputs
echo ""
echo "📋 Step 3: Getting API Gateway URL..."
STACK_NAME="agrinexus-week2-dev"  # Adjust if your stack name is different
API_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`WebChatApiUrl`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$API_URL" ]; then
    echo "⚠️  Could not automatically retrieve API URL"
    echo "Please get it manually from CloudFormation outputs:"
    echo "  aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs'"
    echo ""
    echo "Then update docs/web-demo/index.html with the WebChatApiUrl"
else
    echo "✅ API Gateway URL: $API_URL"
    echo ""
    
    # Update index.html with API URL
    echo "📝 Step 4: Updating index.html with API URL..."
    if [ -f "docs/web-demo/index.html" ]; then
        # Create backup
        cp docs/web-demo/index.html docs/web-demo/index.html.bak
        
        # Update API URL
        sed -i.tmp "s|const API_URL = '.*';|const API_URL = '$API_URL';|g" docs/web-demo/index.html
        rm docs/web-demo/index.html.tmp
        
        echo "✅ Updated docs/web-demo/index.html"
        echo "   Backup saved to docs/web-demo/index.html.bak"
    else
        echo "⚠️  docs/web-demo/index.html not found"
    fi
fi

echo ""
echo "✅ Backend deployment complete!"
echo ""
echo "===================================="
echo "📱 Next Steps: Deploy Frontend"
echo "===================================="
echo ""
echo "Option 1: GitHub Pages (Recommended - Free)"
echo "-------------------------------------------"
echo "1. Commit and push changes:"
echo "   git add docs/web-demo/"
echo "   git commit -m 'Add web chat demo'"
echo "   git push origin main"
echo ""
echo "2. Enable GitHub Pages:"
echo "   - Go to your repo on GitHub"
echo "   - Settings → Pages"
echo "   - Source: Deploy from a branch"
echo "   - Branch: main, Folder: /docs"
echo "   - Save"
echo ""
echo "3. Your demo will be live at:"
echo "   https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/web-demo/"
echo ""
echo "Option 2: Test Locally First"
echo "-----------------------------"
echo "cd docs/web-demo"
echo "python3 -m http.server 8000"
echo "open http://localhost:8000"
echo ""
echo "===================================="
echo "🧪 Testing"
echo "===================================="
echo ""
echo "Test the backend directly:"
echo "curl -X POST $API_URL \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"message\": \"How to control cotton pests?\", \"language\": \"en\"}'"
echo ""
echo "===================================="
echo "📊 Monitoring"
echo "===================================="
echo ""
echo "View Lambda logs:"
echo "sam logs -n agrinexus-web-chat-dev --tail"
echo ""
echo "View CloudWatch metrics:"
echo "aws cloudwatch get-metric-statistics \\"
echo "  --namespace AWS/Lambda \\"
echo "  --metric-name Invocations \\"
echo "  --dimensions Name=FunctionName,Value=agrinexus-web-chat-dev \\"
echo "  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \\"
echo "  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \\"
echo "  --period 3600 \\"
echo "  --statistics Sum"
echo ""
echo "✅ Deployment script complete!"
