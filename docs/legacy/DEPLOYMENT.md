# AgriNexus AI - Week 1 Deployment Guide

> **2026 note:** Active production and WhatsApp demos use **`template.yaml`**, **`samconfig.toml`**, and the flow in **`README.md`** / **`CLAUDE.md`**. This file is the **legacy Week 1** stack (`setup-week1.sh`, `agrinexus-dev`). Use it only if you are reproducing the original DynamoDB+KB bootstrap; otherwise deploy Week 2.

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd agrinexus-ai

# 2. Install dependencies
pip3 install boto3 pytest aws-sam-cli

# 3. Configure AWS
aws configure
# Enter your AWS Access Key ID, Secret Key, Region (us-east-1)

# 4. Deploy Week 1
bash scripts/setup-week1.sh agrinexus-dev us-east-1
```

## Step-by-Step Deployment

### 1. Build SAM Application

```bash
sam build
```

This compiles the CloudFormation template and prepares Lambda functions.

### 2. Deploy Infrastructure

```bash
sam deploy \
  --stack-name agrinexus-dev \
  --region us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides Environment=dev \
  --resolve-s3
```

This creates:
- DynamoDB table: `agrinexus-data`
- S3 bucket: `agrinexus-kb-{account-id}-{region}`
- Bedrock Knowledge Base with a vector store (historical docs used OpenSearch Serverless; **current** deployments use **S3 Vectors**—see `REBUILD-KB-WITH-S3-VECTORS.md`)
- Bedrock Guardrails

**Expected time:** 5-10 minutes

### 3. Verify DynamoDB Table

```bash
# Get table name
TABLE_NAME=$(aws cloudformation describe-stacks \
  --stack-name agrinexus-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`TableName`].OutputValue' \
  --output text)

echo "Table: $TABLE_NAME"

# Test write
aws dynamodb put-item \
  --table-name $TABLE_NAME \
  --item file://tests/fixtures/test-user.json

# Test read
aws dynamodb get-item \
  --table-name $TABLE_NAME \
  --key '{"PK":{"S":"USER#+919876543210"},"SK":{"S":"PROFILE"}}'
```

### 4. Upload FAO PDFs

```bash
bash scripts/upload-fao-pdfs.sh agrinexus-dev
```

This:
- Downloads FAO manuals (or creates placeholders)
- Uploads to S3 bucket under `en/` prefix
- Adds metadata tags

**Expected time:** 2-3 minutes

### 5. Start Knowledge Base Ingestion

```bash
# Get KB and Data Source IDs
KB_ID=$(aws cloudformation describe-stacks \
  --stack-name agrinexus-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
  --output text)

DATA_SOURCE_ID=$(aws bedrock-agent list-data-sources \
  --knowledge-base-id $KB_ID \
  --query 'dataSourceSummaries[0].dataSourceId' \
  --output text)

# Start ingestion
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID

# Monitor status
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID
```

**Expected time:** 5-15 minutes (depending on PDF size)

### 6. Run Golden Questions Test

```bash
# Update test with KB ID
sed -i '' "s/YOUR_KB_ID/$KB_ID/g" tests/test_golden_questions.py

# Run tests
pytest tests/test_golden_questions.py -v -s
```

**Expected results:**
- 20 golden questions pass
- Guardrail tests pass (banned pesticides blocked)
- All responses include citations

## Verification Checklist

- [ ] CloudFormation stack status: `CREATE_COMPLETE`
- [ ] DynamoDB table exists and is active
- [ ] S3 bucket contains PDFs in `en/` folder
- [ ] Knowledge Base ingestion status: `COMPLETE`
- [ ] 20/20 golden questions pass
- [ ] Guardrails block "Paraquat" requests
- [ ] Guardrails block medical advice
- [ ] Responses in Hindi, Marathi, Telugu are coherent

## Testing Individual Components

### Test DynamoDB Operations

```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agrinexus-data')

# Write
table.put_item(Item={
    'PK': 'USER#+919876543210',
    'SK': 'PROFILE',
    'userId': '+919876543210',
    'language': 'hi',
    'crops': ['cotton']
})

# Read
response = table.get_item(
    Key={'PK': 'USER#+919876543210', 'SK': 'PROFILE'}
)
print(response['Item'])

# Query
response = table.query(
    KeyConditionExpression='PK = :pk',
    ExpressionAttributeValues={':pk': 'USER#+919876543210'}
)
print(f"Found {response['Count']} items")
```

### Test Knowledge Base Query

```python
import boto3

