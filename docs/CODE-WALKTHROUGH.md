# AgriNexus AI — Code Walkthrough

This document explains the architecture and core logic of the AgriNexus AI codebase. It’s designed for new contributors and judges who want a clear map from AWS services to source code.

## 1. High-Level Architecture

**Message Flow**
1. WhatsApp → API Gateway → `WebhookHandler` Lambda
2. Webhook stores dedup + message → DynamoDB → SQS
3. `MessageProcessor` Lambda handles text/image/RAG/voice response
4. Responses are sent back to WhatsApp via Meta Graph API

**Nudge Flow**
1. `WeatherPoller` runs on schedule (EventBridge)
2. If conditions favorable, Step Functions triggers
3. `NudgeSender` sends WhatsApp template or text fallback
4. EventBridge Scheduler creates T+24h / T+48h reminders
5. `ResponseDetector` listens on DynamoDB Streams for DONE/NOT YET

## 2. AWS Services → Code Mapping

- **API Gateway**: `template-week2.yaml` → `WhatsAppApi`
- **Lambda Functions**: `src/*/`
- **SQS Queues**: `MessageQueue`, `VoiceQueue`, `MessageDLQ`
- **DynamoDB**: single table `agrinexus-data`
- **Bedrock**: RAG + Vision
- **Transcribe/Polly**: voice pipeline
- **Step Functions**: `statemachine/nudge-workflow.asl.json`
- **CloudWatch**: dashboard JSON in `dashboards/`

## 3. Core Components (Source Code)

### 3.1 Webhook Handler (`src/webhook/handler.py`)
**Purpose**: Entry point for all WhatsApp traffic.

Key responsibilities:
- Verify webhook signature (`verify_signature`)
- Deduplicate messages (conditional DynamoDB write)
- Store inbound messages for response detection
- Route audio → `VoiceQueue`, others → `MessageQueue`

Key functions:
- `verify_signature(payload, signature)`
- `should_skip_rag(text)` (DONE/NOT YET detection shortcut)
- `lambda_handler(event, context)`

### 3.2 Message Processor (`src/processor/handler.py`)
**Purpose**: Main AI workflow for text/image messages.

Key responsibilities:
- Onboarding state machine
- Language handling
- Bedrock RAG query
- WhatsApp reply (text or buttons)

Key functions:
- `handle_onboarding(...)`
- `query_bedrock(...)`
- `send_whatsapp_message(...)`
- `send_whatsapp_buttons(...)`

### 3.3 Voice Processor (`src/voice/processor.py`)
**Purpose**: Convert WhatsApp voice notes → text.

Key responsibilities:
- Download audio from WhatsApp
- Upload to S3
- Start Transcribe job + poll
- Queue transcript into `MessageQueue`

### 3.4 Vision Analyzer (`src/processor/analyzer.py`)
**Purpose**: Diagnose crop images.

Key responsibilities:
- Download image from WhatsApp
- Invoke Claude 3 Sonnet Vision
- Return diagnosis in local language

### 3.5 Weather Poller (`src/weather/handler.py`)
**Purpose**: Trigger nudges based on weather.

Key responsibilities:
- Get unique farmer locations
- (Mock or real) weather evaluation
- Trigger Step Functions with nudge payload

### 3.6 Nudge Sender (`src/nudge/sender.py`)
**Purpose**: Send nudges + schedule reminders.

Key responsibilities:
- Dedup nudge per activity/day
- Send WhatsApp template (fallback to text)
- Create reminder schedules (T+24h, T+48h)
- Emit custom metric `NudgesSent`

### 3.7 Reminder Sender (`src/nudge/reminder.py`)
**Purpose**: Send reminder if task incomplete.

Key responsibilities:
- Check nudge status
- Send reminder via WhatsApp
- Update status to REMINDED

### 3.8 Response Detector (`src/nudge/detector.py`)
**Purpose**: Detect DONE/NOT YET and close loop.

Key responsibilities:
- Listen to DynamoDB Streams
- Detect DONE/NOT YET phrases (multi-language)
- Update nudge status to DONE
- Delete reminder schedules
- Emit `NudgesCompleted` metric

### 3.9 DLQ Handler (`src/dlq/handler.py`)
**Purpose**: Send fallback errors in local dialect.

Key responsibilities:
- Extract phone number
- Lookup dialect
- Send apology message

## 4. Data Model (Single Table)

Common patterns in DynamoDB:
- `PK = USER#<phone>`
- `SK = PROFILE` → user profile
- `SK = MSG#<timestamp>` → message records
- `SK = NUDGE#<timestamp>#<activity>` → nudge records

GSIs:
- `GSI1PK = LOCATION#<district>` (query farmers by location)

## 5. Scripts and Testing

**Demo scripts**:
- `scripts/demo-scenario.sh`
- `scripts/demo-nudge-flow.sh`
- `scripts/demo-nudge-multilang.sh`
- `scripts/reset-onboard-and-demo.sh`

**Tests**:
- `tests/test_nudge_flow.py`
- `tests/test_golden_questions.py`
- `tests/test_vision.py`

## 6. Observability

- CloudWatch dashboard: `dashboards/cloudwatch-dashboard.json`
- Custom metrics:
  - `AgriNexus/NudgesSent`
  - `AgriNexus/NudgesCompleted`

## 7. Quick Pointers for New Contributors

- Start at `template-week2.yaml` to see all AWS resources.
- Follow message flow: `webhook` → `processor` → `whatsapp`.
- Follow nudge flow: `weather` → `nudge/sender` → `scheduler` → `reminder` → `detector`.
- Use the demo scripts to validate behavior end-to-end.
