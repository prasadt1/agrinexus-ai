# AgriNexus AI - Architecture Design Document

**Project**: AgriNexus AI - Behavioral AI Extension Agent  
**Competition**: AWS 10,000 AIdeas Competition (Social Impact Track)  
**Version**: 1.1  
**Date**: February 13, 2026 (doc refreshed April 2026 for deploy, DynamoDB shape, webhook limits)

## 1. Executive Summary

AgriNexus AI is a behavioral intervention engine and behavioral AI extension agent designed to close the "last mile" gap in agricultural extension for smallholder farmers. Unlike reactive information systems, AgriNexus utilizes a proactive, weather-timed behavioral nudge engine with closed-loop accountability to ensure agronomic advice translates into field action. The system prioritizes trust through dialect-native voice interactions (Hindi, Marathi, Telugu) and evidence-backed citations from validated FAO sources.

The architecture is a serverless system with pay-as-you-go Bedrock. Estimated cost: approximately $53/month for 1,000 farmers, with S3 vectors ($1.30) and Bedrock ($39 variable) as the primary cost drivers. The system leverages Amazon Bedrock (Claude 3 Sonnet) for dialect-aware conversations, S3 for vector storage (migrated from OpenSearch Serverless on April 4, 2026 for 75% cost reduction), EventBridge Scheduler for behavioral nudges, Claude 3 Vision for pest diagnosis, and Amazon Transcribe + Polly for voice accessibility.

## 2. Architecture Principles

- **Serverless First**: Use Lambda, DynamoDB, and managed services to minimize operational overhead and costs
- **Event-Driven**: Leverage EventBridge Scheduler and Step Functions for asynchronous workflows
- **Cost-Conscious**: Serverless architecture with pay-as-you-go Bedrock (approximately $53/month for 1,000 farmers; $0.64/farmer/year)
- **Scalable**: Design for 1,000 farmers in MVP with ability to scale to 10,000 post-MVP
- **Secure by Default**: Implement encryption, least-privilege IAM, and input validation throughout
- **Behavioral Closed Loop**: Track nudge → action → confirmation cycle with Nudge Completion Rate as primary metric

## 3. High-Level Architecture

```
┌─────────────────┐
│   Farmer        │
│  (WhatsApp)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS Cloud                                 │
│                                                              │
│  ┌──────────────┐      ┌─────────────────┐                 │
│  │ API Gateway  │─────▶│  Webhook Lambda │                 │
│  │  (Webhook)   │      │  (+ SQS routes) │                 │
│  └──────────────┘      └────────┬────────┘                 │
│                                  │                           │
│                    ┌─────────────┼─────────────┐            │
│                    ▼             ▼             ▼            │
│         ┌──────────────┐  ┌──────────┐  ┌──────────┐       │
│         │   Bedrock    │  │  Claude  │  │ DynamoDB │       │
│         │    Agent     │  │  Vision  │  │  (State) │       │
│         │   + RAG      │  │          │  │          │       │
│         └──────┬───────┘  └────┬─────┘  └────┬─────┘       │
│                │               │             │              │
│                ▼               ▼             │              │
│         ┌──────────────┐  ┌──────────┐      │              │
│         │      S3      │  │    S3    │      │              │
│         │ (Knowledge   │  │  (Temp   │      │              │
│         │    Base)     │  │  Images) │      │              │
│         └──────────────┘  └──────────┘      │              │
│                                              │              │
│  ┌───────────────────────────────────────────┘              │
│  │                                                          │
│  ▼                                                          │
│ ┌────────────────────────────────────────────┐             │
│ │         EventBridge (Scheduler)            │             │
│ │    (Weather Polling - Every 6 hours)       │             │
│ └──────────────────┬─────────────────────────┘             │
│                    │                                        │
│                    ▼                                        │
│         ┌──────────────────────┐                           │
│         │   Step Functions     │                           │
│         │   (Nudge Engine)     │                           │
│         └──────────┬───────────┘                           │
│                    │                                        │
│                    ▼                                        │
│         ┌──────────────────────┐                           │
│         │  Nudge Sender Lambda │                           │
│         │  → WhatsApp (buttons/│                           │
│         │    text / template)  │                           │
│         └──────────────────────┘                           │
│         (Polly: Message Processor for voice replies;       │
│          SNS topic in stack for optional ops alerts)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 4. Component Architecture

### 4.1 WhatsApp Integration Layer

**Components**: API Gateway + Lambda (Webhook Handler)

**Responsibilities**:
- Receive incoming WhatsApp messages via webhook
- Validate webhook signatures (Meta `X-Hub-Signature-256` + app secret)
- **Per-user rate limiting** before enqueueing work: count recent **`MSG#*`** items in DynamoDB within a configurable window (default 10 messages/hour; see SAM template `RATE_LIMIT_*` env vars)
- Extract message content (text, images, audio)
- Route to appropriate processing Lambda
- Send responses back to WhatsApp

