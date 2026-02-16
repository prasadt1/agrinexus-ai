# Week 2: WhatsApp Integration + Behavioral Nudge Engine

## Overview

Week 2 adds the core behavioral intervention capabilities:
- WhatsApp webhook handler with signature validation
- Onboarding flow with Interactive Buttons
- Weather-triggered behavioral nudges
- EventBridge Scheduler for T+24h and T+48h reminders
- Response detector via DynamoDB Streams
- Closed-loop testing: nudge → reminder → DONE

## Architecture

```
WhatsApp → API Gateway → Webhook Handler → SQS → Message Processor → Bedrock
                                                                    ↓
                                                                DynamoDB
                                                                    ↑
Weather Poller → Step Functions → Nudge Sender → EventBridge Scheduler
(every 6h)                                              ↓
                                                  Reminder Sender
                                                        ↑
                                            DynamoDB Streams → Response Detector
```

## Components

### 1. WhatsApp Webhook Handler
- **Function**: `src/webhook/handler.py`
- **Purpose**: Validates webhook signature, queues messages
- **Key Features**:
  - X-Hub-Signature-256 validation
  - Idempotency using wamid
  - Returns HTTP 200 within 2 seconds
  - Async processing via SQS

### 2. Message Processor
- **Function**: `src/processor/handler.py`
- **Purpose**: Processes messages, interacts with Bedrock
- **Key Features**:
  - User profile management
  - Bedrock RAG queries
  - Dialect-aware responses
  - Source citations

### 3. Weather Poller
- **Function**: `src/weather/handler.py`
- **Purpose**: Checks weather every 6 hours
- **Trigger Conditions**:
  - Wind speed < 10 km/h
  - No rain forecast
- **Action**: Triggers Step Functions workflow

### 4. Nudge Sender
- **Function**: `src/nudge/sender.py`
- **Purpose**: Sends behavioral nudges
- **Key Features**:
  - Dialect-specific templates
  - Creates DynamoDB nudge records
  - Schedules T+24h and T+48h reminders

### 5. Reminder Sender
- **Function**: `src/nudge/reminder.py`
- **Purpose**: Sends reminders if task not completed
- **Triggered By**: EventBridge Scheduler

### 6. Response Detector
- **Function**: `src/nudge/detector.py`
- **Purpose**: Detects DONE/NOT YET keywords
- **Triggered By**: DynamoDB Streams
- **Key Features**:
  - Multi-dialect keyword detection
  - Updates nudge status to DONE
  - Deletes scheduled reminders

### 7. DLQ Handler
- **Function**: `src/dlq/handler.py`
- **Purpose**: Handles failed messages
- **Key Features**:
  - Dialect-aware error messages
  - Reads user profile for language preference

## Deployment

### Prerequisites

1. Complete Week 1 deployment
2. WhatsApp Business API account
3. Weather API key (OpenWeatherMap)

### Setup

```bash
# 1. Deploy Week 2 infrastructure
sam build -t template-week2.yaml
sam deploy --guided

# 2. Configure secrets
aws secretsmanager update-secret \
  --secret-id agrinexus-whatsapp-dev \
  --secret-string '{
    "VERIFY_TOKEN": "your_verify_token",
    "ACCESS_TOKEN": "your_whatsapp_access_token",
    "PHONE_NUMBER_ID": "your_phone_number_id",
    "WEBHOOK_SECRET": "your_webhook_secret"
  }'

aws secretsmanager update-secret \
  --secret-id agrinexus-weather-dev \
  --secret-string '{
    "API_KEY": "your_openweathermap_api_key",
    "BASE_URL": "https://api.openweathermap.org/data/2.5"
  }'

# 3. Configure WhatsApp webhook
# Get webhook URL from stack outputs
WEBHOOK_URL=$(aws cloudformation describe-stacks \
  --stack-name agrinexus-week2 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
  --output text)

echo "Configure this URL in WhatsApp Business API: $WEBHOOK_URL"
```

### Testing

