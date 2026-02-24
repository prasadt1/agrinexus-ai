# AgriNexus AI — Architecture Deep Dive

## 1. System Overview

AgriNexus AI is a **100% serverless** WhatsApp chatbot that provides agricultural advisory services to smallholder cotton farmers in India. It supports **4 languages** (Hindi, Marathi, Telugu, English) and **3 input modes** (text, voice, images).

The system has two major subsystems:

| Subsystem | Purpose | Trigger |
|-----------|---------|---------|
| **Reactive Q&A** | Answer farmer questions via RAG, voice, and vision | Farmer sends a WhatsApp message |
| **Proactive Nudge Engine** | Weather-based behavioral interventions with closed-loop accountability | EventBridge Scheduler (every 6h) |

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WHATSAPP CLOUD API                            │
│                         (Meta Business Platform)                           │
└──────────────┬──────────────────────────────────────────┬──────────────────┘
               │ Inbound messages                         ▲ Outbound messages
               ▼                                          │
┌──────────────────────────┐                 ┌────────────┴───────────────┐
│   API Gateway (REST)     │                 │  WhatsApp Business API     │
│   GET  /webhook (verify) │                 │  graph.facebook.com/v22.0  │
│   POST /webhook (msgs)   │                 │  (text, audio, buttons,    │
└──────────┬───────────────┘                 │   templates)               │
           │                                 └────────────▲──────────────┘
           ▼                                              │
┌──────────────────────────┐                              │
│  WebhookHandler Lambda   │──── Signature validation ────│
│  (src/webhook/handler.py)│──── Idempotency (DynamoDB)   │
│  (src/webhook/handler.py)│──── Route by message type    │
└────┬──────────┬──────────┘                              │
     │          │                                         │
     │ text/    │ audio                                   │
     │ image    │                                         │
     ▼          ▼                                         │
┌─────────┐ ┌──────────┐                                  │
│ Message │ │  Voice   │                                  │
│ Queue   │ │  Queue   │                                  │
│ (FIFO)  │ │  (FIFO)  │                                  │
└────┬────┘ └────┬─────┘                                  │
     │           │                                        │
     ▼           ▼                                        │
┌─────────────┐ ┌──────────────┐                          │
│  Message    │ │  Voice       │                          │
│  Processor  │ │  Processor   │──── Transcribe ──┐       │
│  Lambda     │ │  Lambda      │                  │       │
│             │ └──────────────┘                  │       │
│  ┌────────┐ │                    ┌──────────────┘       │
│  │Onboard │ │◄───────────────────┘ (re-queued as text)  │
│  │  FSM   │ │                                           │
│  ├────────┤ │                                           │
│  │Bedrock │ │─── RAG (Claude 3 Sonnet) ─────────────────┤
│  │  RAG   │ │                                           │
│  ├────────┤ │                                           │
│  │Claude  │ │─── Vision (Claude 3 Sonnet) ──────────────┤
│  │Vision  │ │                                           │
│  ├────────┤ │                                           │
│  │ Polly  │ │─── TTS (voice responses) ─────────────────┤
│  │  TTS   │ │                                           │
│  └────────┘ │                                           │
└─────────────┘                                           │
                                                          │