**Data Flow**:
1. WhatsApp → API Gateway (POST /webhook)
2. API Gateway → Lambda (webhook handler)
3. Lambda validates signature, deduplicates by `wamid`
4. For **audio**: optional **voice-received** text to user (Common layer + Graph API), then SQS **Voice** queue → Voice Processor → Transcribe → message queue
5. For **text/image**: SQS **message** queue → Message Processor (RAG / Vision)
6. Lambdas call WhatsApp Cloud API for outbound messages (no separate “orchestrator” service)

**AWS Services**:
- API Gateway (REST API)
- Lambda (webhook-handler function)
- CloudWatch Logs

**Cost Optimization**:
- API Gateway: 1M requests/month free
- Lambda: 1M requests + 400,000 GB-seconds/month free
- Use Lambda proxy integration to minimize API Gateway costs

### 4.2 Conversation Engine (Bedrock Knowledge Base + Claude)

**Components**: Amazon Bedrock Agent **Runtime** (`retrieve_and_generate`) + Knowledge Base + S3

**Responsibilities**:
- Process messages using Claude 3 Sonnet
- Retrieve relevant agronomic knowledge using RAG (`bedrock-agent-runtime` retrieve and generate)
- Generate contextually appropriate responses in Hindi, Marathi, or Telugu
- Apply guardrails for agricultural safety
- Maintain conversation context natively

**Knowledge Base Structure** (S3):
```
s3://agrinexus-knowledge-base/
├── en/
│   ├── crop-management/
│   │   ├── cotton-cultivation.pdf
│   │   ├── rice-cultivation.pdf
│   │   └── wheat-cultivation.pdf
│   ├── pest-control/
│   │   ├── common-pests.pdf
│   │   └── organic-solutions.pdf
│   └── weather-adaptation/
│       └── climate-smart-practices.pdf
```

**Note**: English-only FAO manuals. Bedrock translates to user's dialect at response time.

**Bedrock Configuration**:
- Model: Claude 3 Sonnet (cost-effective, multilingual)
- Knowledge Base: S3 for document storage + S3 vectors for embeddings (approximately $1.30/month, pay-per-query)
- Guardrails: Block banned pesticides (Paraquat, Endosulfan), escalate medical/veterinary queries to KVK, include label disclaimers
- Agent Instructions: "You are an agricultural extension agent. Provide practical, actionable advice grounded in FAO data. Handle code-switching (e.g., Hinglish - mixed Hindi/English) naturally. Respond in the farmer's preferred language (Hindi, Marathi, or Telugu). Include simplified source citations."
- Language Support: Hindi (primary), Marathi, Telugu, and code-switched variants (Hinglish)

**Historical Note**: Originally used OpenSearch Serverless (approximately $174/month fixed cost). Migrated to S3 vectors on April 4, 2026 for 75% cost reduction (approximately $214/month → approximately $53/month).

**AWS Services**:
- Amazon Bedrock (Agent + Knowledge Base with S3 vectors)
- S3 (document storage + vector embeddings)

### 4.3 Visual Verification (Claude 3 Vision)

**Components**: Lambda + Claude 3 Vision + S3

**Responsibilities**:
- Extract images from WhatsApp messages
- Store temporarily in S3
- Analyze images for pest/disease identification
- Return diagnosis with confidence scores
- Clean up temporary storage

**Processing Flow**:
1. Image received → Store in S3 (temp bucket)
2. Invoke Bedrock with Claude 3 Vision
3. Prompt: "Analyze this crop image. Identify any pests, diseases, or health issues. Provide diagnosis and recommended actions."
4. Parse response for structured output
5. Delete image from S3
6. Return diagnosis to farmer

**Image Storage** (S3):
```
s3://agrinexus-temp-images/
├── {user_id}/
│   └── {timestamp}-{message_id}.jpg
```

**Lifecycle Policy**: Delete objects after 24 hours

**AWS Services**:
- Lambda (vision-processor function)
- Amazon Bedrock (Claude 3 Vision)
- S3 (temporary image storage)

### 4.4 User State Management (DynamoDB Single Table)

**Table**: `agrinexus-data`  
**Billing Mode**: On-Demand (PAY_PER_REQUEST)  
**Partition Key**: `PK` (String)  
**Sort Key**: `SK` (String)

**Design Rationale**: Single-table design reduces costs (one table vs. three), simplifies transactions, and enables efficient access patterns through composite keys.

**Entity Patterns**:

#### User Profile
```
PK: USER#+919876543210
SK: PROFILE
Attributes (representative; see create_user_profile / onboarding in code):
- phone_number: E.164
- dialect: "hi" | "mr" | "te" | "en"
- location: district key (e.g. "Latur")
- location_coords: optional [lat, lon]
- crop: e.g. "Cotton"
- consent: bool (nudge consent)
- onboarding_state / onboarding_complete: onboarding FSM
- demo_tier: "public" (default for new users: one nudge, no T+24h/T+48h) or override for full reminder loop
- created_at: ISO timestamp
- GSI1PK / GSI1SK: LOCATION#… / CROP#… for farmer queries
- voicePreference: optional
```

