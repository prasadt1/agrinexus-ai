# AgriNexus AI - WhatsApp Agricultural Advisory System

Behavioral intervention engine for smallholder farmers. AWS 10,000 AIdeas Competition submission.

## 🎯 Competition Status: Week 3 Complete ✅

All core features implemented and tested:
- ✅ RAG-based agricultural Q&A (4 languages)
- ✅ Voice input (Amazon Transcribe)
- ✅ Voice output (Amazon Polly)
- ✅ Vision analysis (Claude 3 Sonnet - pest/disease identification)
- ✅ Behavioral nudges with weather triggers
- ✅ Multi-language support (Hindi, Marathi, Telugu, English)

## Architecture

- **Serverless**: Lambda, DynamoDB, EventBridge Scheduler, Step Functions
- **AI**: Amazon Bedrock (Claude 3 Sonnet + RAG), Transcribe, Polly, Claude Vision
- **Messaging**: WhatsApp Business API
- **Storage**: DynamoDB single-table design, S3 for knowledge base + temp audio
- **Cost**: ~$50/month for 1,000 users (includes WhatsApp, Bedrock, OpenSearch Serverless)

## Features

### 1. Multi-Modal Input
- **Text**: Type questions in Hindi, Marathi, Telugu, or English
- **Voice**: Send voice notes - automatically transcribed and processed
- **Images**: Send crop photos for pest/disease identification

### 2. Intelligent Responses
- **RAG System**: Answers based on FAO manuals + Indian agricultural research
- **Source Citations**: Every response includes references
- **Multi-Language**: Responds in user's preferred language
- **Voice Output**: Optional audio responses (Hindi, Marathi, English)

### 3. Behavioral Nudges
- **Weather-Based**: Spray reminders when conditions are optimal
- **Closed-Loop**: Tracks completion with "हो गया" (done) responses
- **Smart Reminders**: T+24h and T+48h follow-ups if not completed
- **Duplicate Prevention**: Max 1 nudge per activity per day

### 4. Vision Analysis
- **Pest Identification**: Bollworm, aphids, whitefly, etc.
- **Disease Detection**: Leaf curl, wilt, blight, etc.
- **Nutrient Deficiency**: Nitrogen, potassium deficiencies
- **Actionable Advice**: Specific pesticides, dosages, timing, prevention

### 5. Safety Features
- **Domain Restrictions**: Only answers farming questions (no medical advice)
- **Guardrails**: Blocks banned pesticides (optional)
- **Error Handling**: Dialect-aware error messages via DLQ

## Quick Start

### Prerequisites

```bash
# Install AWS SAM CLI
brew install aws-sam-cli  # macOS
# or: pip install aws-sam-cli

# Install Python dependencies
pip3 install boto3 pytest

# Configure AWS credentials
aws configure
```

### Deployment

```bash
# 1. Deploy infrastructure
sam build --template template-week2.yaml
sam deploy --template-file .aws-sam/build/template.yaml \
  --stack-name agrinexus-week2 \
  --parameter-overrides "KnowledgeBaseId=YOUR_KB_ID GuardrailId='' Environment=dev TableName=agrinexus-data GuardrailVersion=1" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --resolve-s3

# 2. Configure WhatsApp secrets
aws secretsmanager create-secret \
  --name agrinexus/whatsapp/verify-token \
  --secret-string "YOUR_VERIFY_TOKEN"

aws secretsmanager create-secret \
  --name agrinexus/whatsapp/app-secret \
  --secret-string "YOUR_APP_SECRET"

aws secretsmanager create-secret \
  --name agrinexus/whatsapp/access-token \
  --secret-string "YOUR_PERMANENT_ACCESS_TOKEN"

aws secretsmanager create-secret \
  --name agrinexus/whatsapp/phone-number-id \
  --secret-string "YOUR_PHONE_NUMBER_ID"

# 3. Configure Meta webhook
# Go to Meta Developer Portal → WhatsApp → Configuration
# Set Callback URL to your webhook URL (from deployment output)
# Subscribe to 'messages' field
```

## Usage

### HELP Command
Send `HELP` (or `मदद`, `मदत`, `సహాయం`) to see available features.

### Text Questions
```
User: कपास में कीट कैसे नियंत्रित करें?
Bot: कपास में कीटों को नियंत्रित करने के लिए...
```

### Voice Input
Send a voice note asking your question - it will be transcribed and answered.

### Image Analysis
Send a photo of your crop - the bot will identify pests/diseases and provide recommendations.

