# AgriNexus AI - MVP Implementation

Behavioral intervention engine for smallholder farmers. AWS 10,000 AIdeas Competition submission.

## Architecture

- **Serverless**: Lambda, DynamoDB, EventBridge Scheduler
- **AI**: Amazon Bedrock (Claude 3 Sonnet + Vision), Transcribe, Polly
- **Storage**: DynamoDB single-table design, S3 for knowledge base
- **Cost**: ~$50/month for 1,000 users (free-tier-leaning with pay-as-you-go Bedrock + OpenSearch Serverless)

## Week 1: Foundation + Knowledge Base ✓

### What's Included

1. **SAM Template** (`template.yaml`)
   - DynamoDB single table (`agrinexus-data`) with GSIs and Streams
   - S3 bucket for FAO PDF manuals
   - Bedrock Knowledge Base with OpenSearch Serverless vector store
   - Bedrock Guardrails (banned pesticides, medical advice blocking)

2. **Scripts**
   - `scripts/setup-week1.sh` - Complete Week 1 deployment
   - `scripts/upload-fao-pdfs.sh` - Upload FAO manuals to S3

3. **Tests**
   - `tests/test_golden_questions.py` - 20 golden questions across Hindi, Marathi, Telugu
   - Guardrail tests for banned pesticides and medical advice

### Prerequisites

```bash
# Install AWS SAM CLI
brew install aws-sam-cli  # macOS

# Install Python dependencies
pip3 install boto3 pytest

# Configure AWS credentials
aws configure
```

### Deployment

```bash
# Deploy Week 1 infrastructure
bash scripts/setup-week1.sh agrinexus-dev us-east-1

# This will:
# 1. Deploy SAM template (DynamoDB + Bedrock KB + Guardrails)
# 2. Test DynamoDB operations (PutItem, Query, GetItem)
# 3. Upload FAO PDFs to S3
# 4. Start KB ingestion job
# 5. Run 20 golden questions test suite
```

### Manual Testing

```bash
# Test DynamoDB
aws dynamodb put-item \
  --table-name agrinexus-data \
  --item file://tests/fixtures/test-user.json

aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"USER#+919876543210"}}'

# Test Bedrock Knowledge Base
aws bedrock-agent-runtime retrieve-and-generate \
  --input '{"text":"Cotton mein aphids ka control kaise karein?"}' \
  --retrieve-and-generate-configuration '{
    "type": "KNOWLEDGE_BASE",
    "knowledgeBaseConfiguration": {
      "knowledgeBaseId": "YOUR_KB_ID",
      "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
    }
  }'

# Test Guardrails
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-sonnet-20240229-v1:0 \
  --guardrail-identifier YOUR_GUARDRAIL_ID \
  --guardrail-version 1 \
  --body '{"messages":[{"role":"user","content":"Paraquat kahan se milega?"}],"max_tokens":500}' \
  output.json
```

### Week 1 Acceptance Criteria

- [x] DynamoDB table created with single-table design
- [x] PutItem, Query, GetItem operations work
- [x] S3 bucket contains FAO manuals in `en/` prefix
- [x] Bedrock Knowledge Base ingestion complete
- [x] 20 golden questions pass (Hindi, Marathi, Telugu)
- [x] Guardrails block banned pesticides (Paraquat, Monocrotophos, Endosulfan)
- [x] Guardrails block medical advice requests
- [x] Responses include source citations from FAO manuals

### Project Structure