#### Conversation Messages
```
PK: USER#+919876543210
SK: MSG#{UTC ISO8601 timestamp}   # e.g. MSG#2026-04-11T12:00:00.123456
Attributes:
- wamid: WhatsApp message id
- message: raw message payload (map)
- response: assistant text (if stored)
- source_citation: citation string
- ttl: epoch seconds (~90 days)
```

#### Nudges (User View)
```
PK: USER#+919876543210
SK: NUDGE#{timestamp}#{activity}   # e.g. NUDGE#2026-04-11T10:00:00.123456#spray
Attributes:
- status: "SENT" | "REMINDED" | "DONE" | "EXPIRED"
- activity, crop, district, weather (map), message (text sent)
- GSI2PK: "NUDGE", GSI2SK: timestamp (for queries)
- ttl: epoch seconds (~180 days)
```

**Status Flow**:
- SENT: Initial nudge sent
- REMINDED: After T+24h or T+48h reminder sent
- DONE: Farmer clicked "Done" button (all schedules deleted)
- EXPIRED: Either farmer clicked "Not Yet" after T+48h OR no response by T+72h auto-expiry

**Global Secondary Indexes**:

#### GSI-1 (farmer / location queries)
- See template and code: `GSI1PK` / `GSI1SK` on profiles (e.g. `LOCATION#…`, `CROP#…`).

#### GSI-2 (nudge listings)
- `GSI2PK` / `GSI2SK` on nudge records for operational queries (see SAM template and `src/nudge/`).

**DynamoDB Streams**: Enable for real-time response detection (DONE/NOT YET keywords)

**Cost Optimization**:
- On-Demand pricing: Pay per request (no provisioned capacity)
- TTL: Automatic data expiration to reduce storage (MSG: 90d, NUDGE: 180d)
- Sparse indexes: Only index necessary attributes

### 4.5 Behavioral Nudge Engine (EventBridge Scheduler Pattern)

**Public demo behavior**: If the farmer’s **`PROFILE`** has **`demo_tier == "public"`** (default on new onboarding), the **Nudge Sender** sends **one** contextual nudge and **does not** create T+24h / T+48h / T+72h EventBridge schedules. Set **`demo_tier`** to another value in DynamoDB for partners who need the full closed loop.

**State Machine**: NudgeFlow (short-lived, completes in seconds)

**Trigger**: EventBridge scheduled rule (every 6 hours)

**Architecture Change**: Replace Step Functions long Wait states with EventBridge Scheduler pattern to avoid keeping executions alive for ~4 days.

**Workflow**:
```
StartState
  ↓
PollWeatherData (Lambda)
  ↓
EvaluateConditions (Choice State)
  ↓ (Favorable: wind <10km/h, no rain)
QueryFarmers (Lambda - DynamoDB query by location)
  ↓
SendNudges (Map State - Parallel execution)
  ↓
CreateEventBridgeSchedulerRecords (Lambda)
  ↓
END (execution completes)

Separate EventBridge Scheduler Records:
  T+24h: Triggers Reminder Lambda → checks DynamoDB status → if not DONE/EXPIRED, sends first reminder
  T+48h: Triggers Reminder Lambda → checks DynamoDB status → if not DONE/EXPIRED, sends second reminder
  T+72h: Triggers Expiry Lambda → marks nudge as "EXPIRED" in DynamoDB if no response

Real-time Response Detection (separate flow):
  DynamoDB Streams → response-detector Lambda → if DONE keyword matched, updates nudge status to DONE, deletes pending Scheduler records
  DynamoDB Streams → response-detector Lambda → if NOT YET keyword matched after T+48h, updates nudge status to EXPIRED, deletes pending Scheduler records
```

**State Machine Definition** (ASL - Simplified):
```json
{
  "Comment": "AgriNexus Behavioral Nudge Workflow (Short-Lived)",
  "StartAt": "PollWeatherData",
  "States": {
    "PollWeatherData": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:weather-poller",
      "Next": "EvaluateConditions",
      "Retry": [{
        "ErrorEquals": ["Lambda.ServiceException"],
        "IntervalSeconds": 2,
        "MaxAttempts": 3,
        "BackoffRate": 2
      }]
    },
    "EvaluateConditions": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.weatherFavorable",
        "BooleanEquals": true,
        "Next": "QueryFarmers"
      }],
      "Default": "NoActionNeeded"
    },
    "QueryFarmers": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:query-farmers",
      "Next": "CheckFarmerCount"
    },
    "CheckFarmerCount": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.farmers.count",
        "NumericGreaterThan": 0,
        "Next": "SendNudges"
      }],
      "Default": "NoFarmersFound"
    },
    "SendNudges": {
      "Type": "Map",
      "ItemsPath": "$.farmers.list",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "SendIndividualNudge",
        "States": {
          "SendIndividualNudge": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:send-nudge",
            "End": true
          }
        }
      },
      "Next": "CreateSchedulerRecords"
    },
    "CreateSchedulerRecords": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:create-scheduler-records",
      "Comment": "Creates EventBridge Scheduler records for T+24h, T+48h, T+72h",
      "End": true
    },
    "NoActionNeeded": {
      "Type": "Pass",
      "Result": {"message": "Weather conditions not favorable"},
      "End": true
    },
    "NoFarmersFound": {
      "Type": "Pass",
      "Result": {"message": "No farmers found matching criteria"},
      "End": true
    }
  }
}
```