┌─────────────────── NUDGE ENGINE ────────────────────────┤
│                                                         │
│  ┌───────────────┐    ┌─────────────┐                   │
│  │ EventBridge   │───▶│  Weather    │                   │
│  │ (every 6h)    │    │  Poller     │                   │
│  └───────────────┘    │  Lambda     │                   │
│                       └──────┬──────┘                   │
│                  favorable?  │                           │
│                       ┌──────▼──────┐                   │
│                       │Step Functions│                   │
│                       │  Workflow    │                   │
│                       └──────┬──────┘                   │
│                              │                          │
│                       ┌──────▼──────┐                   │
│                       │  Nudge      │───────────────────┤
│                       │  Sender     │                   │
│                       │  Lambda     │                   │
│                       └──────┬──────┘                   │
│                              │ schedules                │
│                       ┌──────▼──────┐                   │
│                       │ EventBridge │                   │
│                       │ Scheduler   │                   │
│                       │ T+24h/T+48h│                   │
│                       └──────┬──────┘                   │
│                              │                          │
│                       ┌──────▼──────┐                   │
│                       │  Reminder   │───────────────────┘
│                       │  Sender     │
│                       │  Lambda     │
│                       └─────────────┘
│
│  ┌─ Closed-Loop Detection ──────────────────────────────┐
│  │                                                      │
│  │  DynamoDB Stream ──▶ Response Detector Lambda        │
│  │  (MSG# inserts)      - Scans for DONE/NOT YET        │
│  │                      - Marks nudge DONE               │
│  │                      - Deletes reminder schedules     │
│  │                      - Emits CloudWatch metrics       │
│  └──────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow Diagrams

### 3.1 Text Query Flow

```
Farmer sends text ──▶ WhatsApp Cloud API
                         │
                         ▼
                    API Gateway POST /webhook
                         │
                         ▼
                  WebhookHandler Lambda
                    │  1. Verify X-Hub-Signature-256
                    │  2. Deduplicate via DynamoDB (WAMID# conditional put)
                    │  3. Store MSG# record (for Response Detector stream)
                    │  4. Check DONE/NOT YET keywords → skip SQS if match
                    │  5. Send to MessageQueue (FIFO, grouped by phone)
                    ▼
              SQS MessageQueue.fifo
                    │
                    ▼
             MessageProcessor Lambda
                    │
                    ├── New user? ──▶ Onboarding FSM (5-step)
                    │                 welcome → language → location → crop → consent
                    │                 Uses interactive reply buttons
                    │
                    ├── HELP command? ──▶ Return help message in user's dialect
                    │
                    ├── Text query ──▶ Bedrock RAG (Knowledge Base)
                    │                  │  Model: Claude 3 Sonnet
                    │                  │  KB ID: H81XLD3YWY
                    │                  │  Sources: FAO manuals + ICAR research
                    │                  │  Language instruction injected into prompt
                    │                  │  Optional: Guardrails (banned pesticides, medical)
                    │                  ▼
                    │                  Response with source citations
                    │
                    └── Voice-originated? ──▶ Also generate Polly TTS audio
                                              Upload MP3 to S3 (presigned URL)
                                              Send audio message via WhatsApp
```

### 3.2 Voice Query Flow

```
Farmer sends voice note ──▶ WhatsApp Cloud API
                               │
                               ▼
                         WebhookHandler Lambda
                           │  type=audio → route to VoiceQueue
                           ▼
                      SQS VoiceQueue.fifo (batch=1)
                           │
                           ▼
                    VoiceProcessor Lambda (90s timeout)
                      │
                      │  1. Get WhatsApp media URL (graph.facebook.com)
                      │  2. Download audio bytes
                      │  3. Upload .ogg to S3 temp bucket
                      │  4. Start Amazon Transcribe batch job
                      │     Language: hi-IN / mr-IN / te-IN / en-IN
                      │  5. Poll every 1s for up to 60s
                      │  6. Extract transcript + confidence
                      │  7. Cleanup: delete S3 object + Transcribe job
                      │
                      ├── confidence ≥ 0.5 ──▶ Re-queue as text message to MessageQueue
                      │                        (with _source='voice' marker)
                      │                        → MessageProcessor handles RAG + voice response
                      │
                      └── confidence < 0.5 ──▶ Send error in user's dialect
                           or timeout/failure    "Your voice wasn't clear..."
```

### 3.3 Image Analysis Flow

```
Farmer sends crop photo ──▶ WhatsApp Cloud API
                               │
                               ▼
                         WebhookHandler Lambda
                           │  type=image → send to MessageQueue
                           ▼
                      SQS MessageQueue.fifo
                           │
                           ▼
                    MessageProcessor Lambda
                      │  message_type == 'image'
                      │
                      ▼
                   Vision Analyzer (src/processor/analyzer.py)
                      │
                      │  1. Download image from WhatsApp (media API)
                      │  2. Save to S3 for record-keeping
                      │  3. Base64-encode image
                      │  4. Call Claude 3 Sonnet Vision (bedrock-runtime:InvokeModel)
                      │     Prompt: "Analyze this {crop} plant image..."
                      │     Response language: user's dialect
                      │  5. Parse diagnosis, severity, confidence
                      │
                      ▼
                   Send analysis back via WhatsApp (text only, no voice)
                   Includes: diagnosis, severity, recommendations, prevention
```

### 3.4 Behavioral Nudge Flow (Proactive)

```
EventBridge Schedule (every 6 hours)
         │
         ▼
   WeatherPoller Lambda
     │  1. Scan DynamoDB for unique user locations
     │  2. Check weather per location:
     │     - Mock mode: Aurangabad always favorable (wind=8.5, rain=0)
     │     - Real mode: OpenWeatherMap API
     │  3. Favorable = wind < 10 km/h AND rain == 0
     │
     │  For each favorable location:
     ▼
   Step Functions (NudgeStateMachine)
     │  Single state: invoke NudgeSender Lambda
     ▼
   NudgeSender Lambda
     │  1. Query GSI1 for farmers in location (LOCATION#{district})
     │  2. For each farmer with consent:
     │     a. Check has_pending_nudge() → skip if already has one today
     │     b. Generate message in farmer's dialect:
     │        "आज स्प्रे करने के लिए अच्छा मौसम है। हवा 8.5 km/h..."
     │     c. Create NUDGE# record in DynamoDB (status=SENT)
     │     d. Send WhatsApp template or text message
     │     e. Emit CloudWatch metric: NudgesSent
     │     f. Schedule T+24h reminder (EventBridge Scheduler)
     │     g. Schedule T+48h reminder (EventBridge Scheduler)
     ▼
   EventBridge Scheduler (at T+24h and T+48h)
     │
     ▼
   ReminderSender Lambda
     │  1. Check nudge status in DynamoDB
     │  2. If status != DONE:
     │     - Send reminder in farmer's dialect
     │     - Update status to REMINDED
     │  3. If status == DONE:
     │     - Skip (farmer already completed)

   ──── Closed-Loop Detection (parallel) ────

   DynamoDB Stream (MSG# INSERT events)
     │
     ▼
   ResponseDetector Lambda
     │  1. Extract message text from stream record
     │  2. Check NOT YET keywords first (more specific):
     │     hi: "अभी नहीं", mr: "नाही झाला", te: "ఇంకా లేదు"
     │     → Send acknowledgment, reminders continue
     │  3. Check DONE keywords:
     │     hi: "हो गया", mr: "झाला", te: "అయ్యింది"
     │     → Mark nudge DONE in DynamoDB
     │     → Delete scheduled reminders from EventBridge
     │     → Send confirmation: "बहुत अच्छा! 🎉"
     │     → Emit CloudWatch metric: NudgesCompleted
```

---

## 4. DynamoDB Single-Table Design

```
┌──────────────────┬────────────────────────────┬────────────────────────────┐
│       PK         │            SK              │       Purpose              │
├──────────────────┼────────────────────────────┼────────────────────────────┤
│ USER#+91xxx      │ PROFILE                    │ User profile + onboarding  │
│ USER#+91xxx      │ MSG#2026-02-24T10:00:00    │ Message history (TTL: 7d)  │
│ USER#+91xxx      │ NUDGE#2026-02-24T06:00#spray│ Nudge record              │
│ WAMID#wamid_xxx  │ DEDUP                      │ Idempotency (TTL: 24h)    │
└──────────────────┴────────────────────────────┴────────────────────────────┘

GSIs:
┌─────────────────┬──────────────────┬──────────────────────────────────────┐
│     Index       │    Key Schema    │              Usage                   │
├─────────────────┼──────────────────┼──────────────────────────────────────┤
│ GSI1            │ GSI1PK / GSI1SK  │ LOCATION#{district} / CROP#{crop}    │
│                 │                  │ → Query farmers by location for nudge│
├─────────────────┼──────────────────┼──────────────────────────────────────┤
│ GSI2            │ GSI2PK / GSI2SK  │ NUDGE / {timestamp}                  │
│                 │                  │ → Query all nudges by time           │
└─────────────────┴──────────────────┴──────────────────────────────────────┘

Stream: NEW_AND_OLD_IMAGES → ResponseDetector Lambda
TTL: Enabled on 'ttl' attribute (auto-cleanup of messages and dedup records)
```

### User Profile Record

```json
{
  "PK": "USER#+919876543210",
  "SK": "PROFILE",
  "phone_number": "+919876543210",
  "dialect": "hi",
  "location": "Aurangabad",
  "location_coords": { "lat": 19.8762, "lon": 75.3433 },
  "crop": "Cotton",
  "consent": true,
  "onboarding_complete": true,
  "created_at": "2026-02-24T10:00:00",
  "GSI1PK": "LOCATION#Aurangabad",
  "GSI1SK": "CROP#Cotton"
}
```

### Nudge Record

```json
{
  "PK": "USER#+919876543210",
  "SK": "NUDGE#2026-02-24T06:00:00#spray",
  "GSI2PK": "NUDGE",
  "GSI2SK": "2026-02-24T06:00:00",
  "status": "SENT",
  "activity": "spray",
  "weather": { "wind_speed": 8.5, "rain": 0 },
  "message": "आज स्प्रे करने के लिए अच्छा मौसम है...",
  "ttl": 1741344000
}
```

Status lifecycle: `SENT` → `REMINDED` (after T+24h/T+48h) → `DONE` (farmer confirms)

---

## 5. Key Business Logic

### 5.1 Onboarding State Machine

The `MessageProcessor` implements a 5-step onboarding flow using WhatsApp interactive reply buttons:

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐    ┌─────────┐
│ Welcome │───▶│ Language │───▶│ Location │───▶│  Crop  │───▶│ Consent │──▶ Complete
│ (new    │    │ (button) │    │ (button) │    │(button)│    │ (button)│
│  user)  │    │ En/Hi/Mr │    │ Aur/Jal/ │    │ Cotton/│    │ Yes/No  │
└─────────┘    └──────────┘    │  Nagpur  │    │ Wheat/ │    └─────────┘
                               └──────────┘    │Soybean │
                                               └────────┘
```

- State stored in `onboarding_state` field of PROFILE record
- Supports both button replies and free-text input
- Multi-script keyword matching (e.g., "हिंदी" or "Hindi" both select Hindi)
- Any district name accepted (not just the 3 pre-configured ones)

### 5.2 RAG Query Pipeline

```python
# Prompt template injected into Bedrock Knowledge Base query:
"""
You are an agricultural extension agent helping smallholder farmers in India
with FARMING questions ONLY.
{language_instruction}  # e.g., "Respond in Hindi (Devanagari script)"
Include source citations.

IMPORTANT RESTRICTIONS:
- ONLY answer questions about agriculture, farming, crops, pests, diseases...
- If the question is about human health, medical issues... respond:
  "I can only help with farming questions."
"""
```

- **Model**: Claude 3 Sonnet (`anthropic.claude-3-sonnet-20240229-v1:0`)
- **Knowledge Base**: FAO manuals + ICAR-CICR research PDFs in S3
- **Vector Store**: OpenSearch Serverless (Titan Embeddings v1)
- **Guardrails** (optional): Block banned pesticides (paraquat, monocrotophos, endosulfan, methyl parathion, phorate), deny medical/financial advice, anonymize PII

### 5.3 Webhook Security

```
Inbound POST → Extract X-Hub-Signature-256 header
             → Load app_secret from Secrets Manager
             → HMAC-SHA256(app_secret, request_body)
             → Compare digest (constant-time)
             → Reject if mismatch (403)
```

- Configurable via `VERIFY_SIGNATURE` env var (disabled in dev)
- DynamoDB conditional write (`attribute_not_exists(PK)`) for message deduplication
- DONE/NOT YET messages skip SQS entirely — handled by DynamoDB Stream → ResponseDetector

### 5.4 Duplicate Nudge Prevention

The `has_pending_nudge()` function prevents multiple nudges per activity per day:

```python
# Query all NUDGE# records for this user
# Filter: same date + same activity + status in [SENT, REMINDED]
# If found → skip this farmer (don't send another nudge)
```

### 5.5 Voice Processing Pipeline

```
WhatsApp voice note (.ogg)
  → Download via Media API
  → Upload to S3 temp bucket
  → Amazon Transcribe batch job (language-specific: hi-IN, mr-IN, te-IN, en-IN)
  → Poll 1s intervals for up to 60s
  → Extract transcript + confidence score
  → If confidence ≥ 0.5: re-queue as text message with _source='voice' marker
  → MessageProcessor detects _source='voice' → generates Polly TTS response
  → Cleanup: delete S3 object + Transcribe job
```

### 5.6 Text-to-Speech (Voice Output)

```
Polly Voice Mapping:
  Hindi  → Aditi (hi-IN)     ✅ Native
  Marathi → Aditi (hi-IN)    ⚠️ Hindi fallback (understood by Marathi speakers)
  Telugu  → None              ⚠️ Text-only (no native Polly voice)
  English → Kajal (en-IN)    ✅ Neural bilingual voice

Process:
  1. Synthesize MP3 via Polly
  2. Upload to S3 temp bucket (1-day lifecycle)
  3. Generate presigned URL (1h expiry)
  4. Send as WhatsApp audio message
```

---

## 6. AWS Infrastructure (Two-Stack Deployment)

### Stack 1: Foundation (`template.yaml`)

| Resource | Type | Purpose |
|----------|------|---------|
| AgriNexusTable | DynamoDB | Single-table design, streams enabled, GSI1+GSI2 |
| KnowledgeBaseBucket | S3 | FAO PDF storage |
| BedrockKnowledgeBase | Bedrock KB | RAG over agricultural documents |
| OpenSearchCollection | AOSS | Vector store for embeddings |
| BedrockGuardrail | Bedrock Guardrail | Safety: banned pesticides, medical, PII |
| BedrockDataSource | Bedrock DataSource | S3 → KB sync (prefix: en/) |

### Stack 2: Application (`template-week2.yaml`)

| Resource | Type | Purpose |
|----------|------|---------|
| WhatsAppApi | API Gateway | REST API with /webhook endpoint |
| WebhookHandler | Lambda | Signature validation, routing, dedup |
| MessageProcessor | Lambda | Onboarding, RAG, vision, voice output |
| VoiceProcessor | Lambda | Transcribe voice notes (90s timeout) |
| DLQHandler | Lambda | Dialect-aware error messages |
| WeatherPoller | Lambda | Check weather every 6h |
| NudgeSender | Lambda | Send nudges, schedule reminders |
| ReminderSender | Lambda | T+24h and T+48h follow-ups |
| ResponseDetector | Lambda | DynamoDB Stream → DONE detection |
| NudgeStateMachine | Step Functions | Orchestrate nudge workflow |
| MessageQueue | SQS FIFO | Text/image message processing |
| VoiceQueue | SQS FIFO | Voice note processing (batch=1) |
| MessageDLQ | SQS FIFO | Failed messages (14-day retention) |
| TempAudioBucket | S3 | Temporary audio storage (1-day lifecycle) |
| SchedulerRole | IAM Role | EventBridge → Lambda invocation |

---

## 7. Multi-Language Support Matrix

| Feature | Hindi (hi) | Marathi (mr) | Telugu (te) | English (en) |
|---------|-----------|-------------|-------------|-------------|
| Onboarding | ✅ Devanagari | ✅ Devanagari | ✅ Telugu script | ✅ |
| RAG Q&A | ✅ | ✅ | ✅ | ✅ |
| Voice Input (STT) | ✅ hi-IN | ✅ mr-IN | ✅ te-IN | ✅ en-IN |
| Voice Output (TTS) | ✅ Aditi | ⚠️ Hindi fallback | ❌ Text only | ✅ Kajal |
| Vision Analysis | ✅ | ✅ | ✅ | ✅ |
| Nudge Messages | ✅ | ✅ | ✅ | ✅ |
| DONE keywords | हो गया, कर दिया | झाला, केला | అయ్యింది, చేశాను | done, completed |
| NOT YET keywords | अभी नहीं, बाद में | नाही झाला, नंतर | ఇంకా లేదు, తర్వాత | not yet, later |
| HELP command | मदद | मदत | సహాయం | HELP |

---

## 8. Error Handling & Resilience

```
                    ┌─────────────────────────────┐
                    │     WhatsApp Message         │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  WebhookHandler              │
                    │  - Signature validation       │
                    │  - DynamoDB dedup (WAMID#)   │
                    │  - 200 OK within 2 seconds   │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │  SQS FIFO Queue              │
                    │  - 3 retries                 │
                    │  - 180s visibility timeout   │
                    │  - 4-day retention           │
                    └──────────┬──────────────────┘
                               │
               ┌───────────────┴────────────────┐
               │ Success                  Failure (3x)
               ▼                               ▼
        Response sent              ┌───────────────────┐
        to farmer                  │  Dead Letter Queue │
                                   │  (14-day retention)│
                                   └─────────┬─────────┘
                                             │
                                   ┌─────────▼─────────┐
                                   │  DLQHandler Lambda │
                                   │  - Look up dialect │
                                   │  - Send error msg  │
                                   │    in user's lang   │
                                   └───────────────────┘
```

- **WhatsApp API calls**: 3 retries with exponential backoff (0.5s, 1s, 2s)
- **Idempotency**: DynamoDB conditional writes prevent duplicate processing
- **FIFO ordering**: Messages grouped by phone number maintain per-user order
- **Graceful degradation**: Voice failures → suggest typing; Vision failures → suggest text description

---

## 9. Secrets Management

All sensitive credentials stored in AWS Secrets Manager:

| Secret Path | Used By | Purpose |
|-------------|---------|---------|
| `agrinexus/whatsapp/verify-token` | WebhookHandler | Webhook verification challenge |
| `agrinexus/whatsapp/app-secret` | WebhookHandler | HMAC signature validation |
| `agrinexus/whatsapp/access-token` | All outbound Lambdas | WhatsApp Business API auth |
| `agrinexus/whatsapp/phone-number-id` | All outbound Lambdas | WhatsApp sender identity |

---

## 10. Monitoring & Metrics

Custom CloudWatch metrics emitted by the nudge engine:

| Metric | Namespace | Emitted By |
|--------|-----------|------------|
| `NudgesSent` | AgriNexus | NudgeSender Lambda |
| `NudgesCompleted` | AgriNexus | ResponseDetector Lambda |

**Completion Rate** = `NudgesCompleted / NudgesSent` (tracked on CloudWatch dashboard)

Standard Lambda metrics (invocations, errors, duration) available for all 8 functions via CloudWatch.

---

## 11. Cost Model (1,000 users/month)

| Service | Usage | Cost |
|---------|-------|------|
| DynamoDB | 1M reads, 500K writes | ~$0 (free tier) |
| DynamoDB Streams | 1M stream reads | ~$0.50 |
| S3 | 100 MB docs + temp audio | ~$0 (free tier) |
| Bedrock KB (RAG) | 1K queries | ~$5 |
| Bedrock Vision | 100 images | ~$3 |
| OpenSearch Serverless | 1 OCU minimum | ~$20 |
| Transcribe | 100 voice notes | ~$2 |
| Polly | 100 responses | ~$0.50 |
| Lambda | 50K invocations | ~$0 (free tier) |
| EventBridge Scheduler | 1K schedules | ~$1 |
| **Total** | | **~$32/month** |

OpenSearch Serverless is the cost floor at ~$20/month (1 OCU for indexing + 1 for search).
