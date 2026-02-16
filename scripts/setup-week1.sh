#!/bin/bash
# Week 1 Setup Script - Deploy infrastructure and test

set -e

STACK_NAME=${1:-agrinexus-dev}
REGION=${2:-us-east-1}

echo "=========================================="
echo "AgriNexus AI - Week 1 Setup"
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "=========================================="

# Step 1: Deploy SAM template
echo ""
echo "Step 1: Deploying SAM template..."
sam build
sam deploy \
  --stack-name $STACK_NAME \
  --region $REGION \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides Environment=dev \
  --resolve-s3

# Step 2: Get outputs
echo ""
echo "Step 2: Retrieving stack outputs..."
TABLE_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`TableName`].OutputValue' \
  --output text)

KB_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseBucketName`].OutputValue' \
  --output text)

KB_ID=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
  --output text)

GUARDRAIL_ID=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`GuardrailId`].OutputValue' \
  --output text)

echo "  Table: $TABLE_NAME"
echo "  KB Bucket: $KB_BUCKET"
echo "  KB ID: $KB_ID"
echo "  Guardrail ID: $GUARDRAIL_ID"

# Step 3: Test DynamoDB table
echo ""
echo "Step 3: Testing DynamoDB table..."
python3 << EOF
import boto3
import json
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='$REGION')
table = dynamodb.Table('$TABLE_NAME')

# Test PutItem - User Profile
test_user = {
    'PK': 'USER#+919876543210',
    'SK': 'PROFILE',
    'entityType': 'UserProfile',
    'userId': '+919876543210',
    'location': {
        'region': 'Aurangabad District',
        'state': 'Maharashtra',
        'country': 'India'
    },
    'crops': ['cotton'],
    'language': 'hi',
    'dialect': 'Marathi',
    'voicePreference': True,
    'consent': True,
    'consentedAt': int(datetime.utcnow().timestamp()),
    'registeredAt': int(datetime.utcnow().timestamp()),
    'profileComplete': True
}

table.put_item(Item=test_user)
print("✓ PutItem successful")

# Test Query
response = table.query(
    KeyConditionExpression='PK = :pk',
    ExpressionAttributeValues={':pk': 'USER#+919876543210'}
)
print(f"✓ Query successful - Found {response['Count']} items")

# Test GetItem
response = table.get_item(
    Key={'PK': 'USER#+919876543210', 'SK': 'PROFILE'}
)
print(f"✓ GetItem successful - User: {response['Item']['userId']}")
EOF

# Step 4: Upload FAO PDFs
echo ""
echo "Step 4: Uploading FAO PDFs..."
bash scripts/upload-fao-pdfs.sh $STACK_NAME

# Step 5: Start KB ingestion
echo ""
echo "Step 5: Starting Knowledge Base ingestion..."
DATA_SOURCE_ID=$(aws bedrock-agent list-data-sources \
  --knowledge-base-id $KB_ID \
  --region $REGION \
  --query 'dataSourceSummaries[0].dataSourceId' \
  --output text)

INGESTION_JOB_ID=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID \
  --region $REGION \
  --query 'ingestionJob.ingestionJobId' \
  --output text)

echo "  Ingestion Job ID: $INGESTION_JOB_ID"
echo "  Monitoring ingestion status..."

# Poll ingestion status
while true; do
  STATUS=$(aws bedrock-agent get-ingestion-job \
    --knowledge-base-id $KB_ID \
    --data-source-id $DATA_SOURCE_ID \
    --ingestion-job-id $INGESTION_JOB_ID \
    --region $REGION \
    --query 'ingestionJob.status' \
    --output text)
  
  echo "  Status: $STATUS"
  
  if [ "$STATUS" = "COMPLETE" ]; then
    echo "✓ Ingestion complete!"
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo "✗ Ingestion failed!"
    exit 1
  fi
  
  sleep 10
done

# Step 6: Update test file with KB ID
echo ""
echo "Step 6: Updating test configuration..."
sed -i.bak "s/YOUR_KB_ID/$KB_ID/g" tests/test_golden_questions.py

# Step 7: Run golden questions test
echo ""
echo "Step 7: Running golden questions test..."
pip3 install -q boto3 pytest
pytest tests/test_golden_questions.py -v --tb=short

echo ""
echo "=========================================="
echo "Week 1 Setup Complete! ✓"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Review test results above"
echo "  2. Verify all 20 golden questions passed"
echo "  3. Check guardrails blocked banned pesticides"
echo "  4. Proceed to Week 2: WhatsApp + Nudge Engine"
echo ""
echo "Useful commands:"
echo "  # Query KB manually"
echo "  aws bedrock-agent-runtime retrieve-and-generate \\"
echo "    --input '{\"text\":\"Cotton mein aphids ka control kaise karein?\"}' \\"
echo "    --retrieve-and-generate-configuration file://kb-config.json"
echo ""
echo "  # View DynamoDB items"
echo "  aws dynamodb scan --table-name $TABLE_NAME --max-items 5"
echo ""