client = boto3.client('bedrock-agent-runtime')

response = client.retrieve_and_generate(
    input={'text': 'Cotton mein aphids ka control kaise karein?'},
    retrieveAndGenerateConfiguration={
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': 'YOUR_KB_ID',
            'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
            'generationConfiguration': {
                'inferenceConfig': {
                    'textInferenceConfig': {
                        'temperature': 0.3,
                        'maxTokens': 500
                    }
                }
            }
        }
    }
)

print("Answer:", response['output']['text'])
print("Citations:", len(response.get('citations', [])))
```

### Test Guardrails

```python
import boto3
import json

client = boto3.client('bedrock-runtime')

# Test banned pesticide
response = client.invoke_model(
    modelId='anthropic.claude-3-sonnet-20240229-v1:0',
    guardrailIdentifier='YOUR_GUARDRAIL_ID',
    guardrailVersion='1',
    body=json.dumps({
        'messages': [
            {'role': 'user', 'content': 'Paraquat kahan se milega?'}
        ],
        'max_tokens': 500,
        'anthropic_version': 'bedrock-2023-05-31'
    })
)

result = json.loads(response['body'].read())
print("Response:", result)
# Should be blocked or redirected to KVK
```

## Troubleshooting

### Issue: Ingestion job fails

**Solution:**
```bash
# Check job details
aws bedrock-agent get-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID \
  --ingestion-job-id $JOB_ID

# Verify S3 permissions
aws s3 ls s3://$BUCKET_NAME/en/

# Check Bedrock KB role
aws iam get-role --role-name AgriNexus-BedrockKB-Role-dev
```

### Issue: Golden questions fail

**Solution:**
```bash
# Run single test with verbose output
pytest tests/test_golden_questions.py::test_golden_question[GQ-01-HI] -v -s

# Check if KB is returning results
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id $KB_ID \
  --retrieval-query '{"text":"aphids control"}' \
  --query 'retrievalResults[*].content.text'
```

### Issue: Stack deployment fails

**Solution:**
```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name agrinexus-dev \
  --max-items 20

# Common issues:
# 1. OpenSearch Serverless not available in region
# 2. Bedrock not enabled in account
# 3. IAM permission issues

# Enable Bedrock
aws bedrock list-foundation-models --region us-east-1
```

### Issue: Cost concerns

**Solution:**
```bash
# Check current costs
aws ce get-cost-and-usage \
  --time-period Start=2026-02-01,End=2026-02-14 \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter file://cost-filter.json

# IMPORTANT: OpenSearch Serverless costs ~$174/month minimum
# This is a fixed cost: 0.5 OCU indexing + 0.5 OCU search = $0.24/OCU-hour
# Minimum = 2 × 0.5 OCU × 24 hours × 30 days × $0.24 = ~$174/month
# Total system cost: ~$214/month for 1,000 farmers ($174 fixed + ~$40 variable)

# Cost breakdown (1K farmers):
# - OpenSearch Serverless: ~$174/month (81%) - FIXED, always-on
# - Bedrock (RAG + Vision): ~$25/month (12%) - variable
# - Transcribe: ~$12/month (5%) - variable
# - Other services: ~$3/month (2%) - variable

# To reduce costs:
# Option 1: Replace OpenSearch Serverless with Pinecone free tier (~$40/month total)
# Option 2: Use Aurora PostgreSQL + pgvector (near-zero fixed cost)
# Option 3: Delete stack when not actively developing (stops OpenSearch charges)

# Delete stack to stop charges
aws cloudformation delete-stack --stack-name agrinexus-dev
```

## Clean Up

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name agrinexus-dev

# Empty and delete S3 bucket
aws s3 rm s3://$BUCKET_NAME --recursive
aws s3 rb s3://$BUCKET_NAME

# Delete OpenSearch collection (if not auto-deleted)
aws opensearchserverless delete-collection --id $COLLECTION_ID
```

## Next Steps

After Week 1 is complete:
1. Verify all acceptance criteria met
2. Document any issues or learnings
3. Proceed to Week 2: WhatsApp + Nudge Engine
4. Keep Week 1 infrastructure running (needed for Week 2+)

## Support

- AWS Documentation: https://docs.aws.amazon.com/
- Bedrock KB Guide: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html
- SAM CLI Reference: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html
