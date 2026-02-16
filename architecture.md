# AgriNexus AI - Architecture Design Document

**Project**: AgriNexus AI - Behavioral AI Extension Agent  
**Competition**: AWS 10,000 AIdeas Competition (Social Impact Track)  
**Version**: 1.0  
**Date**: February 13, 2026

## 1. Executive Summary

AgriNexus AI is a behavioral intervention engine and behavioral AI extension agent designed to close the "last mile" gap in agricultural extension for smallholder farmers. Unlike reactive information systems, AgriNexus utilizes a proactive, weather-timed behavioral nudge engine with closed-loop accountability to ensure agronomic advice translates into field action. The system prioritizes trust through dialect-native voice interactions (Hindi, Marathi, Telugu) and evidence-backed citations from validated FAO sources.

The architecture is a free-tier-leaning serverless system with pay-as-you-go Bedrock. Estimated cost: ~$50/month for 1,000 users, with OpenSearch Serverless (~$20) and Bedrock (~$15) as the primary cost drivers. The system leverages Amazon Bedrock (Claude 3 Sonnet) for dialect-aware conversations, EventBridge Scheduler for behavioral nudges, Claude 3 Vision for pest diagnosis, and Amazon Transcribe + Polly for voice accessibility.

## 2. Architecture Principles

- **Serverless First**: Use Lambda, DynamoDB, and managed services to minimize operational overhead and costs
- **Event-Driven**: Leverage EventBridge Scheduler and Step Functions for asynchronous workflows
- **Cost-Conscious**: Free-tier-leaning architecture with pay-as-you-go Bedrock (~$50/month for 1,000 users)
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
│  │ API Gateway  │─────▶│  Lambda         │                 │
│  │  (Webhook)   │      │  (Orchestrator) │                 │
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
│         │  Lambda (Send Nudge) │                           │
│         │  + Polly (Voice)     │                           │
│         │  + SNS (Alerts)      │                           │
│         └──────────────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 4. Component Architecture

### 4.1 WhatsApp Integration Layer

**Components**: API Gateway + Lambda (Webhook Handler)

**Responsibilities**:
- Receive incoming WhatsApp messages via webhook
- Validate webhook signatures (Twilio/Meta)
- Extract message content (text, images, audio)
- Route to appropriate processing Lambda
- Send responses back to WhatsApp

**Data Flow**:
1. WhatsApp → API Gateway (POST /webhook)
2. API Gateway → Lambda (webhook-handler)
3. Lambda validates signature
4. Lambda extracts message type and content
5. Lambda invokes appropriate processor (conversation or vision)

**AWS Services**:
- API Gateway (REST API)
- Lambda (webhook-handler function)
- CloudWatch Logs

**Cost Optimization**:
- API Gateway: 1M requests/month free
- Lambda: 1M requests + 400,000 GB-seconds/month free
- Use Lambda proxy integration to minimize API Gateway costs

### 4.2 Conversation Engine (Bedrock Agent)

**Components**: Amazon Bedrock Agent + Knowledge Base + S3

**Responsibilities**:
- Process messages using Claude 3 Sonnet
- Retrieve relevant agronomic knowledge using RAG
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
- Knowledge Base: S3 + OpenSearch Serverless vector store (~$20/month for 1 OCU)
- Guardrails: Block banned pesticides (Paraquat, Endosulfan), escalate medical/veterinary queries to KVK, include label disclaimers
- Agent Instructions: "You are an agricultural extension agent. Provide practical, actionable advice grounded in FAO data. Handle code-switching (e.g., Hinglish - mixed Hindi/English) naturally. Respond in the farmer's preferred language (Hindi, Marathi, or Telugu). Include simplified source citations."
- Language Support: Hindi (primary), Marathi, Telugu, and code-switched variants (Hinglish)