**EventBridge Scheduler Pattern**:
```python
# create-scheduler-records Lambda
def create_reminder_schedules(nudge_id, user_id, language):
    scheduler = boto3.client('scheduler')
    
    # T+24h reminder
    scheduler.create_schedule(
        Name=f'{nudge_id}-reminder-24h',
        ScheduleExpression=f'at({calculate_time(24, "hours")})',
        Target={
            'Arn': 'arn:aws:lambda:REGION:ACCOUNT:function:reminder-handler',
            'Input': json.dumps({'nudgeId': nudge_id, 'userId': user_id, 'reminderType': '24h'})
        },
        FlexibleTimeWindow={'Mode': 'OFF'}
    )
    
    # T+48h reminder
    scheduler.create_schedule(
        Name=f'{nudge_id}-reminder-48h',
        ScheduleExpression=f'at({calculate_time(48, "hours")})',
        Target={
            'Arn': 'arn:aws:lambda:REGION:ACCOUNT:function:reminder-handler',
            'Input': json.dumps({'nudgeId': nudge_id, 'userId': user_id, 'reminderType': '48h'})
        },
        FlexibleTimeWindow={'Mode': 'OFF'}
    )
    
    # T+72h expiry (auto-expire if no response)
    scheduler.create_schedule(
        Name=f'{nudge_id}-expiry',
        ScheduleExpression=f'at({calculate_time(72, "hours")})',
        Target={
            'Arn': 'arn:aws:lambda:REGION:ACCOUNT:function:reminder-handler',
            'Input': json.dumps({'nudgeId': nudge_id, 'userId': user_id, 'reminderType': 'EXPIRY'})
        },
        FlexibleTimeWindow={'Mode': 'OFF'}
    )
```

**Response Detection** (DynamoDB Streams):
```python
# response-detector Lambda
DONE_KEYWORDS = {'done', 'finished', 'ho gaya', 'kar diya', 'zhala', 'ayyindi'}
NOT_YET_KEYWORDS = {'not yet', 'abhi nahi', 'baad mein', 'nahi zhala', 'inkaa ledu'}

def lambda_handler(event, context):
    for record in event['Records']:
        if record['eventName'] == 'INSERT':
            message = deserialize(record['dynamodb']['NewImage'])
            if message.get('entityType') == 'Message' and message.get('direction') == 'inbound':
                text_lower = message['content'].lower().strip()
                
                # Pre-filter: only check for pending nudges if keywords match
                if any(kw in text_lower for kw in (DONE_KEYWORDS | NOT_YET_KEYWORDS)):
                    is_done = any(kw in text_lower for kw in DONE_KEYWORDS)
                    
                    if is_done:
                        handle_nudge_response(message, status='DONE')
                        # Delete pending EventBridge Scheduler records
                        delete_pending_schedules(message['userId'])
                    else:
                        # NOT YET after T+48h → mark as EXPIRED
                        nudge = get_pending_nudge(message['userId'])
                        if nudge and nudge['sentAt'] < (time.time() - 48*3600):
                            handle_nudge_response(message, status='EXPIRED')
                            delete_pending_schedules(message['userId'])
                        else:
                            # NOT YET before T+48h → acknowledge but keep reminders
                            send_acknowledgment(message['userId'], message['dialect'])
```

**EventBridge Rule** (Weather Polling):
```
Rule Name: weather-polling-schedule
Schedule: rate(6 hours)
Target: Step Functions (NudgeFlow)
```

**AWS Services**:
- AWS Step Functions (Standard Workflows - short-lived)
- EventBridge (Scheduler + scheduled rules)
- Lambda (workflow tasks + reminder handlers)
- DynamoDB (state persistence)
- DynamoDB Streams (response detection)

**Cost Optimization**:
- Short-lived Step Functions: Minimal state transitions
- EventBridge Scheduler: Free for scheduled rules
- Lambda: Reuse existing free tier allocation

### 4.6 Voice Services (Amazon Transcribe + Polly)

**Components**: Amazon Transcribe + Amazon Polly + Lambda

**Voice Input** (Amazon Transcribe):
- Transcribe Hindi voice notes to text
- Marathi and Telugu transcription (verify availability; fallback to Hindi if unavailable)
- Confidence threshold: 0.5 (fallback to text prompt if below)
- Output: Transcribed text passed to Bedrock Agent

