# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgriNexus AI is a serverless WhatsApp chatbot for smallholder farmers in India, providing AI-powered agronomic advice, voice/image support, and behavioral nudges. Built on AWS SAM with Amazon Bedrock (RAG, Claude Vision, Transcribe, Polly) and the WhatsApp Business API.

## Build & Deploy

The active SAM template is `template-week2.yaml` (not `template.yaml` or `template-simple.yaml`).

```bash
# Build
sam build --template template-week2.yaml

# Deploy (uses samconfig-week2.toml)
sam deploy --config-file samconfig-week2.toml

# Or with explicit overrides
sam deploy --template-file .aws-sam/build/template.yaml \
  --stack-name agrinexus-week2 \
  --parameter-overrides "KnowledgeBaseId=YOUR_KB_ID GuardrailId='' Environment=dev TableName=agrinexus-data GuardrailVersion=1" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --resolve-s3
```

All Lambda functions run **Python 3.11**.

## Running Tests

```bash
# RAG/Q&A tests (requires KNOWLEDGE_BASE_ID env var set)
pytest tests/test_golden_questions.py -v

# Voice pipeline test (pass an audio file path, language code, topic)
python tests/test_voice_simple.py path/to/audio.mp3 hi cotton

# Vision/pest detection test
python tests/test_vision.py path/to/image.jpg en cotton

# Full voice round-trip (requires TEMP_AUDIO_BUCKET env var)
python tests/test_voice_end_to_end.py

# Nudge flow tests
pytest tests/test_nudge_flow.py -v
```

Test env vars needed: `KNOWLEDGE_BASE_ID`, `TEMP_AUDIO_BUCKET`, `VOICE_QUEUE_URL`.

## Architecture

### Message Flow

**Text query:** WhatsApp -> API Gateway -> `WebhookHandler` (validates HMAC-SHA256 signature, checks DynamoDB idempotency) -> SQS FIFO queue -> `MessageProcessor` (onboarding state machine or Bedrock RAG) -> WhatsApp Cloud API

**Voice query:** WhatsApp -> `WebhookHandler` -> VoiceQueue -> `VoiceProcessor` (Transcribe) -> SQS -> `MessageProcessor` -> Bedrock RAG -> Polly -> WhatsApp

**Image query:** WhatsApp -> `WebhookHandler` -> SQS -> `MessageProcessor` -> `analyzer.py` (Claude Vision) -> WhatsApp

**Nudge flow:** `WeatherPoller` (EventBridge scheduled) -> Step Functions (`statemachine/nudge-workflow.asl.json`) -> `NudgeSender` -> WhatsApp + EventBridge Scheduler (T+24h, T+48h reminders) -> `ReminderSender`. `ResponseDetector` listens on DynamoDB Streams to detect DONE/NOT YET replies and cancel pending reminders.

### Lambda Functions (src/)

| Function | File | Purpose |
|----------|------|---------|
| WebhookHandler | `src/webhook/handler.py` | HMAC validation, idempotency, SQS routing |
| MessageProcessor | `src/processor/handler.py` | Onboarding FSM, Bedrock RAG, voice output |
| VoiceProcessor | `src/voice/processor.py` | Transcribe audio to text, re-queue |
| NudgeSender | `src/nudge/sender.py` | Send weather-triggered nudges |
| ReminderSender | `src/nudge/reminder.py` | T+24h/T+48h follow-up reminders |
| ResponseDetector | `src/nudge/detector.py` | DynamoDB Streams consumer, detect DONE |
| WeatherPoller | `src/weather/handler.py` | Check weather, start Step Functions |
| DLQHandler | `src/dlq/handler.py` | Failed message error recovery |

### Shared Layer

`src/common-layer/python/common/whatsapp.py` — `send_whatsapp_message()` with 5-minute Secrets Manager credential caching. Imported by all Lambdas that send messages.

### Key Module Relationships

`src/processor/handler.py` imports `output.py` (Polly TTS) and `analyzer.py` (Claude Vision) as local relative imports (not package imports). These three files must be co-located in the same Lambda package.

### Data Store: DynamoDB Single-Table

Table name: `agrinexus-data` (configured via `TABLE_NAME` env var)

Key patterns:
- User profile: `PK=USER#<phone>`, stores `onboarding_state`, `dialect`, `district`, `crop`, `nudge_consent`
- Idempotency: `PK=MSG#<wamid>` to deduplicate WhatsApp message delivery
- Nudge tracking: records sent nudges and completion status for duplicate prevention

### WhatsApp Secrets (Secrets Manager)

- `agrinexus/whatsapp/verify-token` — webhook verification
- `agrinexus/whatsapp/app-secret` — HMAC-SHA256 signature validation
- `agrinexus/whatsapp/access-token` — Cloud API auth
- `agrinexus/whatsapp/phone-number-id` — outbound sender ID

Signature verification can be disabled in dev via `VERIFY_SIGNATURE=false` on the webhook Lambda.

### Onboarding State Machine

Implemented in `src/processor/handler.py`. States: language selection -> district -> crop -> nudge consent -> `COMPLETE`. Supported languages/dialects: `hi` (Hindi), `mr` (Marathi), `te` (Telugu), `en` (English). Valid districts: Aurangabad, Jalna, Nagpur. Valid crops: Cotton, Wheat, Soybean, Maize.

### Voice Language Support

Defined in `src/voice/output.py`:
- Hindi: Polly voice `Aditi`, engine `standard`
- English (IN): Polly voice `Kajal`, engine `neural`
- Marathi: Polly voice `Aditi`, engine `standard`
- Telugu: No Polly voice — text-only fallback

## Monitoring & Debugging

```bash
# Tail Lambda logs
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow
aws logs tail /aws/lambda/agrinexus-processor-dev --follow
aws logs tail /aws/lambda/agrinexus-voice-dev --follow

# Manually invoke functions
aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/response.json
aws lambda invoke --function-name agrinexus-voice-dev --payload '{}' /tmp/response.json

# Reset user profile for re-onboarding
./scripts/reset-profile.sh +919876543210

# Run E2E demo flow
./scripts/e2e-test.sh --phone +919876543210
```

Create `scripts/demo.env` (gitignored) with `WEBHOOK_URL`, `APP_SECRET`, `PHONE_NUMBER` — all test scripts auto-load it.

## Key Documentation

- `architecture.md` — full system design
- `architecture/diagrams.md` — Mermaid flow diagrams
- `docs/E2E-TEST-GUIDE.md` — end-to-end test walkthrough
- `docs/CODE-WALKTHROUGH.md` — component-by-component guide
- `ISSUES-LOG.md` — 38+ resolved debugging issues
- `requirements.md` — EARS requirements specification (100+ requirements)