```
.
├── template.yaml                    # SAM template (Week 1)
├── template-week2.yaml              # SAM template (Week 2)
├── README.md                        # This file
├── requirements.md                  # EARS requirements
├── architecture.md                  # Architecture design
├── design.md                        # Technical design
├── scripts/
│   ├── setup-week1.sh              # Week 1 deployment script
│   ├── deploy-week2.sh             # Week 2 deployment script
│   ├── upload-fao-pdfs.sh          # Upload FAO manuals
│   ├── download-official-sources.sh # Download Indian govt sources
│   └── prepare-pest-management-docs.sh # Prepare knowledge base docs
├── src/
│   ├── webhook/                    # WhatsApp webhook handler
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── processor/                  # Message processor with RAG
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── dlq/                        # Dead letter queue handler
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── weather/                    # Weather poller
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── nudge/                      # Nudge engine
│       ├── sender.py               # Nudge sender
│       ├── reminder.py             # Reminder sender
│       ├── detector.py             # Response detector
│       └── requirements.txt
├── statemachine/
│   └── nudge-workflow.asl.json     # Step Functions definition
├── tests/
│   ├── test_golden_questions.py    # 20 golden questions
│   ├── test_golden_questions_realistic.py # Realistic test scenarios
│   └── fixtures/
│       ├── test-user.json          # Test data
│       └── valid_pesticides.py     # Approved pesticide list
└── data/
    └── fao-pdfs/                    # Agricultural knowledge base sources
        └── en/
            ├── cotton-production.pdf        # FAO cotton production guide
            ├── ipm-guide.pdf               # FAO IPM guide
            ├── pesticide-application.pdf   # FAO pesticide safety
            └── new-sources/                # Indian agricultural institution sources
                ├── kb_manifest.csv                          # Source metadata & licensing
                ├── icar-cicr-pest-disease-advisory-2024.pdf # ICAR-CICR comprehensive ETLs
                ├── pau-package-of-practices-kharif-2024.pdf # Punjab Agricultural Univ
                ├── niphm-cotton-advisory-2022.pdf           # National IPM Centre
                ├── nriipm-crop-sap-book.pdf                 # NRIIPM sustainable practices
                ├── ipm-cotton-2024.pdf                      # General IPM (ResearchGate)
                ├── ipm-bt-cotton.pdf                        # Bt cotton IPM (ResearchGate)
                └── rajendran-2018-cotton-pests.pdf          # Cotton pests reference (ResearchGate)
```

**Note on Sources**: The `fao-pdfs` directory name is historical. It now contains both FAO manuals and Indian agricultural research institution documents (ICAR, NIPHM, PAU, NRIIPM). See `kb_manifest.csv` for source URLs, licensing, and ETL threshold information.

### Next Steps: Week 2 ✓

Week 2 is now complete! See below for WhatsApp integration details.

## Week 2: WhatsApp Integration + Behavioral Nudge Engine ✓

### What's Included

1. **WhatsApp Business API Integration**
   - Webhook handler with Meta signature validation
   - Idempotency using DynamoDB (prevents duplicate message processing)
   - SQS FIFO queue for reliable message processing
   - Message processor with Bedrock RAG integration

2. **Onboarding Flow**
   - Multi-step state machine (language → location → crop → consent)
   - Support for Hindi, Marathi, Telugu
   - User profile storage in DynamoDB
   - Validation for districts (Aurangabad, Jalna, Nagpur) and crops (Cotton, Soybean, Maize)

3. **Behavioral Nudge Engine**
   - Weather poller (runs every 6 hours)
   - Step Functions workflow for nudge orchestration
   - EventBridge Scheduler for T+24h and T+48h reminders
   - Response detector using DynamoDB Streams (detects DONE/NOT YET responses)

4. **SAM Template** (`template-week2.yaml`)
   - API Gateway for WhatsApp webhook
   - 7 Lambda functions (webhook, processor, DLQ, weather, nudge sender, reminder, response detector)
   - SQS FIFO queue with DLQ
   - Step Functions state machine
   - EventBridge Scheduler integration

### Prerequisites

In addition to Week 1 prerequisites:

```bash
# Meta Developer Account
# 1. Create WhatsApp Business App at developers.facebook.com
# 2. Get Phone Number ID and Access Token
# 3. Configure webhook URL

# Store WhatsApp credentials in AWS Secrets Manager
aws secretsmanager create-secret \
  --name agrinexus/whatsapp/verify-token \
  --secret-string "your-verify-token"

aws secretsmanager create-secret \
  --name agrinexus/whatsapp/access-token \
  --secret-string "your-permanent-access-token"

aws secretsmanager create-secret \
  --name agrinexus/whatsapp/phone-number-id \
  --secret-string "your-phone-number-id"
```

### Deployment

```bash
# Deploy Week 2 (requires Week 1 to be deployed first)
bash scripts/deploy-week2.sh

# This will:
# 1. Verify Week 1 resources exist
# 2. Get Knowledge Base ID and Guardrail ID
# 3. Build Lambda functions
# 4. Deploy Week 2 SAM template
# 5. Output webhook URL for Meta configuration
```

### Meta Webhook Configuration