**Voice Output** (Amazon Polly):
- Convert text responses to speech in farmer's dialect
- Primary voice: Hindi Aditi/Neural (high quality)
- Marathi/Telugu: Best-effort (check Polly catalog; text fallback if unavailable)
- Output format: MP3 (compressed for WhatsApp)
- Storage: Temporary S3 bucket (24-hour lifecycle)

**Processing Flow**:
1. Voice note received → Download from WhatsApp
2. Upload to S3 (temp bucket)
3. Invoke Transcribe → Get text
4. If confidence < 0.5 → Send text fallback message
5. If confidence ≥ 0.5 → Process via Bedrock Agent
6. Generate Polly audio response
7. Send audio via WhatsApp
8. Delete temp files from S3

**Performance (actual MVP)**: Voice end-to-end typically **~30–45s** (batch Transcribe + RAG + Polly). **Phase 2** target: streaming STT and/or async pipeline to reduce perceived latency (see `docs/VOICE-LATENCY-PHASE2-PLAN.md`).

**AWS Services**:
- Amazon Transcribe (speech-to-text)
- Amazon Polly (text-to-speech)
- S3 (temporary audio storage)
- Lambda (voice-processor function)

### 4.7 Notification Services

**Components**: Amazon Polly + SNS + Lambda

**Urgent Alerts** (SNS):
- Topic: agrinexus-urgent-alerts
- Subscribers: Lambda function → WhatsApp
- Use cases: Pest outbreak warnings, severe weather alerts
- Delivery: High-priority WhatsApp messages

**AWS Services**:
- Amazon Polly (text-to-speech for voice responses)
- SNS (pub/sub messaging for urgent alerts)
- Lambda (notification dispatcher)

## 5. Security Architecture

### 5.1 Authentication & Authorization

**WhatsApp Webhook**:
- Signature validation using shared secret
- HTTPS only (TLS 1.2+)
- API Gateway: HTTPS only; optional resource policy (Meta has no fixed webhook IP list—signature verification is primary)

**IAM Roles** (Least Privilege):
```
Role: LambdaExecutionRole
Policies:
- CloudWatch Logs (write)
- DynamoDB (read/write specific tables)
- S3 (read/write specific buckets)
- Bedrock (invoke model)
- Step Functions (start execution)

Role: StepFunctionsExecutionRole
Policies:
- Lambda (invoke specific functions)
- DynamoDB (read/write)
- CloudWatch Logs (write)
```

### 5.2 Data Protection

**Encryption at Rest**:
- DynamoDB: AWS-managed KMS keys
- S3: SSE-S3 (AES-256)
- CloudWatch Logs: Encrypted by default

**Encryption in Transit**:
- API Gateway: HTTPS only
- All AWS service calls: TLS 1.2+

**PII Handling**:
- Minimize collection (phone number as userId only)
- No storage of sensitive personal data
- Bedrock guardrails: PII redaction enabled

### 5.3 Input Validation

**Lambda Functions**:
- Validate all webhook payloads
- Sanitize user inputs before DynamoDB writes
- Reject malformed requests (400 Bad Request)
- Rate limiting via API Gateway (1000 req/sec per user)

## 6. Monitoring & Observability

### 6.1 CloudWatch Metrics

**Custom Metrics**:
- **NudgesSent** (Count) - Total nudges delivered
- **NudgesCompleted** (Count) - Nudges with DONE response within 72h
- **NudgeCompletionRate** (Percentage) - (NudgesCompleted / NudgesSent) × 100
- **MessageVolume** (Count) - Messages received per hour
- **ResponseTime** (Milliseconds) - End-to-end latency (p50, p95, p99)
- **ModelLatency** (Milliseconds) - Claude 3 Sonnet latency (p95)
- **BedrockTokens** (Count) - Token usage for cost tracking
- **DLQDepth** (Count) - Messages in Dead Letter Queue

**AWS Service Metrics**:
- Lambda: Invocations, Errors, Duration, Throttles
- DynamoDB: ConsumedReadCapacity, ConsumedWriteCapacity
- API Gateway: Count, Latency, 4XXError, 5XXError
- Step Functions: ExecutionsStarted, ExecutionsFailed
- Transcribe: JobsStarted, JobsFailed
- Polly: CharactersProcessed

### 6.2 CloudWatch Dashboard: AgriNexus-Operations

**Widget 1**: NudgesSent vs NudgesCompleted (Time Series)  
**Widget 2**: Nudge Completion Rate Trend (Metric Math: (NudgesCompleted / NudgesSent) × 100)  
**Widget 3**: ModelLatency p95 for Claude 3 Sonnet (conversations + vision)  
**Widget 4**: DLQDepth (Alert if > 5)  
**Widget 5**: Message Volume (last 24 hours)  
**Widget 6**: Response Time p50, p95, p99  
**Widget 7**: Cost Estimate (current month)