**AWS Services**:
- Amazon Bedrock (Agent + Knowledge Base with OpenSearch Serverless vector store)
- S3 (document storage)

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
Attributes:
- entityType: "UserProfile"
- userId: "+919876543210"
- location: {district: "Aurangabad District", state: "Maharashtra", country: "India"}
- crops: ["cotton", "soybean"]
- language: "hi" (Hindi)
- dialect: "Marathi"
- voicePreference: true
- consent: true
- registeredAt: Unix timestamp
- lastActive: Unix timestamp
- profileComplete: true
```

#### Conversation Messages
```
PK: USER#+919876543210
SK: MSG#1707955200#abc123
Attributes:
- entityType: "Message"
- messageId: "abc123"
- wamid: "wamid.HBgNOTE3..."
- timestamp: 1707955200
- direction: "inbound" | "outbound"
- content: "Mere cotton mein pests hain"
- messageType: "text" | "image" | "audio"
- language: "hi"
- sessionId: "session-xyz789"
- source_citation: "FAO Cotton Guide, Section 3"
- bedrockResponse: {model: "claude-3-sonnet", tokens: 450}
- TTL: 1715731200 (90 days)
```

#### Nudges (User View)
```
PK: USER#+919876543210
SK: NUDGE#1707955200#spray-pesticide
Attributes:
- entityType: "Nudge"
- nudgeId: "2026-02-14-spray-pesticide-aurangabad"
- activity: "spray_pesticide"
- sentAt: 1707955200
- scheduledReminderAt: 1708041600 (T+24h)
- status: "sent" | "reminded" | "done" | "not_yet" | "no_response"
- responseAt: Unix timestamp (optional)
- responseText: "Ho gaya" (optional)
- weatherCondition: {temperature: 28, rainfall: 0, windSpeed: 6}
- TTL: 1723507200 (180 days)
```

**Global Secondary Indexes**:

#### GSI-1: SessionIndex
- Partition Key: `sessionId` (String)
- Sort Key: `timestamp` (Number)
- Projection: ALL
- Purpose: Retrieve all messages in a conversation session (Note: May not be needed if Bedrock Agent manages sessions internally)

#### GSI-2: StatusIndex (Sparse)
- Partition Key: `status` (String)
- Sort Key: `scheduledReminderAt` (Number)
- Projection: ALL
- Purpose: Query pending reminders for EventBridge Scheduler
- Sparse Index: Only items with `status` attribute are indexed

**DynamoDB Streams**: Enable for real-time response detection (DONE/NOT YET keywords)

**Cost Optimization**:
- On-Demand pricing: Pay per request (no provisioned capacity)
- TTL: Automatic data expiration to reduce storage (MSG: 90d, NUDGE: 180d)
- Sparse indexes: Only index necessary attributes

### 4.5 Behavioral Nudge Engine (EventBridge Scheduler Pattern)

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
  T+24h: Triggers Reminder Lambda → checks DynamoDB status → if not DONE, sends first reminder
  T+48h: Triggers Reminder Lambda → checks DynamoDB status → if not DONE, sends second reminder
  T+72h: Triggers Timeout Lambda → marks nudge as "no_response" in DynamoDB

Real-time Response Detection (separate flow):
  DynamoDB Streams → response-detector Lambda → if DONE keyword matched, updates nudge status, deletes pending Scheduler records
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
    
    # T+72h timeout
    scheduler.create_schedule(
        Name=f'{nudge_id}-timeout',
        ScheduleExpression=f'at({calculate_time(72, "hours")})',
        Target={
            'Arn': 'arn:aws:lambda:REGION:ACCOUNT:function:timeout-handler',
            'Input': json.dumps({'nudgeId': nudge_id, 'userId': user_id})
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
                    handle_nudge_response(message, status='done' if is_done else 'not_yet')
                    
                    if is_done:
                        # Delete pending EventBridge Scheduler records
                        delete_pending_schedules(message['userId'])
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

**Performance Target**: Voice round-trip ≤ 10 seconds

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
- API Gateway resource policy (IP whitelist for Twilio/Meta)

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
- ModelLatency p95 > 10 seconds

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
| DynamoDB | 50M read units | 25M free | ~$12.50 |
| DynamoDB | 10M write units | 25M free | $0 |
| S3 Storage | 5 GB | 5 GB free | $0 |
| S3 Requests | 50,000 PUT | 2,000 free | ~$0.24 |
| OpenSearch Serverless | 1 OCU (indexing + search) | Pay-as-you-go | ~$20 |
| Bedrock (Claude 3 Sonnet) | 5M tokens | Pay-as-you-go | ~$15 |
| Transcribe | 30,000 minutes | 60 min free | ~$2.40 |
| Polly | 30,000 characters | 5M free | $0 |
| Step Functions | 10,000 transitions | 4,000 free | ~$0.15 |
| EventBridge Scheduler | 8,000 schedules | Free | $0 |
| CloudWatch Logs | 3 GB | 5 GB free | $0 |
| **Total** | | | **~$50/month** |

**Note**: OpenSearch Serverless is the primary cost driver (~40% of total cost). Bedrock is second (~30%). DynamoDB overage is third (~25%).

**Cost Optimization Strategies**:
- Consider Aurora Serverless v2 as vector store alternative (lower minimum cost)
- Implement response caching for common queries (reduce Bedrock calls)
- Batch DynamoDB writes where possible
- Use S3 lifecycle policies aggressively
- Optimize Bedrock prompts to reduce tokens
- Monitor and alert on cost thresholds ($50, $75, $100)

### 8.2 Scaling Projections (10,000 farmers - Post-MVP)

**Estimated Monthly Cost**: ~$250

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
- [ ] FAO PDF upload and Bedrock KB index
- [ ] Configure Bedrock Guardrails (banned pesticides, KVK escalation)
- [ ] Test Bedrock responses in Hindi, Marathi, Telugu from English source docs
- [ ] Implement 20 golden questions for RAG quality testing

**Acceptance**:
- Table created, PutItem/Query works
- S3 `en/` contains manuals; KB passes 20 golden questions
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
- Voice round-trip completes <10s
- Cotton pest identified correctly from test image within 15s
- Failed processing sends apology message in user's dialect
- Guardrail tests achieve 100% refusal rate

### Week 4: Demo Polish + Article

**Tasks**:
- [ ] CloudWatch Dashboard (Completion Rate metric, DLQ depth, latency)
- [ ] End-to-end integration tests for Aurangabad demo scenario
- [ ] Run guardrail test suite (20 scenarios) and RAG golden questions
- [ ] Performance testing (p95 latency with 10 concurrent users)
- [ ] End-to-End Demo Video (Aurangabad Farmer scenario)
- [ ] Article publication on AWS Builder Center (#aideas-2025, #EMEA tags)
- [ ] Cost audit: verify actual spend vs. $50/month estimate

**Acceptance**:
- Dashboard shows Completion Rate metric, DLQ depth, latency
- "Aurangabad Farmer" scenario recorded without manual intervention
- All tests pass with required thresholds
- Article submitted before March 13 deadline
- Actual cost ≤ $60/month

**Note**: Confirm Builder Center article submission deadline aligns with March 13 competition deadline. If the article is a competition requirement, prioritize it early in Week 4.

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
- 95% of voice round-trip within 10 seconds
- 99% uptime during business hours (6 AM - 10 PM IST)
- Zero security vulnerabilities in code scans
- <$60 total AWS costs during MVP phase

**User Metrics**:
- 80% of farmers complete onboarding
- 60% response rate to behavioral nudges (DONE or NOT YET)
- 40% "DONE" completion rate for nudges
- 90% RAG accuracy on golden questions across all three dialects

**Competition Metrics**:
- Working demo for judges (Aurangabad Cotton Farmer scenario)
- All promised features functional (Tier 1 + Tier 2)
- Clear differentiation from reactive information systems
- Compelling "closed loop" demonstration with real-time dashboard

## 12. Post-MVP Roadmap

### Phase 2 (Month 2-3):
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