```bash
# Test webhook verification (GET)
curl "$WEBHOOK_URL?hub.mode=subscribe&hub.verify_token=your_verify_token&hub.challenge=test123"

# Test message processing (POST)
# Send a test message via WhatsApp to your business number

# Check SQS queue
aws sqs get-queue-attributes \
  --queue-url $(aws cloudformation describe-stacks \
    --stack-name agrinexus-week2 \
    --query 'Stacks[0].Outputs[?OutputKey==`MessageQueueUrl`].OutputValue' \
    --output text) \
  --attribute-names ApproximateNumberOfMessages

# Trigger weather poller manually
aws lambda invoke \
  --function-name agrinexus-weather-dev \
  --payload '{}' \
  response.json

cat response.json
```

## Closed-Loop Testing

### Scenario: Aurangabad Cotton Farmer

1. **Setup**: Create test user profile
```python
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agrinexus-data')

table.put_item(Item={
    'PK': 'USER#+919876543210',
    'SK': 'PROFILE',
    'phone_number': '+919876543210',
    'dialect': 'hi',
    'location': 'Aurangabad,IN',
    'crop': 'cotton'
})
```

2. **Trigger**: Run weather poller
```bash
aws lambda invoke \
  --function-name agrinexus-weather-dev \
  --payload '{}' \
  response.json
```

3. **Verify**: Check nudge sent
```bash
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{
    ":pk": {"S": "USER#+919876543210"},
    ":sk": {"S": "NUDGE#"}
  }'
```

4. **Simulate Response**: Send "हो गया" message
```python
# Simulate message via webhook
# This will trigger Response Detector via DynamoDB Streams
```

5. **Verify Completion**: Check nudge status updated to DONE
```bash
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{
    ":pk": {"S": "USER#+919876543210"},
    ":sk": {"S": "NUDGE#"}
  }' \
  --filter-expression "#status = :status" \
  --expression-attribute-names '{"#status": "status"}' \
  --expression-attribute-values '{":status": {"S": "DONE"}}'
```

## Monitoring

### CloudWatch Metrics

- `NudgesSent`: Total nudges sent
- `NudgesCompleted`: Total nudges marked DONE
- `CompletionRate`: (NudgesCompleted / NudgesSent) × 100
- `MessageVolume`: Messages processed per hour
- `DLQDepth`: Messages in dead letter queue

### CloudWatch Logs

- `/aws/lambda/agrinexus-webhook-dev`
- `/aws/lambda/agrinexus-processor-dev`
- `/aws/lambda/agrinexus-weather-dev`
- `/aws/lambda/agrinexus-nudge-sender-dev`
- `/aws/lambda/agrinexus-reminder-dev`
- `/aws/lambda/agrinexus-response-detector-dev`

## Cost Estimate

| Service | Usage | Cost |
|---------|-------|------|
| API Gateway | 10K requests | $0.04 |
| Lambda | 50K invocations | $0.10 |
| SQS | 10K messages | $0.00 |
| EventBridge Scheduler | 1K schedules | $1.00 |
| DynamoDB Streams | 10K records | $0.02 |
| Secrets Manager | 2 secrets | $0.80 |
| **Week 2 Total** | | **~$2/month** |
| **Week 1 + Week 2** | | **~$27/month** |

## Next Steps

- Implement onboarding flow with Interactive Buttons
- Add Claude Vision for image processing
- Add Transcribe + Polly for voice
- Build CloudWatch Dashboard
- Create end-to-end integration tests

## Troubleshooting

### Webhook not receiving messages
- Verify WhatsApp webhook configuration
- Check API Gateway logs
- Verify signature validation

### Nudges not sending
- Check weather poller logs
- Verify Step Functions execution
- Check DynamoDB for nudge records

### Reminders not triggering
- Verify EventBridge Scheduler created
- Check Scheduler execution logs
- Verify IAM role permissions

### Response detection not working
- Check DynamoDB Streams enabled
- Verify Response Detector logs
- Test keyword matching logic
