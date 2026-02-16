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
├── README.md                        # This file
├── requirements.md                  # EARS requirements
├── architecture.md                  # Architecture design
├── design.md                        # Technical design
├── scripts/
│   ├── setup-week1.sh              # Week 1 deployment script
│   ├── upload-fao-pdfs.sh          # Upload FAO manuals
│   ├── download-official-sources.sh # Download Indian govt sources
│   └── prepare-pest-management-docs.sh # Prepare knowledge base docs
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

### Next Steps: Week 2

- WhatsApp webhook handler with signature validation
- Onboarding flow with Interactive Buttons
- Weather poller + Step Functions (short-lived)
- EventBridge Scheduler for reminders (T+24h, T+48h, T+72h)
- Response detector (DynamoDB Streams)
- Closed-loop testing: nudge → reminder → DONE

### Cost Breakdown (Week 1)

| Service | Usage | Free Tier | Cost |
|---------|-------|-----------|------|
| DynamoDB | 1M reads, 500K writes | 25 GB, 25 WCU/RCU | $0 |
| S3 | 100 MB PDFs | 5 GB | $0 |
| Bedrock KB | 1K queries | Pay-as-you-go | ~$5 |
| OpenSearch Serverless | 1 OCU (indexing + search) | Pay-as-you-go | ~$20 |
| Lambda | 10K invocations | 1M free | $0 |
| **Total** | | | **~$25/month** |

**Note**: OpenSearch Serverless is the primary cost driver for Week 1. This is a fixed minimum cost (~$0.24/hour per OCU) even with low usage. For production at scale, consider Aurora Serverless v2 as an alternative vector store.

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