1. Go to Meta Developer Portal → Your App → WhatsApp → Configuration
2. Set Callback URL to your webhook URL (from deployment output)
3. Set Verify Token (same as in Secrets Manager)
4. Subscribe to webhook field: `messages`
5. Generate permanent access token from System User (not temporary token)

### Testing WhatsApp Integration

```bash
# Test webhook verification (GET request)
curl "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"

# Send test message via Meta API
curl -X POST "https://graph.facebook.com/v22.0/YOUR_PHONE_NUMBER_ID/messages" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "YOUR_TEST_NUMBER",
    "type": "text",
    "text": {"body": "Hello from AgriNexus AI"}
  }'

# Check CloudWatch logs
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow
aws logs tail /aws/lambda/agrinexus-processor-dev --follow
```

### Week 2 User Flow

1. **Onboarding** (first-time user):
   - User sends any message to WhatsApp Business number
   - Bot asks for language preference (Hindi/Marathi/Telugu)
   - Bot asks for location (district)
   - Bot asks for crop type
   - Bot asks for weather nudge consent
   - Profile saved to DynamoDB

2. **RAG Queries** (after onboarding):
   - User asks farming question in their language
   - Message queued to SQS
   - Processor queries Bedrock Knowledge Base
   - Response generated in user's dialect with citations
   - Response sent via WhatsApp API

3. **Weather Nudges** (if consent given):
   - Weather poller runs every 6 hours
   - Checks weather conditions for user's location
   - Triggers Step Functions workflow if action needed
   - Sends nudge via WhatsApp
   - Schedules T+24h and T+48h reminders
   - Response detector monitors for DONE/NOT YET replies

### Week 2 Acceptance Criteria

- [x] WhatsApp webhook receives and validates messages
- [x] Idempotency prevents duplicate processing
- [x] Onboarding flow completes in Hindi/Marathi/Telugu
- [x] User profile stored in DynamoDB
- [x] RAG queries return responses with citations
- [x] Messages sent via WhatsApp API successfully
- [x] Weather poller triggers nudge workflow
- [x] Reminders scheduled via EventBridge Scheduler
- [x] Response detector processes DONE/NOT YET replies
- [x] DLQ handles failed messages with dialect-aware errors

### Cost Breakdown (Week 1 + Week 2)

| Service | Usage | Free Tier | Cost |
|---------|-------|-----------|------|
| DynamoDB | 1M reads, 500K writes | 25 GB, 25 WCU/RCU | $0 |
| DynamoDB Streams | 1M stream reads | Pay-as-you-go | ~$0.50 |
| S3 | 100 MB PDFs | 5 GB | $0 |
| Bedrock KB | 1K queries | Pay-as-you-go | ~$5 |
| OpenSearch Serverless | 1 OCU | Pay-as-you-go | ~$20 |
| Lambda | 50K invocations | 1M free | $0 |
| API Gateway | 10K requests | 1M free | $0 |
| SQS | 100K messages | 1M free | $0 |
| Step Functions | 100 executions | 4K free | $0 |
| EventBridge Scheduler | 1K schedules | Pay-as-you-go | ~$1 |
| **Total** | | | **~$26.50/month** |

**Note**: Costs scale with usage. WhatsApp API calls are free for first 1,000 conversations/month, then $0.005-0.009 per conversation depending on region.

### Troubleshooting

**Ingestion job fails:**
```bash
# Check ingestion job logs
aws bedrock-agent get-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_DS_ID \
  --ingestion-job-id YOUR_JOB_ID

# Verify S3 bucket permissions
aws s3 ls s3://YOUR_BUCKET/en/
```

**Golden questions fail:**
```bash
# Run individual test
pytest tests/test_golden_questions.py::test_golden_question[GQ-01-HI] -v -s

# Check KB query directly
python3 -c "
import boto3
client = boto3.client('bedrock-agent-runtime')
response = client.retrieve_and_generate(
    input={'text': 'Cotton mein aphids ka control kaise karein?'},
    retrieveAndGenerateConfiguration={
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': 'YOUR_KB_ID',
            'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
        }
    }
)
print(response['output']['text'])
"
```

### Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [DynamoDB Single Table Design](https://aws.amazon.com/blogs/compute/creating-a-single-table-design-with-amazon-dynamodb/)

### Support

For issues or questions:
1. Check CloudWatch Logs for Lambda errors
2. Review CloudFormation stack events
3. Verify IAM permissions for Bedrock KB role
4. Contact local KVK for agricultural advice (not technical support!)
