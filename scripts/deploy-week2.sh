#!/bin/bash
set -e

echo "========================================="
echo "AgriNexus AI - Week 2 Deployment"
echo "========================================="

# Check if Week 1 is deployed
echo "Checking Week 1 deployment..."
TABLE_EXISTS=$(aws dynamodb describe-table --table-name agrinexus-data 2>&1 || echo "NOT_FOUND")

if [[ "$TABLE_EXISTS" == *"NOT_FOUND"* ]]; then
    echo "ERROR: Week 1 not deployed! DynamoDB table 'agrinexus-data' not found."
    echo "Please deploy Week 1 first using: bash scripts/setup-week1.sh"
    exit 1
fi

echo "✓ Week 1 table found"

# Get Week 1 resource IDs
echo "Fetching Week 1 resource IDs..."

# Try to get from CloudFormation stack first
STACK_NAME="agrinexus-week1"
KB_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
    --output text 2>/dev/null || echo "")

GUARDRAIL_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`GuardrailId`].OutputValue' \
    --output text 2>/dev/null || echo "")

# If not found in stack, prompt user
if [ -z "$KB_ID" ] || [ "$KB_ID" == "None" ]; then
    echo ""
    echo "Could not find Knowledge Base ID from Week 1 stack."
    echo "Please enter your Bedrock Knowledge Base ID:"
    read -p "KB ID: " KB_ID
fi

if [ -z "$GUARDRAIL_ID" ] || [ "$GUARDRAIL_ID" == "None" ]; then
    echo ""
    echo "Could not find Guardrail ID from Week 1 stack."
    echo "Please enter your Bedrock Guardrail ID:"
    read -p "Guardrail ID: " GUARDRAIL_ID
fi

echo "✓ Knowledge Base ID: $KB_ID"
echo "✓ Guardrail ID: $GUARDRAIL_ID"

# Build
echo ""
echo "Building Week 2 Lambda functions..."
sam build -t template-week2.yaml

# Deploy
echo ""
echo "Deploying Week 2 stack..."
sam deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name agrinexus-week2 \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameter-overrides \
        Environment=dev \
        TableName=agrinexus-data \
        KnowledgeBaseId=$KB_ID \
        GuardrailId=$GUARDRAIL_ID \
        GuardrailVersion=1 \
    --no-fail-on-empty-changeset

# Get outputs
echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="

WEBHOOK_URL=$(aws cloudformation describe-stacks \
    --stack-name agrinexus-week2 \
    --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
    --output text)

echo ""
echo "Webhook URL: $WEBHOOK_URL"
echo ""
echo "Next Steps:"
echo "1. Update WhatsApp secrets:"
echo "   aws secretsmanager update-secret --secret-id agrinexus-whatsapp-dev --secret-string '{...}'"
echo ""
echo "2. Configure webhook in Meta for Developers:"
echo "   URL: $WEBHOOK_URL"
echo "   Verify Token: (your chosen token)"
echo ""
echo "3. Create WhatsApp message templates in Meta Business Manager"
echo ""
echo "4. Test webhook: curl \"$WEBHOOK_URL?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test\""