### Behavioral Nudges
If you consent during onboarding, you'll receive weather-based spray reminders:
```
Bot: आज स्प्रे करने के लिए अच्छा मौसम है। हवा 8.5 km/h है और बारिश नहीं होगी। क्या आपने स्प्रे कर दिया?

कृपया "हो गया" भेजें जब आप स्प्रे कर लें।

User: हो गया
Bot: बढ़िया! आपने स्प्रे कर दिया। धन्यवाद!
```

## Project Structure

```
.
├── template-week2.yaml              # SAM template (complete system)
├── README.md                        # This file
├── CHANGELOG.md                     # Engineering changelog
├── ISSUES-LOG.md                    # Debugging log
├── scripts/
│   ├── deploy-week2.sh             # Deployment script
│   └── upload-fao-pdfs.sh          # Upload knowledge base docs
├── src/
│   ├── webhook/                    # WhatsApp webhook handler
│   ├── processor/                  # Message processor with RAG + voice + vision
│   ├── voice/                      # Voice input (Transcribe)
│   ├── dlq/                        # Dead letter queue handler
│   ├── weather/                    # Weather poller
│   └── nudge/                      # Nudge engine (sender, reminder, detector)
├── statemachine/
│   └── nudge-workflow.asl.json     # Step Functions workflow
├── tests/
│   ├── test_golden_questions.py    # RAG tests
│   ├── test_voice_*.py             # Voice tests
│   └── test_vision.py              # Vision tests
└── data/
    └── fao-pdfs/                    # Knowledge base sources
        └── en/
            ├── cotton-production.pdf
            ├── ipm-guide.pdf
            └── new-sources/         # Indian agricultural research
                ├── icar-cicr-pest-disease-advisory-2024.pdf
                ├── pau-package-of-practices-kharif-2024.pdf
                └── ...
```

## Testing

### Text RAG
```bash
pytest tests/test_golden_questions.py -v
```

### Voice Input
```bash
# Test with your own voice recording
python tests/test_voice_simple.py path/to/audio.mp3 hi cotton
```

### Vision Analysis
```bash
# Test with crop image
python tests/test_vision.py path/to/image.jpg en cotton
```

### End-to-End Voice Round-Trip
```bash
# Voice in → Transcribe → RAG → Voice out
python tests/test_voice_end_to_end.py
```

## Architecture Details

### Lambda Functions
1. **WebhookHandler**: Receives WhatsApp messages, routes to appropriate queue
2. **MessageProcessor**: Handles text/image messages, RAG queries, voice output
3. **VoiceProcessor**: Transcribes voice notes, queues as text
4. **NudgeSender**: Sends behavioral nudges, schedules reminders
5. **ReminderSender**: Sends T+24h and T+48h reminders
6. **ResponseDetector**: Detects DONE/NOT YET responses via DynamoDB Streams
7. **WeatherPoller**: Checks weather, triggers nudge workflow
8. **DLQHandler**: Handles failed messages with dialect-aware errors

### Data Flow

**Text Query:**
```
WhatsApp → Webhook → SQS → Processor → Bedrock RAG → WhatsApp
```

**Voice Query:**
```
WhatsApp → Webhook → VoiceQueue → VoiceProcessor → Transcribe → SQS → Processor → Bedrock RAG → Polly → WhatsApp
```

**Image Query:**
```
WhatsApp → Webhook → SQS → Processor → Claude Vision → WhatsApp
```

**Nudge Flow:**
```
Weather Poller → Step Functions → Nudge Sender → WhatsApp
                                → EventBridge Scheduler (T+24h, T+48h)
                                → Reminder Sender → WhatsApp
```

## Cost Breakdown

| Service | Usage (1K users) | Monthly Cost |
|---------|------------------|--------------|
| DynamoDB | 1M reads, 500K writes | $0 (free tier) |
| DynamoDB Streams | 1M stream reads | ~$0.50 |
| S3 | 100 MB docs + temp audio | $0 (free tier) |
| Bedrock KB | 1K queries | ~$5 |
| Bedrock Vision | 100 images | ~$3 |
| OpenSearch Serverless | 1 OCU | ~$20 |
| Transcribe | 100 voice notes | ~$2 |
| Polly | 100 responses | ~$0.50 |
| Lambda | 50K invocations | $0 (free tier) |
| API Gateway | 10K requests | $0 (free tier) |
| SQS | 100K messages | $0 (free tier) |
| Step Functions | 100 executions | $0 (free tier) |
| EventBridge Scheduler | 1K schedules | ~$1 |
| **Total** | | **~$32/month** |

**Note**: WhatsApp API is free for first 1,000 conversations/month.

