<img width="2816" height="1536" alt="Gemini_Generated_Image_lodjzglodjzglodj" src="https://github.com/user-attachments/assets/6987a1de-2f7c-4d1e-8d96-d6c9c7619f94" />

# AgriNexus AI – WhatsApp Agricultural Advisory

**Close the last mile:** AI-powered agronomic advice and weather-timed nudges for smallholder farmers—in their language, on WhatsApp. Built with **Kiro**, **EARS**, and **Amazon Bedrock**.

**In 30 seconds:** Send a voice note → get cited agronomic advice in your language. Send a crop photo → get pest/disease ID and recommendations. Get a nudge when weather is right for spraying—reply "हो गया" (done) to close the loop.

---

## Architecture

- **Serverless**: Lambda, DynamoDB, EventBridge Scheduler, Step Functions
- **AI**: Amazon Bedrock (Claude 3 Sonnet + RAG), Transcribe, Polly, Claude Vision
- **Messaging**: WhatsApp Business API
- **Storage**: DynamoDB single-table design, S3 for knowledge base + temp audio
- **Cost**: ~$214/month for 1,000 farmers (~$174 fixed OpenSearch + ~$40 variable). See [Cost breakdown](#cost-breakdown)

**Diagrams:** See [architecture/diagrams.md](architecture/diagrams.md) for Mermaid diagrams (high-level, webhook, text/voice/image flows, nudge flow). Full design: [architecture.md](architecture.md).

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
# Or use: sam deploy --config-env default (after setting KnowledgeBaseId in samconfig-week2.toml)

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

### WhatsApp integration (webhook, secrets, templates)

- **Webhook URL**: After deploy, use the stack output `WebhookUrl` (e.g. `https://<api-id>.execute-api.us-east-1.amazonaws.com/dev/webhook`). In Meta Developer Portal → WhatsApp → Configuration, set this as **Callback URL** and subscribe to **messages**.
- **Verification (GET)**: Meta sends `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`. The webhook Lambda reads `agrinexus/whatsapp/verify-token` from Secrets Manager and returns `hub.challenge` if the token matches.
- **Signatures (POST)**: Incoming message payloads are verified with `X-Hub-Signature-256` (HMAC-SHA256) using `agrinexus/whatsapp/app-secret`. Reject if invalid.
- **Sending messages**: The processor and nudge Lambdas use `agrinexus/whatsapp/access-token` and `agrinexus/whatsapp/phone-number-id` to call the WhatsApp Cloud API (text, interactive buttons, or template messages where used).
- **Message types**: Inbound text, image, and audio are supported. Outbound: text, optional interactive buttons (e.g. language/location during onboarding), and template messages for nudges (see [architecture/diagrams.md](architecture/diagrams.md)).

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
├── architecture.md                  # Full architecture document
├── architecture/                    # Diagrams and quick reference
│   ├── README.md
│   └── diagrams.md                 # Mermaid: flows, webhook, nudge
├── docs/
│   ├── E2E-TEST-GUIDE.md           # End-to-end test guide
│   ├── CODE-WALKTHROUGH.md         # Component walkthrough
│   ├── NUDGE-TEST-CHECKLIST.md
│   └── NUDGE-DEMO-RUNBOOK.md
├── scripts/
│   ├── deploy-week2.sh            # Deployment script
│   ├── e2e-test.sh                 # E2E automated test
│   ├── reset-profile.sh            # Reset user for re-onboarding
│   ├── demo-reset.sh               # Pre-demo cleanup (DynamoDB + SQS)
│   ├── demo.env.example            # Example env (copy to demo.env)
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

### End-to-End (All Features)

See `docs/E2E-TEST-GUIDE.md` for testing onboarding, Q&A, voice, vision, and nudges.

**One-time setup:** Copy `scripts/demo.env.example` to `scripts/demo.env` and set `WEBHOOK_URL`, `APP_SECRET`, and `PHONE_NUMBER`. All test scripts auto-load it:

```bash
cp scripts/demo.env.example scripts/demo.env
# Edit scripts/demo.env, then:
./scripts/e2e-test.sh --phone +919876543210
```

### Reset Profile (Re-Onboarding)

```bash
./scripts/reset-profile.sh +919876543210
```

Then send a new language keyword (`हिंदी` / `मराठी` / `తెలుగు` / `English`) in WhatsApp to restart onboarding.

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

### Fixed Infrastructure (always-on)
| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| OpenSearch Serverless | ~$174 | Minimum 0.5 OCU × 2 at $0.24/OCU-hr; always-on |

### Variable Costs (~3K queries + 500 voice min/month for 1K farmers)
| Service | Usage (1K users) | Monthly Cost |
|---------|------------------|--------------|
| Bedrock (Claude 3 Sonnet RAG + Vision) | 3K queries, 100 images | ~$25 |
| Transcribe | 500 voice minutes | ~$12 |
| Polly (neural TTS) | Voice responses | ~$1 |
| DynamoDB (on-demand) | 1M reads, 500K writes | ~$1 |
| EventBridge Scheduler | 1K schedules | ~$1 |
| Lambda, API Gateway, SQS, S3, Step Functions | | $0 (free tier) |
| **Variable total** | | **~$40/month** |

### Total: ~$214/month for 1,000 farmers

OpenSearch Serverless is the dominant cost—it's always-on infrastructure, not pay-per-query. This fixed cost amortizes sharply with scale: at 10,000 farmers, total is ~$574/month (~$0.70/farmer/year).

### Cost Optimization: Cheaper Vector Store Alternatives

OpenSearch Serverless has a ~$174/month minimum. Here are AWS-native alternatives that work with Bedrock Knowledge Bases:

| Alternative | Monthly Cost | Latency | Best For |
|-------------|--------------|---------|----------|
| **Amazon S3 Vectors** (new, Dec 2025) | Pay-per-query (~$5-10) | 100-800ms | Cost-sensitive, low-medium QPS |
| **Aurora PostgreSQL + pgvector** | ~$30-50 (smallest instance) | <100ms | Need SQL + vectors |
| **OpenSearch Managed Cluster** | ~$50-100 | <50ms | High throughput, need full-text search |
| **Pinecone Free Tier** | $0 (up to 100K vectors) | <100ms | Small datasets, external service OK |

**Recommended for AgriNexus**: Switch to **Amazon S3 Vectors** for up to 90% savings. S3 Vectors is fully AWS-native, requires no infrastructure management, and works directly with Bedrock Knowledge Bases. Slightly higher latency (100-800ms vs <50ms) is acceptable for a chatbot use case.

**With S3 Vectors**: Total cost drops to **~$45-50/month** for 1,000 farmers.

See: [AWS S3 Vectors announcement](https://aws.amazon.com/about-aws/whats-new/2024/12/amazon-s3-vectors-preview/) | [Bedrock KB vector store options](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html)

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
# Test voice processor
aws lambda invoke --function-name agrinexus-voice-dev --payload '{}' /tmp/response.json

# Test weather poller
aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/response.json
```

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

## Requirements Methodology: EARS

This project uses **EARS (Easy Approach to Requirements Syntax)** for all functional requirements. EARS provides a structured, unambiguous way to write requirements using five patterns:

1. **Ubiquitous**: The [System] shall [Response]
2. **Event-driven**: When [Event], the [System] shall [Response]
3. **State-driven**: While [State], the [System] shall [Response]
4. **Optional**: Where [Feature], the [System] shall [Response]
5. **Unwanted**: If [Condition], then the [System] shall [Response]

**Example mapping:**

```
Requirement (EARS):
REQ-NUDGE-008: When a farmer responds with DONE keywords
(Hindi: "ho gaya"), the system shall mark the task as
completed in DynamoDB and delete pending reminders.

Implementation (src/nudge/detector.py):
if is_done_response(message_text):
    update_nudge_status(phone_number, 'DONE')
    delete_scheduled_reminders()

Test (tests/test_nudge_flow.py):
def test_done_response_marks_complete():
    send_message("हो गया")
    assert get_nudge_status() == 'DONE'
    assert get_scheduled_reminders() == []
```

See `requirements.md` for the complete EARS specification (100+ requirements covering all features).

## Development Workflow: Kiro AI

This project was developed using **Kiro AI**, which enabled requirements-driven development from EARS specs through to deployed Lambda functions. Kiro's steering documents (`.kiro/specs/`) defined feature specs, implementation plans, and acceptance criteria—keeping requirements, code, and tests traceable throughout the 4-week build.

**Key metrics:**
- 100+ EARS requirements in `requirements.md`
- ~3,000 lines of Python across 8 Lambda functions
- Full test coverage: voice, vision, RAG, nudges

## Documentation

- `architecture.md` — full system design
- `architecture/diagrams.md` — Mermaid flow diagrams
- `docs/E2E-TEST-GUIDE.md` — end-to-end test walkthrough
- `docs/CODE-WALKTHROUGH.md` — component-by-component guide
- `requirements.md` — EARS requirements specification

## Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Amazon Transcribe](https://docs.aws.amazon.com/transcribe/)
- [Amazon Polly](https://docs.aws.amazon.com/polly/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)

## License

MIT License - See LICENSE file for details

## Security

- **Do not commit** API keys, tokens, app secrets, or real phone numbers. `scripts/demo.env` and `.aws-sam/` are gitignored.
- Set **KnowledgeBaseId** in `samconfig-week2.toml` or via `--parameter-overrides` when deploying.
- Set **TEMP_AUDIO_BUCKET** and **KNOWLEDGE_BASE_ID** (and optionally **VOICE_QUEUE_URL**) for integration tests.

## Support

For technical issues:
1. Check CloudWatch Logs
2. Review `ISSUES-LOG.md` for similar problems
3. Verify IAM permissions and secrets configuration

For agricultural advice:
- Contact your local Krishi Vigyan Kendra (KVK)
- This system provides information, not professional agricultural consultation
