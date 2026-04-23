![AgriNexus AI - Bridging the Last Mile: From trapped research to accessible WhatsApp-based agricultural advice for smallholder farmers](https://github.com/user-attachments/assets/8aa328e4-327b-4d73-aaed-338800a656a1)

# AgriNexus AI – WhatsApp Agricultural Advisory

**Close the last mile:** AI-powered agronomic advice and weather-timed nudges for smallholder farmers—in their language, on WhatsApp. Built with **AWS Serverless** + **Amazon Bedrock** and a requirements-driven workflow (**Kiro** + **EARS**).

**In 30 seconds:** Send a voice note → get cited agronomic advice in your language. Send a crop photo → get pest/disease ID and recommendations. Get a nudge when weather is right for spraying—reply "हो गया" (done) to close the loop.

[![AWS Serverless](https://img.shields.io/badge/AWS-Serverless-232F3E?logo=amazonaws&logoColor=white)](https://aws.amazon.com/serverless/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-Claude%203%20Sonnet-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![WhatsApp Business Platform](https://img.shields.io/badge/WhatsApp-Business%20Platform-25D366?logo=whatsapp&logoColor=white)](https://www.whatsapp.com/business/platform/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![AWS SQS](https://img.shields.io/badge/AWS-SQS-232F3E?logo=amazonaws&logoColor=white)](https://aws.amazon.com/sqs/)
[![AWS DynamoDB](https://img.shields.io/badge/AWS-DynamoDB-4053D6?logo=amazondynamodb&logoColor=white)](https://aws.amazon.com/dynamodb/)
[![Kiro](https://img.shields.io/badge/Kiro-Requirements%20to%20Code-6E56CF)](https://kiro.ai/)
[![EARS](https://img.shields.io/badge/Requirements-EARS-0B7285)](https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax)

---

## Try It Yourself

Pick the web demo or WhatsApp experience.

| **🌐 Web demo** | **💬 WhatsApp** |
|--------------|--------------|
| [Try web demo](https://demo.agrinexus-ai.farm/web-demo/live-2026-04-13b.html) (no phone number) | [Open WhatsApp (wa.me)](https://wa.me/4915120105731) |
| **Includes:** Text Q&A (RAG), optional image | **Includes:** Onboarding + text (public); voice/photo/nudges (allowlisted) |
| **Best for:** Instant tryout in a browser | **Best for:** Full channel UX (buttons, voice, nudges) |
| **Privacy:** No login; anonymous `client_id` in browser storage for rate limits | **Privacy:** WhatsApp number required |
| **Limits:** ~5 questions/hour per IP + client; API Gateway + WAF caps | **Limits:** Rich features are allowlisted |

If your hosted site still has a **`chat.html`** redirect page, it should forward to the same **`wa.me`** number above.

**WhatsApp access:** Text is open; voice/photo/nudges are available via the [demo request template](https://github.com/prasadt1/agrinexus-ai/issues/new?template=demo-request.md).

**Data retention (summary):** Conversation rows written by the **processor** use a **90-day** TTL; short-lived **`MSG#*`** rows written by the **webhook** for the response detector use **7 days**; **WAMID** dedup keys use **24 hours**; **nudge** records use **180 days**. `demo_tier: public` limits **nudge follow-up scheduling**, not those TTLs. Details: [E2E-TEST-CHECKLIST.md](E2E-TEST-CHECKLIST.md) (section 6).

**Competition / article:** [AWS 10,000 AIdeas — AgriNexus finalist story on AWS Builder](https://builder.aws.com/content/3C8hBRTcsRuQrHzE3Pq243yhXTF/aideas-finalist-agrinexus-ai) (external).

---

## What it does (high level)

- **Multi-modal input**: text, voice notes (Transcribe), crop images (Vision)
- **Grounded answers**: Bedrock Knowledge Base RAG with citations (FAO + regional agronomy sources)
- **Behavioral nudges**: weather-timed spray reminders + DONE/NOT YET loop with follow-ups (full tier)
- **Multi-dialect**: Hindi, Marathi, Telugu, English
- **Safety**: farming-domain guardrails, banned pesticide blocking (optional), abuse/cost controls

## Architecture

- **Onboarding**: language → district (**Latur**, **Jalna**, **Nagpur**) → crop → nudge consent (`src/processor/handler.py`).
- **Serverless**: Lambda, DynamoDB, SQS, EventBridge Scheduler, Step Functions
- **AI**: Amazon Bedrock (Claude 3 Sonnet + Knowledge Base RAG), Transcribe, Polly, Claude Vision
- **Messaging**: WhatsApp Business Platform (Cloud API)
- **Storage**: DynamoDB single-table design, S3 for knowledge base sources + temp audio/images
- **Abuse / cost controls**:
  - WhatsApp **webhook**: Meta signature verification + per-user message rate limits (defaults in `template-week2.yaml`)
  - Public **web chat**: per-IP + per-client caps + API Gateway throttling + WAF on `/chat`
- **Cost**: modeled **~$53/month for 1,000 farmers** (pay-per-use). See [Cost breakdown](#cost-breakdown)

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
- **Smart Reminders**: T+24h and T+48h follow-ups if not completed (**skipped** when profile **`demo_tier`** is **`public`**)
- **Auto-Expiry**: T+72h auto-expiry if no response (EXPIRED status)
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

---

## Quick start (deploy your own)

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
# 1. Deploy infrastructure (recommended: samconfig-week2.toml)
sam build --template-file template-week2.yaml
sam deploy --config-file samconfig-week2.toml

# Manual alternative (match parameters in samconfig-week2.toml, including TableStreamArn):
# sam deploy --template-file .aws-sam/build/template.yaml \
#   --stack-name agrinexus-week2 \
#   --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
#   --resolve-s3 \
#   --parameter-overrides "Environment=dev TableName=agrinexus-data TableStreamArn=arn:aws:dynamodb:REGION:ACCOUNT:table/TABLE/stream/... KnowledgeBaseId=YOUR_KB_ID GuardrailId='' GuardrailVersion=1"

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

### Knowledge base setup

**Important**: The source PDF documents are **not included in this repository** due to copyright considerations. You need to obtain and upload them separately.

See [data/fao-pdfs/README.md](data/fao-pdfs/README.md) for:
- List of required documents with download links
- Copyright and licensing information
- Instructions for uploading to S3
- Alternative knowledge sources
- **URL manifests (cotton / wheat / soybean):** tracked CSVs under `data/fao-pdfs/` (`kb_url_manifest_all.csv`, `kb_url_manifest_download.csv`, `kb_url_manifest_manual.csv`) and helper script **`scripts/download_kb_from_manifest.py`** to fetch direct-PDF rows into `data/fao-pdfs/en/<crop>/` (run `--dry-run` first). Details: [data/fao-pdfs/README.md](data/fao-pdfs/README.md).

Quick setup:
```bash
# 1. Download PDFs from sources listed in data/fao-pdfs/README.md
#    Optional: batch-fetch direct PDFs from kb_url_manifest_download.csv
#    python3 scripts/download_kb_from_manifest.py --dry-run
#    python3 scripts/download_kb_from_manifest.py
# 2. Place them in data/fao-pdfs/en/
# 3. Upload to S3
aws s3 sync data/fao-pdfs/en/ s3://agrinexus-knowledge-base-dev/en/ \
    --exclude "*.DS_Store" --exclude "README.md"

# 4. Trigger Bedrock ingestion
aws bedrock-agent start-ingestion-job \
    --knowledge-base-id YOUR_KB_ID \
    --data-source-id YOUR_DATA_SOURCE_ID
```

### WhatsApp integration (webhook, secrets, templates)

- **Webhook URL**: After deploy, use the stack output `WebhookUrl` (e.g. `https://<api-id>.execute-api.us-east-1.amazonaws.com/dev/webhook`). In Meta Developer Portal → WhatsApp → Configuration, set this as **Callback URL** and subscribe to **messages**.
- **Verification (GET)**: Meta sends `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`. The webhook Lambda reads `agrinexus/whatsapp/verify-token` from Secrets Manager and returns `hub.challenge` if the token matches.
- **Signatures (POST)**: Incoming message payloads are verified with `X-Hub-Signature-256` (HMAC-SHA256) using `agrinexus/whatsapp/app-secret`. Reject if invalid.
- **Sending messages**: The **webhook** Lambda (via Common layer), **processor**, and **nudge** Lambdas use `agrinexus/whatsapp/access-token` and `agrinexus/whatsapp/phone-number-id` to call the WhatsApp Cloud API. For **inbound audio**, the webhook sends a short “received / preparing reply” text **immediately after deduplication** (before SQS → Voice Processor) so feedback is not delayed by queue or Transcribe. Text/interactive/template sends work as before.
- **Production number cutover** (new eSIM / WABA / templates): update the Meta Developer app, **phone number ID**, approved **message templates**, and **webhook** URL; refresh **`agrinexus/whatsapp/*`** secrets in **Secrets Manager** (never commit tokens).
- **Deploy / test**: **`sam build`** / **`sam deploy --config-file samconfig-week2.toml`**, then manual WhatsApp checks or [docs/E2E-TEST-GUIDE.md](docs/E2E-TEST-GUIDE.md) with **`scripts/demo.env`**.
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
│   ├── E2E-TEST-GUIDE.md           # End-to-end test guide (WhatsApp + integration)
│   ├── CODE-WALKTHROUGH.md         # Component walkthrough
│   └── operations/
│       └── RUNBOOK-ALERTS.md       # CloudWatch alarms, DLQ, web abuse envelope
├── E2E-TEST-CHECKLIST.md           # Pre-demo manual checklist + automated smoke pointer
├── .github/workflows/
│   ├── ci.yml                      # PR/push: fast pytest + sam validate
│   └── aws-smoke.yml               # Optional: workflow_dispatch golden KB tests (secrets)
├── scripts/
│   ├── README.md                   # Which scripts are shared vs local
│   ├── e2e-smoke.sh                # SAM validate + fast pytest + optional KB + web curl
│   ├── reset-profile.sh            # Non-interactive DynamoDB user reset (wraps delete-user-data)
│   ├── delete-user-data.sh         # Delete USER#* items for a phone (supports --yes)
│   ├── clear-nudges.sh             # Clear NUDGE# rows for a user
│   ├── reset-onboard-and-demo.sh   # Reset profile + optional webhook demo flow
│   ├── demo-nudge-loop.sh          # Scripted nudge / reminder demo (uses demo.env)
│   ├── test-complete-flow.sh       # Long synthetic webhook flow (voice/nudge/reminder)
│   ├── deploy-web-demo.sh          # SAM deploy + notes for static demo hosting
│   ├── push-to-public.sh           # Confirmation gate before git push public → open repo
│   ├── create-bedrock-guardrail.sh
│   └── … (other demo helpers; see scripts/README.md)
├── src/
│   ├── webhook/                    # WhatsApp webhook handler
│   ├── web-chat/                   # Public browser API (Bedrock RAG, rate limits)
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

### CI (GitHub Actions)

On every push/PR to `main`, **`.github/workflows/ci.yml`** runs fast unit tests (`tests/test_nudge_flow.py`, `tests/test_district_helplines.py`) and **`sam validate --lint`** on `template-week2.yaml`. Optional **`aws-smoke.yml`** (`workflow_dispatch`) can run golden KB tests when repository secrets are configured.

### One-command smoke (local or CI agent)

From repo root:

```bash
./scripts/e2e-smoke.sh
# Optional: export KNOWLEDGE_BASE_ID=... and WEB_CHAT_URL=https://...execute-api.../dev/chat
```

### Text RAG
```bash
# Integration tests call Bedrock; set a real KB ID or tests skip:
export KNOWLEDGE_BASE_ID=YOUR_KB_ID
pytest tests/test_golden_questions.py -v
```
Without **`KNOWLEDGE_BASE_ID`**, parametrized golden tests **skip** (see `tests/test_golden_questions.py`).

### Voice Input
```bash
# Test with your own voice recording (language codes: hi-IN, mr-IN, te-IN, en-IN)
python tests/test_voice_simple.py path/to/audio.mp3 hi-IN
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

See [docs/E2E-TEST-GUIDE.md](docs/E2E-TEST-GUIDE.md) for testing onboarding, Q&A, voice, vision, and nudges. For a **pre-demo pass/fail list**, use **[E2E-TEST-CHECKLIST.md](E2E-TEST-CHECKLIST.md)**.

**Webhook scripts:** create **`scripts/demo.env`** (not committed) with at least **`WEBHOOK_URL`**, **`APP_SECRET`** (if signatures are on), and **`PHONE_NUMBER`**. Scripts such as **`reset-onboard-and-demo.sh`**, **`test-complete-flow.sh`**, and **`demo-nudge-loop.sh`** source it when present.

### Reset profile / re-onboarding

- **DynamoDB only (no Meta HTTP):** `./scripts/reset-profile.sh 4917647009148` (digits only; or set **`PHONE_NUMBER`** in `demo.env` and run with no args). Wraps **`delete-user-data.sh`** with confirmation skipped.
- **Full scripted webhook flow:** `./scripts/reset-onboard-and-demo.sh --phone <digits>` (requires `WEBHOOK_URL`; see `usage()` in that script).

Then send a new language choice in WhatsApp to restart onboarding.

## Architecture Details

### Lambda Functions
1. **WebhookHandler**: Validates signature, **per-user rate limit** (before enqueue), deduplicates, stores short-lived **`MSG#*`** rows for the response detector, routes **text/image** to the message queue and **audio** to the voice queue; for **audio**, sends localized **voice-received ACK** via WhatsApp (before enqueue) using the Common layer + secrets
2. **WebChatHandler**: Public **POST /chat** API for browser demo—Bedrock KB RAG, optional image analysis, **DynamoDB rate limits**, no WhatsApp
3. **MessageProcessor**: Handles text/image messages, RAG queries, Polly voice output; **does not** send a duplicate “preparing answer” ack for transcribed voice (`_source: voice`)
4. **VoiceProcessor**: Downloads media, **Transcribe** batch job, queues transcribed text to the message queue
5. **NudgeSender**: Sends behavioral nudges, schedules reminders
6. **ReminderSender**: Sends T+24h and T+48h reminders
7. **ResponseDetector**: Detects DONE/NOT YET responses via DynamoDB Streams
8. **WeatherPoller**: Checks weather, triggers nudge workflow
9. **DLQHandler**: Handles failed messages with dialect-aware errors

### Data Flow

**Text Query (WhatsApp):**
```
WhatsApp → Webhook → SQS → Processor → Bedrock RAG → WhatsApp
```

**Text query (web demo):**
```
Browser → API Gateway (+ WAF) → WebChatHandler → Bedrock RAG → JSON response
```

**Voice Query:**
```
WhatsApp → Webhook → (optional ACK text to user) → VoiceQueue → VoiceProcessor → Transcribe → Message queue → Processor → Bedrock RAG → Polly → WhatsApp
```
(ACK is sent from the **webhook** right after dedup + profile dialect lookup, not from VoiceProcessor.)

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

**All pay-per-use, no fixed costs** (migrated from OpenSearch Serverless to S3 vectors on April 4, 2026)

### Variable Costs (~3K queries + 500 voice min/month for 1K farmers)
| Service | Usage (1K users) | Monthly Cost |
|---------|------------------|--------------|
| Bedrock Claude 3 Sonnet (RAG) | 3K queries (3M input + 1.5M output tokens) | ~$32 |
| Bedrock Claude Vision | 100 images | ~$5 |
| Transcribe | 500 voice minutes | ~$12 |
| Polly (neural TTS) | 200 min voice output | ~$2 |
| S3 Vectors (Knowledge Base) | Storage + 3K queries | ~$1.30 |
| DynamoDB (on-demand) | 1M reads, 500K writes | ~$0.90 |
| EventBridge Scheduler | 1K schedules | ~$0.01 |
| Lambda, API Gateway, SQS, S3, Step Functions | | $0 (free tier) |
| **Total** | | **~$53/month** |

### Cost per Farmer (from the same models as the table above)
- **1,000 farmers**: ~$53/month total → ~**$0.053**/farmer/month → ~**$0.64**/farmer/year  
- **10,000 farmers** (projected): ~**$450**/month total → ~**$0.045**/farmer/month → ~**$0.54**/farmer/year  

The **$0.54** figure is **not** a separate measurement—it is **($450 × 12) ÷ 10,000** from the §8.2 projection in `architecture.md`. **Minimal economies of scale** (~16% lower per farmer vs 1K) because **Bedrock / Transcribe / Polly** scale roughly with usage; **S3 Vectors** stays a small slice.

**How to read this:** **~$53/mo @ 1K** and **~$450/mo @ 10K** are **modeled** from AWS-style usage assumptions (see architecture §8), **not** audited Cost Explorer totals. **Validate** with your account before publishing hard commitments.

**100x cheaper than commercial agricultural advisory services** ($5-10/farmer/month)

### Historical Context
- **Before April 4, 2026**: OpenSearch Serverless **~$174/month fixed** (plus variable services → **~$214/month** all-in)
- **After April 4, 2026**: S3 Vectors + pay-per-use stack → **~$53/month** modeled @ 1K farmers (**~75%** reduction vs the old **~$214** all-in figure)

## Known Limitations

1. **Voice round-trip latency**: Typically **~30–40s** end-to-end (batch **Transcribe** ~15–30s + **Bedrock RAG** ~5–15s + **Polly** + WhatsApp media). The **voice-received** text line is sent from the **webhook** as soon as possible after dedup (often **~1–3s**; **cold start** on first request can add more).
2. **Telugu Voice Output**: No native Telugu voice in Polly. Text-only responses for Telugu users.
3. **WhatsApp Test Numbers**: Don't support media (voice/images). Requires real WhatsApp Business number for end-to-end testing.
4. **Weather Data**: Real OpenWeatherMap API integrated. Set MOCK_WEATHER=true for demo reliability.

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

Use the [CloudWatch console](https://console.aws.amazon.com/cloudwatch/) for Lambda log groups (e.g. `/aws/lambda/agrinexus-webhook-dev`, `/aws/lambda/agrinexus-web-chat-dev`).

**Alarms:** The SAM stack publishes **SNS** topic **`agrinexus-alerts-<env>`** (see stack output **`AlertTopicArn`**) for nudge workflow failures, high daily cost, **Lambda errors** (webhook, processor, web-chat, voice), **SQS main-queue backlog age**, and **DLQ depth**. Subscribe an email/SMS to that topic in the AWS console. Full table: **[docs/operations/RUNBOOK-ALERTS.md](docs/operations/RUNBOOK-ALERTS.md)**.

**Billing:** enable [Cost Explorer](https://console.aws.amazon.com/cost-management/home#/cost-explorer) once per account, then filter by service (Bedrock, Transcribe, etc.).

**Custom metrics** (application code, if enabled in your deployment): `AgriNexus/NudgesSent`, `AgriNexus/NudgesCompleted`. You can build a CloudWatch dashboard (e.g. `AgriNexus-Operations-dev`) on top of these and standard Lambda/SQS metrics.

**Traffic visibility vs. browser analytics:** **Web demo** and **WhatsApp** traffic are understood through **AWS**—CloudWatch metrics and logs (API Gateway and `agrinexus-web-chat` for the public `/chat` path; webhook, processor, queues, and DLQ for WhatsApp), optional **WAF** metrics and sampled requests on `/chat`, and the nudge custom metrics above. The **[`dashboards/cloudwatch-dashboard.json`](dashboards/cloudwatch-dashboard.json)** template includes **web demo** API and Lambda widgets plus an on-dashboard pointer to **CloudWatch RUM** for optional **page-view** telemetry. **Optional RUM** (off by default) is configured in **`docs/web-demo/assets/rum-config.js`**; there is no third-party page analytics (e.g. Google Analytics). Details: **[docs/web-demo/README.md#traffic-visibility-vs-browser-analytics](docs/web-demo/README.md#traffic-visibility-vs-browser-analytics)**.

## Real Weather API (Optional)

Production uses **OpenWeatherMap** when `MOCK_WEATHER` is false and the API key is available from **Secrets Manager** (`WEATHER_API_KEY_SECRET` on the Weather Lambda, e.g. `agrinexus/weather/api-key`). Store the key in Secrets Manager—do not put it in `samconfig` or git. Set `MOCK_WEATHER=true` on the Weather poller only for deterministic demo weather. See [WEATHER-API-SETUP.md](WEATHER-API-SETUP.md).

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

See [requirements.md](requirements.md) for the complete EARS specification (100+ requirements covering all features).

## Development Workflow: Kiro AI

This project was developed using **Kiro AI**, which enabled requirements-driven development from EARS specs through to deployed Lambda functions. Kiro's steering documents (`.kiro/specs/`) defined feature specs, implementation plans, and acceptance criteria—keeping requirements, code, and tests traceable throughout the 4-week build.

**Key metrics:**
- 100+ EARS requirements in [requirements.md](requirements.md)
- ~3,000 lines of Python across 8 Lambda functions
- Full test coverage: voice, vision, RAG, nudges

## Documentation

- [architecture.md](architecture.md) — full system design
- [architecture/diagrams.md](architecture/diagrams.md) — Mermaid flow diagrams
- [E2E-TEST-CHECKLIST.md](E2E-TEST-CHECKLIST.md) — pre-demo checklist (manual + automated smoke pointer)
- [docs/E2E-TEST-GUIDE.md](docs/E2E-TEST-GUIDE.md) — end-to-end test walkthrough
- [docs/CODE-WALKTHROUGH.md](docs/CODE-WALKTHROUGH.md) — component-by-component guide
- [data/fao-pdfs/README.md](data/fao-pdfs/README.md) — knowledge-base PDF sources, S3 sync, and **URL manifests / batch download** (`kb_url_manifest_*.csv`, `scripts/download_kb_from_manifest.py`)
- [requirements.md](requirements.md) — EARS requirements specification
- [ISSUES-LOG.md](ISSUES-LOG.md) — troubleshooting history (resolved issues)
- [docs/notes/INDEX.md](docs/notes/INDEX.md) — working notes and one-off reports (optional)
- [docs/demo/TRIGGER-COMMANDS.md](docs/demo/TRIGGER-COMMANDS.md) — scripted demo triggers for nudge/reminder flows (video / manual testing)

### Maintainers (internal / non-public)

Some documents are intentionally **not** part of the public “judge quickstart” narrative (operations runbooks, private/public sync workflow, etc.). If you’re maintaining a deployed stack, you may also consult:

- `docs/operations/RUNBOOK-ALERTS.md` — alarms, DLQ, abuse envelope, rate limits
- `docs/PRIVATE-PUBLIC-SYNC.md` — internal repo sync discipline

## Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Amazon Transcribe](https://docs.aws.amazon.com/transcribe/)
- [Amazon Polly](https://docs.aws.amazon.com/polly/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)

## License

Copyright (C) 2026 [Prasad Tilloo](https://prasadtilloo.com). All rights reserved.

This source code is made publicly available for **portfolio, evaluation, and competition review purposes only**.

**Permitted uses:**
- Viewing and reviewing the source code
- Running the software locally for personal, non-commercial evaluation
- Forking for the purpose of submitting issues or pull requests

**Not permitted** without explicit written permission:
- Commercial use of any kind
- Redistribution of the source code or compiled binaries
- Building derivative products or services based on this codebase
- White-labelling or rebranding this software
- Deploying this software to serve end users in any commercial context

The agricultural knowledge corpus, RAG pipeline configuration, prompt templates, and nudge logic are proprietary components of AgriNexus AI.

**For licensing and partnership enquiries** → prasad@prasadtilloo.com

See the [LICENSE](LICENSE) file for full details.

## Security

- **Do not commit** API keys, tokens, app secrets, or real phone numbers. `scripts/demo.env` and `.aws-sam/` should stay gitignored.
- **Webhook:** Meta **`X-Hub-Signature-256`** verification; **per-user message rate limit** before enqueueing work (see `template-week2.yaml` **`RATE_LIMIT_*`**). **Web chat:** separate rate limits + API Gateway + WAF (see template and runbook).
- Set **KnowledgeBaseId** (and related stack params) in **`samconfig-week2.toml`** or **`--parameter-overrides`** when deploying. Processor Lambdas receive **`KNOWLEDGE_BASE_ID`** from the template.
- For **vision / voice** integration tests, set **`TEMP_AUDIO_BUCKET`** (and any other required env vars) as documented in the test files.

## Support

For technical issues:
1. Check CloudWatch Logs
2. Review [ISSUES-LOG.md](ISSUES-LOG.md) for similar problems
3. Verify IAM permissions and secrets configuration

For agricultural advice:
- Contact your local Krishi Vigyan Kendra (KVK)
- This system provides information, not professional agricultural consultation