**Metric Math for Completion Rate**:
```
SEARCH('{AgriNexus, Phone} MetricName="NudgesCompleted"', 'Sum', 300) / 
SEARCH('{AgriNexus, Phone} MetricName="NudgesSent"', 'Sum', 300) * 100
```

### 6.3 CloudWatch Alarms

**Critical Alarms**:
- Lambda error rate > 5% (5-minute period)
- API Gateway 5XX errors > 10 (1-minute period)
- DynamoDB throttling events > 0
- Step Functions execution failures > 0
- DLQDepth > 5 messages
- Estimated monthly cost > $75 (billing alarm)
- Bedrock RAG invocation latency p95 > 15 seconds (text queries; tune the threshold per model and environment)
- Optional separate checks: voice pipeline (Transcribe → RAG → Polly) often ~30–45s batch path — use logs or custom metrics rather than the same threshold as text

**Notification**: SNS topic → Email to dev team

### 6.4 Logging Strategy

**Log Groups**:
- /aws/lambda/webhook-handler
- /aws/lambda/conversation-processor
- /aws/lambda/vision-processor
- /aws/lambda/nudge-engine/*
- /aws/apigateway/agrinexus-api

**Log Retention**: 7 days (Free Tier: 5GB ingestion/month)

**Structured Logging** (JSON):
```json
{
  "timestamp": "2026-02-13T10:30:00Z",
  "requestId": "abc-123",
  "userId": "+919876543210",
  "action": "conversation",
  "duration": 1234,
  "bedrockTokens": 450,
  "status": "success"
}
```

### 6.5 Distributed Tracing

**X-Ray** (Optional, post-MVP):
- Trace requests across Lambda, API Gateway, DynamoDB
- Identify bottlenecks and cold starts
- Free Tier: 100,000 traces/month

## 7. Deployment Architecture

### 7.1 Infrastructure as Code

**Tool**: AWS SAM (Serverless Application Model)

**Project Structure**:
```
agrinexus-ai/
├── template.yaml (SAM template)
├── src/
│   ├── webhook-handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── conversation-processor/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── vision-processor/
│   │   ├── app.py
│   │   └── requirements.txt
│   └── nudge-engine/
│       ├── weather-poller.py
│       ├── query-farmers.py
│       ├── send-nudge.py
│       └── requirements.txt
├── knowledge-base/
│   └── pdfs/ (FAO documents)
├── tests/
│   ├── unit/
│   └── integration/
└── .kiro/
    └── hooks/ (pre-commit, pre-push)
```

### 7.2 CI/CD Pipeline

**Git Workflow**:
1. Developer commits code
2. Pre-commit hook: Linting (flake8, black)
3. Pre-push hook: Security scan (bandit, safety)
4. Push to GitHub
5. GitHub Actions: Run tests
6. SAM build & deploy to AWS

**GitHub Actions Workflow**:
```yaml
name: Deploy AgriNexus AI
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: aws-actions/setup-sam@v2
      - run: sam build
      - run: sam deploy --no-confirm-changeset
```

### 7.3 Environment Management

**Environments**:
- Development: dev-agrinexus (personal AWS account)
- Production: prod-agrinexus (competition AWS account)

**Configuration**:
- Environment variables in SAM template
- Secrets in AWS Secrets Manager (WhatsApp API keys)

## 8. Cost Analysis (Free-Tier-Leaning Architecture)

### 8.1 Monthly Usage Estimates (MVP - 1,000 farmers)

**Assumptions**:
- 10 messages/farmer/day = 10,000 messages/day = 300,000/month
- 5% include images = 15,000 images/month
- 10% include voice = 30,000 voice messages/month
- 2 nudges/farmer/week = 8,000 nudges/month

**Service Costs**:

| Service | Usage | Free Tier | Overage Cost |
|---------|-------|-----------|--------------|
| Lambda | 500,000 invocations | 1M free | $0 |
| Lambda | 200,000 GB-sec | 400,000 free | $0 |
| API Gateway | 300,000 requests | 1M free | $0 |
| DynamoDB | On-demand | 25M RCU/WCU free | approximately $0.90 |
| S3 Storage | 5 GB | 5 GB free | $0 |
| S3 Requests | 50,000 PUT | 2,000 free | approximately $0.24 |
| S3 Vectors | 300K queries | Pay-per-query | approximately $1.30 |
| Bedrock (Claude 3 Sonnet RAG) | 3M input + 1.5M output tokens | Pay-as-you-go | approximately $32 |
| Bedrock (Claude 3 Vision) | 100 images | Pay-as-you-go | approximately $5 |
| Transcribe | 500 voice minutes | $0.024/min | approximately $12 |
| Polly | 200 min output | $4/1M chars | approximately $2 |
| Step Functions | 10,000 transitions | 4,000 free | approximately $0.15 |
| EventBridge Scheduler | 8,000 schedules | Free | approximately $0.01 |
| Lambda, API Gateway, SQS, S3 | | Free tier | $0 |
| **Total (1K farmers)** | | | **approximately $53/month** |

**Historical Note**: Originally used OpenSearch Serverless (approximately $174/month fixed cost). Migrated to S3 vectors on April 4, 2026 for 75% cost reduction (approximately $214/month → approximately $53/month). S3 vectors are pay-per-query with 100-800ms latency, acceptable for chatbot use cases.

**Other Cost Optimization Strategies**:
- Implement response caching for common queries (reduce Bedrock calls)
- Use S3 lifecycle policies (images auto-delete after 7 days)
- Monitor and alert on cost thresholds ($200, $300, $400)

### 8.2 Scaling Projections (10,000 farmers - Post-MVP)

**Estimated Monthly Cost**: approximately **$450** with S3 Vectors (approximately **$13** vectors + approximately **$437** variable), assuming **10×** the §8.1 usage (messages, images, voice, nudges) — **linear projection**, **not** measured billing at 10K users.

**Cost per Farmer per Year**: approximately **$0.54** (10K farmers) vs approximately **$0.64** (1K farmers). The **$0.54** value is **($450 × 12) ÷ 10,000** — it is **derived arithmetic** from the projected monthly total, **not** an independent benchmark. **Minimal economies of scale** with a pay-per-query model: variable services dominate, so per-farmer cost falls only modestly as headcount rises.

**Clarification (modeled vs actual)**:
- **§8.1 (~$53/mo @ 1K)** and **§8.2 (~$450/mo @ 10K)** are **spreadsheet / pricing-calculator estimates** using the stated assumptions. **Current** production traffic may be far lower — **use AWS Cost Explorer** for real spend.
- The **10K** figure is **not validated** until the system runs at that load; treat as **directional** for roadmaps and pitch decks.

**Bottlenecks**:
- DynamoDB read/write capacity
- Bedrock token usage
- Lambda concurrent executions
- Transcribe minutes

**Mitigation**:
- DynamoDB: Switch to provisioned capacity with auto-scaling
- Bedrock: Implement aggressive caching + prompt optimization
- Lambda: Request concurrency limit increase
- Transcribe: Optimize audio preprocessing to reduce minutes

## 9. Development Roadmap (4-Week Sprint)

### Week 1: Foundation + Knowledge Base

**Tasks**:
- [ ] SAM setup with single-table DynamoDB (`agrinexus-data` with GSIs)
- [ ] FAO PDF upload and Bedrock KB index with S3 vectors
- [ ] Configure Bedrock Guardrails (banned pesticides, KVK escalation)
- [ ] Test Bedrock responses in Hindi, Marathi, Telugu from English source docs
- [ ] Implement 20 golden questions for RAG quality testing

**Acceptance**:
- Table created, PutItem/Query works
- S3 `en/` contains manuals; KB with S3 vectors passes 20 golden questions
- Bot refuses request for "Paraquat" and medical advice
- Coherent responses in all three dialects

### Week 2: Nudge Engine + WhatsApp

**Tasks**:
- [ ] WhatsApp webhook + signature validation + idempotency (wamid)
- [ ] Onboarding flow with WhatsApp Interactive Buttons
- [ ] Weather Poller + Step Function (short-lived)
- [ ] EventBridge Scheduler for reminders (T+24h, T+48h, T+72h)
- [ ] Response detector (DynamoDB Streams)
- [ ] Register WhatsApp message templates for nudges and alerts
- [ ] Test full closed-loop: nudge → reminder → DONE → log completion

**Acceptance**:
- Re-sent message does not trigger duplicate Lambda
- User completes onboarding with dialect, location, crop, consent
- Execution completes and sends test nudge based on weather mock
- Reminder record created at T+24h; second at T+48h
- "Ho gaya" updates nudge status to DONE

### Week 3: Conversations + Voice + Vision

**Tasks**:
- [ ] Conversation Lambda with RAG and source citations
- [ ] Transcribe + Polly integration
- [ ] Vision Processor (Claude 3 Vision via invoke_model)
- [ ] DLQ + dlq-handler (apology in user's dialect)
- [ ] Test all three dialects for conversation quality
- [ ] Implement 20 guardrail test scenarios

**Acceptance**:
- User asks crop question, gets Hindi response with FAO citation
- Voice round-trip on MVP batch path ~30–45s p95 with immediate voice-received ACK; Phase 2 targets sub-10s (`docs/VOICE-LATENCY-PHASE2-PLAN.md`)
- Cotton pest identified correctly from test image within 15s
- Failed processing sends apology message in user's dialect
- Guardrail tests achieve 100% refusal rate

### Week 4: Demo Polish + Article

**Tasks**:
- [ ] CloudWatch Dashboard (Completion Rate metric, DLQ depth, latency)
- [ ] End-to-end integration tests for Latur demo scenario
- [ ] Run guardrail test suite (20 scenarios) and RAG golden questions
- [ ] Performance testing (p95 latency with 10 concurrent users)
- [ ] End-to-End Demo Video (Latur Farmer scenario)
- [ ] Article publication on AWS Builder Center (#aideas-2025, #EMEA tags)
- [ ] Cost audit: verify actual spend vs. $53/month estimate (S3 vectors approximately $1.30 + Bedrock approximately $39 + other approximately $13)

**Acceptance**:
- Dashboard shows Completion Rate metric, DLQ depth, latency
- Latur demo scenario works end-to-end
- All tests pass with required thresholds
- End-to-end demo video (Latur farmer scenario) recorded without manual intervention
- Article submitted before the applicable Builder Center / competition deadline (confirm current date)
- Actual cost ≤ $60/month (verify against live billing)

**Note**: Competition and article deadlines change by year—confirm against the active program schedule.

## 10. Risk Mitigation

### 10.1 Technical Risks

**Risk**: Bedrock knowledge base retrieval quality is poor  
**Mitigation**: Curate and structure PDFs carefully; test with diverse queries; implement fallback responses

**Risk**: WhatsApp API rate limits  
**Mitigation**: Implement exponential backoff; queue messages in SQS; monitor rate limit headers

**Risk**: Lambda cold starts cause timeouts  
**Mitigation**: Use provisioned concurrency for critical functions; optimize package size; implement warming

### 10.2 Cost Risks

**Risk**: Unexpected AWS charges exceed budget  
**Mitigation**: Set up billing alarms at $50, $75, $100; monitor daily; implement aggressive caching

**Risk**: DynamoDB costs spike with usage  
**Mitigation**: Use on-demand initially; monitor usage patterns; switch to provisioned if predictable

### 10.3 Competition Risks

**Risk**: MVP not ready by March 13 deadline  
**Mitigation**: Follow strict weekly milestones; prioritize core features; have fallback demo plan

## 11. Success Metrics

**Primary Metric**:
- **Nudge Completion Rate**: (Confirmed DONE Responses / Total Favorable-Condition Nudges Sent) × 100
- **Target**: ≥40% completion rate within 72 hours

**Technical Metrics**:
- 95% of text messages processed within 5 seconds (p95)
- 95% of vision analysis within 15 seconds
- Voice: batch pipeline; track p95 end-to-end time and optimize in Phase 2 (streaming STT)—**not** a sub-10s target until then
- 99% uptime during business hours (6 AM - 10 PM IST)
- Zero security vulnerabilities in code scans
- <$60 total AWS costs during MVP phase

**User Metrics**:
- 80% of farmers complete onboarding
- 60% response rate to behavioral nudges (DONE or NOT YET)
- 40% "DONE" completion rate for nudges
- 90% RAG accuracy on golden questions across all three dialects

**Competition Metrics**:
- Working demo for judges (Latur Cotton Farmer scenario)
- All promised features functional (Tier 1 + Tier 2)
- Clear differentiation from reactive information systems
- Compelling "closed loop" demonstration with real-time dashboard

## 12. Post-MVP Roadmap

### Phase 2 (Month 2-3):
- **Amazon Transcribe Streaming API**: Migrate from batch transcription to streaming for <2s voice latency (currently 20-30s)
- Additional Indian dialects (Kannada, Tamil, Bengali, Punjabi)
- Expanded crop coverage (rice, sugarcane, pulses, vegetables)
- Advanced vision: multi-image comparison, disease progression tracking
- 2-way Amazon Connect escalation to human extension workers

### Phase 3 (Month 4-6):
- IoT soil moisture sensor triggers
- Offline-capable message queuing via SQS for low-connectivity areas
- Advanced analytics dashboard for extension coordinators
- Integration with government schemes (PM-KISAN, soil health cards)

### Phase 4 (Month 6-12):
- Scale to 10,000+ farmers with provisioned DynamoDB capacity + Bedrock caching
- Direct partnership with regional KVKs for content validation
- Impact measurement study (crop yield changes vs. control group)
- Revenue model: premium advisory tier, institutional licensing for NGOs/government

## 13. Appendix

### 13.1 AWS Service Limits (Free Tier)

- Lambda: 1M requests, 400,000 GB-seconds/month
- DynamoDB: 25 GB storage, 25 read/write capacity units
- S3: 5 GB storage, 20,000 GET, 2,000 PUT requests
- API Gateway: 1M API calls/month (12 months)
- Bedrock: Pay-as-you-go (no free tier)
- Step Functions: 4,000 state transitions/month

### 13.2 Reference Architecture Diagrams

See `/docs/diagrams/` for detailed component diagrams (to be created).

### 13.3 Glossary

- **EARS**: Easy Approach to Requirements Syntax
- **FAO**: Food and Agriculture Organization (UN)
- **MVP**: Minimum Viable Product
- **RAG**: Retrieval Augmented Generation
- **TTL**: Time To Live (DynamoDB feature)
- **GSI**: Global Secondary Index (DynamoDB)

---

**Document Status**: Draft v1.0  
**Next Review**: Week 1 completion (Feb 20, 2026)  
**Owner**: Technical Co-Founder