## Known Limitations

1. **Voice Input Latency**: 20-34 seconds (batch transcription). Post-MVP: migrate to Transcribe Streaming for <2s latency.
2. **Telugu Voice Output**: No native Telugu voice in Polly. Text-only responses for Telugu users.
3. **WhatsApp Test Numbers**: Don't support media (voice/images). Requires real WhatsApp Business number for end-to-end testing.
4. **Weather Data**: Currently mock data. Post-MVP: integrate real weather API.

## Troubleshooting

### Check Logs
```bash
# Webhook
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow

# Processor
aws logs tail /aws/lambda/agrinexus-processor-dev --follow

# Voice
aws logs tail /aws/lambda/agrinexus-voice-dev --follow
```

### Test Components
```bash
# Test webhook
curl "https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test"

# Test voice processor
aws lambda invoke --function-name agrinexus-voice-dev --payload '{}' /tmp/response.json

# Test weather poller
aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/response.json
```

## Monitoring

Create the CloudWatch dashboard (dev example):

```bash
./scripts/create-cloudwatch-dashboard.sh dev us-east-1
```

**Custom Metrics**:
- `AgriNexus/NudgesSent`
- `AgriNexus/NudgesCompleted`

The dashboard includes a completion rate widget based on these metrics.

## Real Weather API (Optional)

By default, the system uses mocked weather for demo reliability. To use real weather:

```bash
USE_REAL_WEATHER=true
WEATHER_API_KEY="YOUR_OPENWEATHER_API_KEY"
```

These are configured via Lambda environment variables (see `template-week2.yaml`).

## Real-Time Multi-Language Nudge Testing

1. Complete onboarding in each language:
   - Hindi: send `हिंदी`
   - Marathi: send `मराठी`
   - Telugu: send `తెలుగు`
   - English: send `English`
2. Use the same district (e.g., Aurangabad) to keep demo deterministic.
3. Trigger the weather poller:
   ```bash
   aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/response.json
   ```
4. Reply with:
   - DONE: `हो गया`, `झाला`, `అయ్యింది`, or `DONE`
   - NOT YET: `अभी नहीं`, `नाही झाला`, `ఇంకా లేదు`, or `NOT YET`

You can automate this with `scripts/demo-nudge-flow.sh`.

## Demo Scenario Script

Run an end-to-end demo flow (onboarding + HELP + sample question + DONE):

```bash
WEBHOOK_URL="https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/webhook" \\
FROM_NUMBER="919876543210" \\
APP_SECRET="YOUR_APP_SECRET" \\
./scripts/demo-scenario.sh
```

**Note**: If `APP_SECRET` is omitted, the script will skip signature headers. In dev, you can set `VERIFY_SIGNATURE=false` on the webhook Lambda.

## Nudge Test Checklist

See `docs/NUDGE-TEST-CHECKLIST.md` for the MVP test matrix and demo steps.

### Common Issues

**"No module named 'output'" error:**
- Ensure `src/processor/output.py` and `src/processor/analyzer.py` exist
- Rebuild: `sam build --template template-week2.yaml`

**"Invalid guardrail identifier" error:**
- Set GuardrailId to empty string in deployment
- Or update Lambda env var: `aws lambda update-function-configuration --function-name agrinexus-processor-dev --environment "Variables={...,GUARDRAIL_ID=''}"`

**Duplicate nudges:**
- Fixed in latest version - system checks for existing pending nudges

**Medical advice responses:**
- Fixed in latest version - system now refuses non-farming questions

## Documentation

- `CHANGELOG.md` - Engineering changelog with all features and fixes
- `ISSUES-LOG.md` - Debugging log with 20+ issues resolved
- `architecture.md` - System architecture design
- `design.md` - Technical design decisions
- `requirements.md` - EARS requirements

## Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Amazon Transcribe](https://docs.aws.amazon.com/transcribe/)
- [Amazon Polly](https://docs.aws.amazon.com/polly/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)

## Competition Submission

**AWS 10,000 AIdeas Competition**
- Category: Agriculture & Food Security
- Region: India (Maharashtra focus)
- Target Users: Smallholder cotton farmers
- Impact: Timely pest management → reduced crop loss → increased income

## License

MIT License - See LICENSE file for details

## Support

For technical issues:
1. Check CloudWatch Logs
2. Review ISSUES-LOG.md for similar problems
3. Verify IAM permissions and secrets configuration

For agricultural advice:
- Contact your local Krishi Vigyan Kendra (KVK)
- This system provides information, not professional agricultural consultation
