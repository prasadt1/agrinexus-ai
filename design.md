# AgriNexus AI - Design Document

**Project**: AgriNexus AI - Behavioral AI Extension Agent  
**Competition**: AWS 10,000 AIdeas Competition (Social Impact Track)  
**Version**: 1.0  
**Date**: February 14, 2026  
**Status**: Design Phase

## 1. Design Overview

This document provides the detailed technical design for AgriNexus AI, translating the requirements into concrete implementation specifications. AgriNexus AI is a behavioral intervention engine designed to close the "last mile" gap in agricultural extension through proactive, weather-timed behavioral nudges with closed-loop accountability.

### 1.1 Design Principles

1. **Single Table Design**: Use DynamoDB single-table pattern to minimize costs and maximize query efficiency
2. **Event-Driven Architecture**: Leverage EventBridge Scheduler (not long-wait Step Functions) for asynchronous workflows
3. **Stateless Lambda Functions**: All compute is stateless with state persisted in DynamoDB
4. **Code-Switching Support**: Native handling of mixed-language inputs (Hinglish)
5. **Behavioral Closed Loop**: Track nudge → action → confirmation cycle with Nudge Completion Rate as primary metric

### 1.2 Technology Stack

- **Compute**: AWS Lambda (Python 3.11)
- **API Layer**: Amazon API Gateway (REST API)
- **AI/ML**: Amazon Bedrock (Claude 3 Sonnet for conversations + vision)
- **Voice**: Amazon Transcribe (speech-to-text) + Amazon Polly (text-to-speech)
- **Storage**: Amazon S3, DynamoDB (single table: `agrinexus-data`)
- **Orchestration**: AWS Step Functions (short-lived) + EventBridge Scheduler
- **Messaging**: Amazon SNS, Amazon Polly
- **Monitoring**: CloudWatch Logs, Metrics, Alarms
- **IaC**: AWS SAM (Serverless Application Model)

## 2. Data Model Design

### 2.1 DynamoDB Single Table Design

**Table Name**: `agrinexus-data`  
**Billing Mode**: On-Demand  
**Partition Key**: `PK` (String)  
**Sort Key**: `SK` (String)

**Design Rationale**: Single-table design reduces costs (one table vs. three), simplifies transactions, and enables efficient access patterns through composite keys.

### 2.2 Access Patterns

| Pattern | Description | Keys |
|---------|-------------|------|
| AP1 | Get user profile | PK=USER#<phone>, SK=PROFILE |
| AP2 | Get user conversations | PK=USER#<phone>, SK begins_with MSG# |
| AP3 | Get session messages | GSI: sessionId, timestamp |
| AP4 | Get user nudges | PK=USER#<phone>, SK begins_with NUDGE# |
| AP5 | Query nudges by region | PK=REGION#<region>, SK=NUDGE#<timestamp> |
| AP6 | Get pending reminders | GSI: status, scheduledReminderAt |

### 2.3 Entity Schemas

#### 2.3.1 User Profile Entity
```json
{
  "PK": "USER#+919876543210",
  "SK": "PROFILE",
  "entityType": "UserProfile",
  "userId": "+919876543210",
  "location": {
    "region": "Aurangabad District",
    "state": "Maharashtra",
    "country": "India"
  },
  "crops": ["cotton", "soybean"],
  "language": "hi",
  "dialect": "Marathi",
  "voicePreference": true,
  "consent": true,
  "consentedAt": 1707868800,
  "farmSize": 2.5,
  "farmSizeUnit": "acres",
  "registeredAt": 1707868800,
  "lastActive": 1707955200,
  "profileComplete": true,
  "onboardingStep": null,
  "metadata": {
    "source": "whatsapp",
    "referral": null
  }
}
```


#### 2.3.2 Conversation Message Entity
```json
{
  "PK": "USER#+919876543210",
  "SK": "MSG#1707955200#abc123",
  "entityType": "Message",
  "userId": "+919876543210",
  "messageId": "abc123",
  "timestamp": 1707955200,
  "direction": "inbound",
  "content": "Mere cotton mein pests hain, help karo",
  "messageType": "text",
  "language": "hi",
  "sessionId": "session-xyz789",
  "bedrockResponse": {
    "model": "claude-3-sonnet",
    "tokens": 450,
    "responseTime": 1234
  },
  "TTL": 1715731200
}
```

**TTL Calculation**: Current timestamp + 90 days (7776000 seconds)

#### 2.3.3 Nudge Entity (User View)
```json
{
  "PK": "USER#+919876543210",
  "SK": "NUDGE#1707955200#spray-pesticide",
  "entityType": "Nudge",
  "nudgeId": "2026-02-14-spray-pesticide-aurangabad",
  "userId": "+919876543210",
  "activity": "spray_pesticide",
  "activityLabel": "Spray pesticides",
  "sentAt": 1707955200,
  "scheduledReminderAt": 1708041600,
  "status": "sent",
  "responseAt": null,
  "responseText": null,
  "weatherCondition": {
    "temperature": 28,
    "rainfall": 0,
    "windSpeed": 6,
    "humidity": 55
  },
  "message": "Good weather for spraying! Low wind, no rain expected for 24 hours.",
  "TTL": 1723507200
}
```

#### 2.3.4 Nudge Entity (Region View)
```json
{
  "PK": "REGION#Aurangabad District",
  "SK": "NUDGE#1707955200#spray-pesticide",
  "GSI1PK": "REGION#Aurangabad District",
  "GSI1SK": "NUDGE#1707955200",
  "GSI2PK": "STATUS#pending",
  "GSI2SK": 1707955200,
  "entityType": "RegionalNudge",
  "nudgeId": "2026-02-14-spray-pesticide-aurangabad",
  "region": "Aurangabad District",
  "state": "Maharashtra",
  "activity": "spray_pesticide",
  "status": "pending",
  "scheduledReminderAt": 1707955200,
  "createdAt": 1707955200,
  "targetCrops": ["cotton", "soybean"],
  "farmerCount": 150,
  "weatherCondition": {
    "temperature": 28,
    "rainfall": 0,
    "windSpeed": 6
  },
  "ttl": 1723507200
}
```

### 2.4 Global Secondary Indexes

#### GSI1: Region/Activity Index
- **Partition Key**: `GSI1PK` (String) - Set to `REGION#{region}` for regional queries
- **Sort Key**: `GSI1SK` (String) - Set to `NUDGE#{timestamp}` or `ACTIVITY#{activity}`
- **Projection**: ALL
- **Purpose**: Query nudges by region for targeting farmers during weather-based nudge campaigns
- **Example**: Query all nudges for "Aurangabad District" in the last 7 days

#### GSI2: Status/Reminder Index
- **Partition Key**: `GSI2PK` (String) - Set to `STATUS#{status}` (e.g., "STATUS#pending")
- **Sort Key**: `GSI2SK` (Number) - Set to `scheduledReminderAt` timestamp
- **Projection**: ALL
- **Purpose**: Query pending reminders for EventBridge Scheduler workflow
- **Sparse Index**: Only items with GSI2PK attribute are indexed
- **Example**: Query all pending reminders scheduled before current time

**Note**: Using generic GSI1PK/GSI1SK and GSI2PK/GSI2SK attribute names follows single-table design best practices, allowing flexible overloading of indexes for multiple access patterns.
- **Purpose**: Query recent nudges by region for analytics

### 2.5 DynamoDB Operations

#### Write Operations
```python
# Create user profile
put_item(
    Item={
        'PK': f'USER#{phone_number}',
        'SK': 'PROFILE',
        'entityType': 'UserProfile',
        # ... other attributes
    }
)

# Store message
put_item(
    Item={
        'PK': f'USER#{phone_number}',
        'SK': f'MSG#{timestamp}#{message_id}',
        'entityType': 'Message',
        'TTL': timestamp + 7776000,  # 90 days
        # ... other attributes
    }
)

# Create nudge (write to both user and region views)
transact_write_items(
    TransactItems=[
        {
            'Put': {
                'Item': {
                    'PK': f'USER#{phone_number}',
                    'SK': f'NUDGE#{timestamp}#{activity}',
                    # ... user nudge attributes
                }
            }
        },
        {
            'Put': {
                'Item': {
                    'PK': f'REGION#{region}',
                    'SK': f'NUDGE#{timestamp}#{activity}',
                    # ... regional nudge attributes
                }
            }
        }
    ]
)
```

#### Read Operations
```python
# Get user profile
get_item(
    Key={
        'PK': f'USER#{phone_number}',
        'SK': 'PROFILE'
    }
)

# Get recent messages for session context
query(
    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
    ExpressionAttributeValues={
        ':pk': f'USER#{phone_number}',
        ':sk': 'MSG#'
    },
    ScanIndexForward=False,
    Limit=10
)

# Get pending reminders
query(
    IndexName='StatusIndex',
    KeyConditionExpression='status = :status AND scheduledReminderAt <= :now',
    ExpressionAttributeValues={
        ':status': 'sent',
        ':now': current_timestamp
    }
)
```

## 3. Component Design

### 3.1 WhatsApp Webhook Handler

**Lambda Function**: `webhook-handler`  
**Runtime**: Python 3.11  
**Memory**: 256 MB  
**Timeout**: 30 seconds

**Responsibilities**:
1. Validate WhatsApp webhook signature
2. Parse incoming message payload
3. Route to appropriate processor (conversation, vision, command)
4. Handle webhook verification (GET request)

**Input** (WhatsApp Webhook):
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "919876543210",
          "id": "wamid.abc123",
          "timestamp": "1707955200",
          "type": "text",
          "text": {
            "body": "Mere cotton mein kab spray karein?"
          }
        }]
      }
    }]
  }]
}
```

**Processing Logic**:
```python
def lambda_handler(event, context):
    # 1. Validate Meta X-Hub-Signature-256
    signature = event['headers']['X-Hub-Signature-256']
    if not validate_signature(event['body'], signature):
        return {'statusCode': 403, 'body': 'Invalid signature'}
    
    # 2. Parse message, extract wamid and phone
    body = json.loads(event['body'])
    message = extract_message(body)
    wamid = message['id']       # WhatsApp message ID (wamid.xxx)
    phone = message['from']
    
    # 3. Idempotency check: conditional DynamoDB put with wamid
    if is_duplicate(wamid):     # Check DynamoDB for existing wamid
        return {'statusCode': 200, 'body': 'Duplicate, already processed'}
    
    # 4. Mark as processing (PutItem with wamid and TTL 24h)
    mark_processing(wamid)
    
    # 5. Route to downstream Lambda (async invocation)
    profile = get_user_profile(phone)
    if not profile or not profile.get('profileComplete'):
        invoke_async('onboarding-handler', message)
    elif message['type'] == 'image':
        invoke_async('vision-processor', message)
    elif message['type'] == 'audio':
        invoke_async('voice-processor', message)
    elif is_command(message.get('text', '')):
        invoke_async('command-handler', message)
    else:
        invoke_async('conversation-processor', message)
    
    # Always return 200 to WhatsApp within 2 seconds
    return {'statusCode': 200, 'body': 'OK'}
```

### 3.2 Onboarding Handler

**Lambda Function**: `onboarding-handler`  
**Runtime**: Python 3.11  
**Memory**: 256 MB  
**Timeout**: 30 seconds

**State Machine** (Onboarding Flow):
```
START
  ↓
Check Profile → Exists & Complete? → Route to Conversation
  ↓ No
Determine Step (language, location, crops)
  ↓
Send Prompt
  ↓
Store Response
  ↓
Complete? → Yes → Send Confirmation
  ↓ No
Next Step
```

**Onboarding Steps**:
1. **Welcome + Dialect**: "Namaste! Main AgriNexus hoon. Aapki bhasha chunein / Select your language:" → WhatsApp Interactive Buttons: [Hindi] [Marathi] [Telugu]
2. **Location** (in selected dialect): "Aap kahan se hain? Apna district ya gaon ka naam batayein." → Validated against district lookup table
3. **Crop** (WhatsApp Interactive Buttons): [Kapas/Cotton] [Gehun/Wheat] [Chawal/Rice] [Soybean] [Other]
4. **Farm Size** (optional): "Kitne acre mein kheti karte hain? (SKIP bhejein agar nahi batana)"
5. **Consent**: "Hum aapko mausam ke hisaab se farming tips bhejenge. Aap kabhi bhi STOP bhejkar band kar sakte hain. Kya aap taiyaar hain? (HAAN/NAHI)"
6. **Confirmation**: Summary of stored info + "Koi bhi sawaal poochein!"

**Note**: Steps 2-6 must be delivered in the dialect selected in Step 1. Maintain onboarding prompt templates for all three languages.

**Profile State Tracking**:
```python
{
  "onboardingStep": "language",  # language, location, crops, farm_size, complete
  "profileComplete": False,
  "partialData": {
    "language": "hi",
    "location": None,
    "crops": None
  }
}
```

### 3.3 Conversation Processor (Bedrock Agent)

**Lambda Function**: `conversation-processor`  
**Runtime**: Python 3.11  
**Memory**: 512 MB  
**Timeout**: 60 seconds

**Responsibilities**:
1. Load conversation context from DynamoDB
2. Detect language and code-switching
3. Invoke Bedrock Agent with RAG
4. Apply guardrails
5. Store conversation in DynamoDB
6. Send response via WhatsApp

**Bedrock Agent Configuration**:
```python
bedrock_agent_config = {
    "agentId": "AGENT_ID",
    "agentAliasId": "ALIAS_ID",
    "sessionId": session_id,
    "inputText": user_message,
    "sessionState": {
        "sessionAttributes": {
            "language": user_language,
            "crops": ",".join(user_crops),
            "location": user_region
        }
    }
}
```

**Code-Switching Detection**:
```python
def detect_language(text):
    """
    Coarse script detection. Hindi and Marathi both use Devanagari,
    so script detection alone can't distinguish them. Rely on
    user's onboarding dialect preference + Bedrock's native detection.
    """
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))  # Hindi & Marathi
    has_telugu = bool(re.search(r'[\u0C00-\u0C7F]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))
    
    if has_telugu:
        return 'te', has_latin   # Telugu (or Telugu + English code-switch)
    elif has_devanagari and has_latin:
        return 'hi', True        # Hinglish code-switch (could be Hindi or Marathi)
    elif has_devanagari:
        return 'hi', False       # Pure Devanagari (Hindi or Marathi — Bedrock disambiguates)
    else:
        return 'en', False       # English fallback
```

**Bedrock Agent Prompt** (System Instructions):
```
You are an agricultural extension agent helping smallholder farmers. 

LANGUAGE HANDLING:
- Respond in the farmer's preferred language (Hindi, Marathi, or Telugu as stored in their profile)
- Use the farmer's vocabulary level
- Translate technical terms into local equivalents
- Handle code-switching naturally (e.g., Hinglish)
- Maintain a conversational, supportive tone

KNOWLEDGE BASE:
- Ground all advice in the FAO agricultural manuals provided (English sources)
- If information is not in the knowledge base, say so clearly and direct to local KVK
- Provide practical, actionable advice suitable for smallholder farmers
- Include simplified source citations (e.g., "Source: FAO Cotton Guide, Section 3")

SAFETY GUARDRAILS:
- Block 100% of requests for banned pesticides (Paraquat, Endosulfan, etc.)
- Include disclaimers when providing pesticide dosage: "Always read product labels"
- Escalate to KVK for: severe infestations, unknown diseases, livestock health, human health
- Do NOT recommend specific pesticide brands
- Refuse medical advice for humans or animals

CONTEXT:
- Farmer location: {location}
- Crops grown: {crops}
- Current season: {season}

RESPONSE FORMAT:
- Keep responses concise (2-3 sentences for simple questions)
- Use bullet points for multi-step instructions
- Include timing information when relevant
```

**Processing Flow**:
```python
def process_conversation(message, user_profile):
    # 1. Load session context
    session_id = get_or_create_session(user_profile['userId'])
    context_messages = get_recent_messages(user_profile['userId'], limit=10)
    
    # 2. Detect language
    language, is_code_switched = detect_language(message['text'])
    
    # 3. Invoke Bedrock Agent
    response = bedrock_agent.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=ALIAS_ID,
        sessionId=session_id,
        inputText=message['text'],
        sessionState={
            'sessionAttributes': {
                'language': language,
                'code_switched': str(is_code_switched),
                'crops': ','.join(user_profile['crops']),
                'location': user_profile['location']['region'],
                'state': user_profile['location']['state']
            }
        }
    )
    
    # 4. Extract response text
    response_text = extract_response_text(response)
    
    # 5. Store conversation
    store_message(user_profile['userId'], message, 'inbound', session_id)
    store_message(user_profile['userId'], response_text, 'outbound', session_id)
    
    # 6. Send via WhatsApp
    send_whatsapp_message(user_profile['userId'], response_text)
    
    return response_text
```

### 3.4 Vision Processor (Claude 3 Vision)

**Lambda Function**: `vision-processor`  
**Runtime**: Python 3.11  
**Memory**: 1024 MB  
**Timeout**: 60 seconds

**Responsibilities**:
1. Download image from WhatsApp
2. Upload to S3 (temporary)
3. Invoke Claude 3 Vision via Bedrock
4. Parse diagnosis
5. Delete image from S3
6. Send diagnosis via WhatsApp

**Processing Flow**:
```python
def process_image(message, user_profile):
    # 1. Download image from WhatsApp
    image_url = message['image']['url']
    image_data = download_whatsapp_media(image_url)
    
    # 2. Upload to S3 temporarily
    s3_key = f"temp/{user_profile['userId']}/{message['timestamp']}.jpg"
    s3.put_object(Bucket=TEMP_BUCKET, Key=s3_key, Body=image_data)
    
    # 3. Invoke Claude 3 Vision
    response = bedrock_runtime.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.b64encode(image_data).decode()
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""Analyze this crop image for a farmer growing {', '.join(user_profile['crops'])} in {user_profile['location']['state']}, India.

Identify:
1. Pest or disease (if present)
2. Severity (low/medium/high)
3. Recommended actions
4. Confidence level

Respond in {user_profile['language']} language.
Format: Clear, actionable advice for a smallholder farmer."""
                    }
                ]
            }]
        })
    )
    
    # 4. Parse response
    diagnosis = parse_vision_response(response)
    
    # 5. Delete image
    s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
    
    # 6. Send diagnosis
    send_whatsapp_message(user_profile['userId'], diagnosis)
    
    return diagnosis
```

**Vision Response Format**:
```
Pest Identified: Fall Armyworm (Spodoptera frugiperda)
Severity: Medium
Confidence: 85%

Recommended Actions:
1. Apply neem-based pesticide early morning
2. Remove affected leaves
3. Monitor daily for 1 week

Timing: Spray within 24 hours for best results.
```

## 4. Behavioral Nudge Engine Design

### 4.1 Step Functions State Machine (Short-Lived with EventBridge Scheduler)

**State Machine Name**: `NudgeFlow`  
**Type**: Standard Workflow (short-lived, completes in seconds)  
**Execution Role**: `StepFunctionsExecutionRole`

**Architecture Change**: Replace long Wait states (24h + 72h) with EventBridge Scheduler pattern to avoid keeping executions alive for ~4 days. At scale, long-wait states burn through state transitions and concurrent execution limits.

**Complete Amazon States Language (ASL) Definition**:
```json
{
  "Comment": "AgriNexus Behavioral Nudge Workflow (Short-Lived with EventBridge Scheduler)",
  "StartAt": "PollWeatherData",
  "States": {
    "PollWeatherData": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:weather-poller",
        "Payload": {
          "regions.$": "$.regions"
        }
      },
      "ResultPath": "$.weatherData",
      "Next": "EvaluateConditions",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandleWeatherError"
        }
      ]
    },
    
    "EvaluateConditions": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.weatherData.Payload.weatherFavorable",
          "BooleanEquals": true,
          "Next": "QueryFarmers"
        },
        {
          "Variable": "$.weatherData.Payload.weatherFavorable",
          "BooleanEquals": false,
          "Next": "NoActionNeeded"
        }
      ],
      "Default": "NoActionNeeded"
    },
    
    "QueryFarmers": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:query-farmers",
        "Payload": {
          "region.$": "$.weatherData.Payload.region",
          "activity.$": "$.weatherData.Payload.recommendedActivity",
          "targetCrops.$": "$.weatherData.Payload.targetCrops"
        }
      },
      "ResultPath": "$.farmers",
      "Next": "CheckFarmerCount"
    },
    
    "CheckFarmerCount": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.farmers.Payload.count",
          "NumericGreaterThan": 0,
          "Next": "SendNudges"
        }
      ],
      "Default": "NoFarmersFound"
    },
    
    "SendNudges": {
      "Type": "Map",
      "ItemsPath": "$.farmers.Payload.farmers",
      "MaxConcurrency": 10,
      "ResultPath": "$.nudgeResults",
      "Iterator": {
        "StartAt": "SendIndividualNudge",
        "States": {
          "SendIndividualNudge": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
              "FunctionName": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:send-nudge",
              "Payload": {
                "farmer.$": "$",
                "activity.$": "$.activity",
                "weatherCondition.$": "$.weatherCondition",
                "message.$": "$.message"
              }
            },
            "ResultPath": "$.nudgeResult",
            "End": true,
            "Retry": [
              {
                "ErrorEquals": ["States.TaskFailed"],
                "IntervalSeconds": 5,
                "MaxAttempts": 2,
                "BackoffRate": 2
              }
            ]
          }
        }
      },
      "Next": "CreateSchedulerRecords"
    },
    
    "CreateSchedulerRecords": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:create-scheduler-records",
        "Payload": {
          "nudgeResults.$": "$.nudgeResults"
        }
      },
      "ResultPath": "$.schedulerRecords",
      "Comment": "Creates EventBridge Scheduler records for T+24h, T+48h, T+72h reminders",
      "End": true
    },
    
    "NoActionNeeded": {
      "Type": "Pass",
      "Result": {
        "message": "Weather conditions not favorable for nudges"
      },
      "End": true
    },
    
    "NoFarmersFound": {
      "Type": "Pass",
      "Result": {
        "message": "No farmers found matching criteria"
      },
      "End": true
    },
    
    "HandleWeatherError": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:handle-error",
        "Payload": {
          "error.$": "$.error",
          "context": "weather-polling"
        }
      },
      "End": true
    }
  }
}
```

### 4.2 EventBridge Scheduler Pattern

**Implementation**: Replace Step Functions Wait states with EventBridge Scheduler one-time schedules.

**create-scheduler-records Lambda**:
```python
import boto3
import json
from datetime import datetime, timedelta

scheduler = boto3.client('scheduler')

def lambda_handler(event, context):
    """
    Creates EventBridge Scheduler records for each nudge sent.
    Schedules: T+24h (first reminder), T+48h (second reminder), T+72h (timeout)
    """
    nudge_results = event['nudgeResults']
    
    for result in nudge_results:
        nudge_id = result['nudgeResult']['Payload']['nudgeId']
        user_id = result['nudgeResult']['Payload']['userId']
        language = result['nudgeResult']['Payload']['language']
        
        # T+24h reminder
        create_schedule(
            name=f'{nudge_id}-reminder-24h',
            time_offset_hours=24,
            target_function='reminder-handler',
            payload={'nudgeId': nudge_id, 'userId': user_id, 'reminderType': '24h', 'language': language}
        )
        
        # T+48h reminder
        create_schedule(
            name=f'{nudge_id}-reminder-48h',
            time_offset_hours=48,
            target_function='reminder-handler',
            payload={'nudgeId': nudge_id, 'userId': user_id, 'reminderType': '48h', 'language': language}
        )
        
        # T+72h timeout
        create_schedule(
            name=f'{nudge_id}-timeout',
            time_offset_hours=72,
            target_function='timeout-handler',
            payload={'nudgeId': nudge_id, 'userId': user_id}
        )
    
    return {'statusCode': 200, 'schedulesCreated': len(nudge_results) * 3}

def create_schedule(name, time_offset_hours, target_function, payload):
    """Create a one-time EventBridge Scheduler schedule"""
    schedule_time = datetime.utcnow() + timedelta(hours=time_offset_hours)
    
    scheduler.create_schedule(
        Name=name,
        ScheduleExpression=f'at({schedule_time.strftime("%Y-%m-%dT%H:%M:%S")})',
        Target={
            'Arn': f'arn:aws:lambda:{boto3.session.Session().region_name}:{boto3.client("sts").get_caller_identity()["Account"]}:function:{target_function}',
            'RoleArn': 'arn:aws:iam::ACCOUNT:role/EventBridgeSchedulerRole',
            'Input': json.dumps(payload)
        },
        FlexibleTimeWindow={'Mode': 'OFF'},
        State='ENABLED'
    )
```

**reminder-handler Lambda**:
```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agrinexus-data')

def lambda_handler(event, context):
    """
    Triggered by EventBridge Scheduler at T+24h or T+48h.
    Checks nudge status in DynamoDB. If not DONE, sends reminder.
    """
    nudge_id = event['nudgeId']
    user_id = event['userId']
    reminder_type = event['reminderType']
    language = event['language']
    
    # Check current nudge status
    response = table.get_item(
        Key={
            'PK': f'USER#{user_id}',
            'SK': f'NUDGE#{nudge_id}'
        }
    )
    
    if 'Item' not in response:
        return {'statusCode': 404, 'message': 'Nudge not found'}
    
    nudge = response['Item']
    
    # If already marked DONE, delete remaining schedules and exit
    if nudge.get('status') == 'done':
        delete_pending_schedules(nudge_id)
        return {'statusCode': 200, 'message': 'Already completed, schedules deleted'}
    
    # Send reminder in user's language
    reminder_messages = {
        'hi': {
            '24h': "Kya aapne spray kar liya? DONE ya NOT YET bhejein.",
            '48h': "Yaad dilana: Spray karna baaki hai? DONE ya NOT YET bhejein."
        },
        'mr': {
            '24h': "Tumhi spray kela ka? DONE kiva NOT YET pathva.",
            '48h': "Aathvan: Spray karna baaki aahe ka? DONE kiva NOT YET pathva."
        },
        'te': {
            '24h': "Miru spray chesara? DONE leda NOT YET pampandi.",
            '48h': "Gurthu cheyandi: Spray cheyadam migilipoinda? DONE leda NOT YET pampandi."
        }
    }
    
    message = reminder_messages.get(language, {}).get(reminder_type, "Did you complete the task? Reply DONE or NOT YET.")
    
    send_whatsapp_message(user_id, message)
    
    # Update status to 'reminded'
    table.update_item(
        Key={'PK': f'USER#{user_id}', 'SK': f'NUDGE#{nudge_id}'},
        UpdateExpression='SET #status = :status, lastReminderAt = :now',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': 'reminded', ':now': int(datetime.utcnow().timestamp())}
    )
    
    return {'statusCode': 200, 'message': f'Reminder sent ({reminder_type})'}

def delete_pending_schedules(nudge_id):
    """Delete remaining EventBridge Scheduler schedules for this nudge"""
    scheduler = boto3.client('scheduler')
    
    for schedule_suffix in ['reminder-24h', 'reminder-48h', 'timeout']:
        try:
            scheduler.delete_schedule(Name=f'{nudge_id}-{schedule_suffix}')
        except scheduler.exceptions.ResourceNotFoundException:
            pass  # Already deleted or doesn't exist
```

**timeout-handler Lambda**:
```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agrinexus-data')

def lambda_handler(event, context):
    """
    Triggered by EventBridge Scheduler at T+72h.
    Marks nudge as 'no_response' if still not completed.
    """
    nudge_id = event['nudgeId']
    user_id = event['userId']
    
    # Check current status
    response = table.get_item(
        Key={
            'PK': f'USER#{user_id}',
            'SK': f'NUDGE#{nudge_id}'
        }
    )
    
    if 'Item' not in response:
        return {'statusCode': 404, 'message': 'Nudge not found'}
    
    nudge = response['Item']
    
    # If already DONE, just exit
    if nudge.get('status') == 'done':
        return {'statusCode': 200, 'message': 'Already completed'}
    
    # Mark as no_response
    table.update_item(
        Key={'PK': f'USER#{user_id}', 'SK': f'NUDGE#{nudge_id}'},
        UpdateExpression='SET #status = :status, timeoutAt = :now',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': 'no_response', ':now': int(datetime.utcnow().timestamp())}
    )
    
    return {'statusCode': 200, 'message': 'Marked as no_response'}
```


### 4.3 Response Detection Logic (DynamoDB Streams with Pre-Filter)

**Lambda Function**: `response-detector`  
**Trigger**: DynamoDB Stream on `agrinexus-data` table

**Purpose**: Detect "DONE" or "NOT YET" responses in real-time and update nudge status. Pre-filter to avoid querying for pending nudges on every inbound message.

**Processing Logic**:
```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agrinexus-data')
scheduler = boto3.client('scheduler')

# Keywords across Hindi, Marathi, Telugu, and English
DONE_KEYWORDS = {
    'done', 'finished', 'completed',           # English
    'ho gaya', 'kar diya', 'kar liya',          # Hindi
    'zhala', 'kela',                             # Marathi
    'ayyindi', 'chesanu',                        # Telugu
}

NOT_YET_KEYWORDS = {
    'not yet', 'later',                          # English
    'abhi nahi', 'baad mein', 'nahi kiya',       # Hindi
    'nahi zhala', 'ajun nahi',                    # Marathi
    'inkaa ledu', 'ledu', 'cheyaledhu',          # Telugu
}

ALL_NUDGE_KEYWORDS = DONE_KEYWORDS | NOT_YET_KEYWORDS

def lambda_handler(event, context):
    for record in event['Records']:
        if record['eventName'] != 'INSERT':
            continue
        
        message = deserialize(record['dynamodb']['NewImage'])
        
        if message.get('entityType') != 'Message' or message.get('direction') != 'inbound':
            continue
        
        text_lower = message['content'].lower().strip()
        
        # Pre-filter: only check for pending nudges if keywords match
        if any(kw in text_lower for kw in ALL_NUDGE_KEYWORDS):
            is_done = any(kw in text_lower for kw in DONE_KEYWORDS)
            handle_nudge_response(message, status='done' if is_done else 'not_yet')

def handle_nudge_response(message, status):
    """Handle DONE or NOT YET response"""
    user_id = message['userId']
    
    # Find most recent pending nudge
    nudge = get_latest_pending_nudge(user_id)
    
    if not nudge:
        return  # No pending nudge found
    
    nudge_id = nudge['nudgeId']
    
    # Update nudge status
    table.update_item(
        Key={'PK': f'USER#{user_id}', 'SK': f'NUDGE#{nudge_id}'},
        UpdateExpression='SET #status = :status, responseAt = :now, responseText = :text',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': status,
            ':now': int(datetime.utcnow().timestamp()),
            ':text': message['content']
        }
    )
    
    if status == 'done':
        # Delete pending EventBridge Scheduler records
        delete_pending_schedules(nudge_id)
        
        # Send congratulations in user's language
        language = nudge.get('language', 'hi')
        congrats_messages = {
            'hi': "Bahut badhiya! 🎉 Aapki mehnat se fasal ko fayda hoga.",
            'mr': "Khup chhan! 🎉 Tumchya mehnatimule pikala faayda hoil.",
            'te': "Chala bagundi! 🎉 Mee koshika valla pantalu labhistayi."
        }
        send_whatsapp_message(user_id, congrats_messages.get(language, "Great work! 🎉"))
        
        # Emit CloudWatch metric
        emit_metric('NudgesCompleted', 1)
    else:
        # Send encouraging message
        language = nudge.get('language', 'hi')
        encourage_messages = {
            'hi': "Koi baat nahi! Jab time mile tab kar lena. Madad chahiye?",
            'mr': "Harak nahi! Vela milala tar kara. Madatichi garaj aahe ka?",
            'te': "Parledu! Samayam dorikite cheyandi. Sahayam kavala?"
        }
        send_whatsapp_message(user_id, encourage_messages.get(language, "No worries! Complete when you can."))

def get_latest_pending_nudge(user_id):
    """Query for most recent nudge with status 'sent' or 'reminded'"""
    response = table.query(
        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
        FilterExpression='#status IN (:sent, :reminded)',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':pk': f'USER#{user_id}',
            ':sk': 'NUDGE#',
            ':sent': 'sent',
            ':reminded': 'reminded'
        },
        ScanIndexForward=False,
        Limit=1
    )
    
    return response['Items'][0] if response['Items'] else None

def delete_pending_schedules(nudge_id):
    """Delete remaining EventBridge Scheduler schedules"""
    for schedule_suffix in ['reminder-24h', 'reminder-48h', 'timeout']:
        try:
            scheduler.delete_schedule(Name=f'{nudge_id}-{schedule_suffix}')
        except scheduler.exceptions.ResourceNotFoundException:
            pass

def deserialize(dynamodb_item):
    """Convert DynamoDB Stream format to Python dict"""
    from boto3.dynamodb.types import TypeDeserializer
    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in dynamodb_item.items()}
```

### 4.4 Dead Letter Queue (DLQ) Handler

**Clarification**: The DLQ catches failures in downstream Lambdas (conversation-processor, vision-processor, voice-processor, onboarding-handler) — NOT the webhook handler itself. The webhook handler always returns 200 to WhatsApp; async failures in downstream processing are caught by DLQ.

**Implementation**:
- Configure SQS DLQ on each downstream Lambda's async invocation configuration
- `dlq-handler` Lambda triggers on DLQ messages
- `dlq-handler` reads the user's dialect preference from DynamoDB and sends an apology in their language

**dlq-handler Lambda**:
```python
import boto3
import json

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('agrinexus-data')

def lambda_handler(event, context):
    """
    Processes failed messages from DLQ.
    Sends apology message in user's dialect.
    """
    for record in event['Records']:
        message_body = json.loads(record['body'])
        user_id = message_body.get('userId')
        
        if not user_id:
            continue
        
        # Get user's dialect preference
        profile = table.get_item(
            Key={'PK': f'USER#{user_id}', 'SK': 'PROFILE'}
        ).get('Item', {})
        
        language = profile.get('language', 'hi')
        
        # Send apology in user's language
        apology_messages = {
            'hi': "Maaf kijiyega, system mein takleef hai. Kripya thodi der baad koshish karein.",
            'mr': "Maaf kara, system madhe apatti aali aahe. Krupaya thoda velane prayatna kara.",
            'te': "Kshaminchandi, system lo samasya vachindi. Dayachesi konni sepu tarvata prayatninchandi."
        }
        
        send_whatsapp_message(user_id, apology_messages.get(language, "Sorry, system error. Please try again later."))
        
        # Log error for monitoring
        print(f"DLQ processed for user {user_id}: {message_body}")
    
    return {'statusCode': 200, 'processed': len(event['Records'])}
```

### 4.5 Bedrock Agent vs InvokeModel Clarification

**Two Model Invocation Patterns**:

1. **Conversations**: Use Bedrock Agent API (`invoke_agent`)
   - Agent manages RAG retrieval, guardrails, and session context natively
   - Maintains conversation history internally
   - Applies configured guardrails automatically
   - Returns responses with source citations

2. **Vision**: Use direct `invoke_model` API with Claude 3 Sonnet (multimodal)
   - Separate invocation from conversation flow
   - Separate 15s timeout
   - Separate cost tracking
   - Direct image analysis without RAG

**Session Truth**: Bedrock Agent manages conversation sessions internally. DynamoDB stores messages for analytics and nudge context only — not as the primary session store.

**Question**: Evaluate whether SessionIndex GSI is still needed if Bedrock Agent sessions are sufficient. For MVP, keep GSI for analytics queries but rely on Bedrock Agent for conversation continuity.

### 4.6 Knowledge Base Strategy

**Storage**: FAO documents in English only (not translated)

**Bedrock Agent Prompt**: "Respond in the farmer's preferred language (Hindi, Marathi, or Telugu as stored in their profile). Use the farmer's vocabulary level. Translate technical terms into local equivalents."

**Document Structure**: Prefer smaller, well-structured PDFs per topic (e.g., `cotton-pest-management.pdf`, `wheat-irrigation-timing.pdf`) over large monolithic documents

**Metadata per Document**:
- source URL
- publication date
- validation date
- locale applicability

**Quality Assurance**: Implement 20 "golden questions" as RAG quality acceptance tests (test across all three dialects)

**Golden Questions Examples**:
1. Hindi: "Cotton mein aphids ka control kaise karein?"
2. Marathi: "Kapasala pani kiti divas la dyave?"
3. Telugu: "Patti pantalu enappudu nataali?"
4. (Continue for 17 more questions covering cotton, wheat, rice, soybean)

**Acceptance Criteria**: ≥90% accuracy on factual crop data across all three dialects

### 4.7 Weather Polling Logic

**Lambda Function**: `weather-poller`  
**Trigger**: EventBridge (every 6 hours)

**Weather API**: OpenWeatherMap API (Free Tier: 1,000 calls/day)

**Processing Logic**:
```python
def lambda_handler(event, context):
    regions = get_active_regions()  # Query DynamoDB for regions with farmers
    
    results = []
    for region in regions:
        weather = fetch_weather(region['coordinates'])
        
        # Evaluate conditions for agricultural activities
        evaluation = evaluate_weather_conditions(weather, region)
        
        if evaluation['favorable']:
            results.append({
                'region': region['name'],
                'weatherFavorable': True,
                'recommendedActivity': evaluation['activity'],
                'targetCrops': evaluation['crops'],
                'weatherCondition': weather,
                'message': evaluation['message']
            })
    
    return {
        'weatherFavorable': len(results) > 0,
        'results': results
    }

def evaluate_weather_conditions(weather, region):
    """
    Evaluate if weather is favorable for specific activities
    """
    temp = weather['temperature']
    wind = weather['windSpeed']
    rain_forecast = weather['rainForecast24h']
    humidity = weather['humidity']
    
    # Pesticide spraying conditions
    if (wind < 10 and rain_forecast == 0 and 
        temp > 18 and temp < 35):
        return {
            'favorable': True,
            'activity': 'spray_pesticide',
            'crops': ['cotton', 'wheat', 'soybean'],
            'message': f"Perfect weather for spraying! Low wind ({wind}km/h), no rain expected."
        }
    
    # Fertilizer application
    if (rain_forecast > 0 and rain_forecast < 20 and 
        temp > 20 and temp < 32):
        return {
            'favorable': True,
            'activity': 'apply_fertilizer',
            'crops': ['wheat', 'rice', 'cotton'],
            'message': f"Good time to fertilize! Light rain expected to help absorption."
        }
    
    # Harvesting conditions
    if (rain_forecast == 0 and humidity < 70 and 
        temp > 22 and temp < 38):
        return {
            'favorable': True,
            'activity': 'harvest',
            'crops': ['wheat', 'cotton', 'soybean'],
            'message': f"Excellent harvesting weather! Dry conditions for next 24 hours."
        }
    
    return {'favorable': False}
```

### 4.8 Voice Processor (Transcribe + Polly)

**Lambda Function**: `voice-processor`  
**Runtime**: Python 3.11  
**Memory**: 1024 MB  
**Timeout**: 60 seconds

**Responsibilities**:
1. Download voice note from WhatsApp
2. Upload to S3 (temporary)
3. Invoke Amazon Transcribe
4. Check transcription confidence
5. Process via Bedrock Agent if confidence ≥ 0.5
6. Generate Polly audio response
7. Send audio via WhatsApp
8. Clean up temporary files

**Processing Flow**:
```python
import boto3
import base64
from datetime import datetime

s3 = boto3.client('s3')
transcribe = boto3.client('transcribe')
polly = boto3.client('polly')
bedrock_agent = boto3.client('bedrock-agent-runtime')

TEMP_BUCKET = 'agrinexus-temp-audio'
CONFIDENCE_THRESHOLD = 0.5

def lambda_handler(event, context):
    message = event['message']
    user_id = message['from']
    audio_url = message['audio']['url']
    
    # 1. Download audio from WhatsApp
    audio_data = download_whatsapp_media(audio_url)
    
    # 2. Upload to S3
    s3_key = f"voice/{user_id}/{message['timestamp']}.ogg"
    s3.put_object(Bucket=TEMP_BUCKET, Key=s3_key, Body=audio_data)
    
    # 3. Start transcription job
    job_name = f"transcribe-{user_id}-{message['timestamp']}"
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': f's3://{TEMP_BUCKET}/{s3_key}'},
        MediaFormat='ogg',
        LanguageCode='hi-IN',  # Hindi primary; verify Marathi/Telugu support
        Settings={
            'ShowAlternatives': True,
            'MaxAlternatives': 2
        }
    )
    
    # 4. Wait for transcription (polling with timeout)
    transcription_text, confidence = wait_for_transcription(job_name)
    
    # 5. Check confidence
    if confidence < CONFIDENCE_THRESHOLD:
        # Fallback to text prompt
        fallback_message = get_fallback_message(user_id)
        send_whatsapp_message(user_id, fallback_message)
        cleanup_temp_files(s3_key, job_name)
        return {'statusCode': 200, 'message': 'Low confidence, sent fallback'}
    
    # 6. Process via Bedrock Agent
    profile = get_user_profile(user_id)
    bedrock_response = bedrock_agent.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=ALIAS_ID,
        sessionId=f"session-{user_id}",
        inputText=transcription_text
    )
    
    response_text = extract_response_text(bedrock_response)
    
    # 7. Generate Polly audio
    polly_response = polly.synthesize_speech(
        Text=response_text,
        OutputFormat='mp3',
        VoiceId='Aditi',  # Hindi Neural voice
        Engine='neural',
        LanguageCode='hi-IN'
    )
    
    audio_stream = polly_response['AudioStream'].read()
    
    # 8. Upload audio to S3 and send via WhatsApp
    audio_s3_key = f"responses/{user_id}/{message['timestamp']}.mp3"
    s3.put_object(Bucket=TEMP_BUCKET, Key=audio_s3_key, Body=audio_stream)
    
    audio_url = s3.generate_presigned_url('get_object', 
        Params={'Bucket': TEMP_BUCKET, 'Key': audio_s3_key},
        ExpiresIn=3600)
    
    send_whatsapp_audio(user_id, audio_url)
    
    # 9. Cleanup
    cleanup_temp_files(s3_key, job_name, audio_s3_key)
    
    return {'statusCode': 200, 'message': 'Voice processed successfully'}

def wait_for_transcription(job_name, max_wait=30):
    """Poll transcription job status"""
    import time
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = response['TranscriptionJob']['TranscriptionJobStatus']
        
        if status == 'COMPLETED':
            transcript = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
            # Download and parse transcript JSON
            transcript_data = download_transcript(transcript)
            text = transcript_data['results']['transcripts'][0]['transcript']
            confidence = transcript_data['results']['items'][0]['alternatives'][0]['confidence']
            return text, float(confidence)
        elif status == 'FAILED':
            raise Exception('Transcription failed')
        
        time.sleep(2)
    
    raise Exception('Transcription timeout')

def get_fallback_message(user_id):
    """Get fallback message in user's language"""
    profile = get_user_profile(user_id)
    language = profile.get('language', 'hi')
    
    messages = {
        'hi': "Maaf kijiye, audio saaf nahi suna. Kripya phir se bhejein ya type karein.",
        'mr': "Maaf kara, audio spasht nahi aikala. Krupaya punha pathva kiva type kara.",
        'te': "Kshaminchandi, audio clear ga vinipinchaledhu. Dayachesi malli pampandi leda type cheyandi."
    }
    
    return messages.get(language, "Sorry, audio unclear. Please resend or type your question.")

def cleanup_temp_files(input_key, job_name, output_key=None):
    """Delete temporary files from S3 and Transcribe job"""
    s3.delete_object(Bucket=TEMP_BUCKET, Key=input_key)
    if output_key:
        s3.delete_object(Bucket=TEMP_BUCKET, Key=output_key)
    transcribe.delete_transcription_job(TranscriptionJobName=job_name)
```

**Performance Target**: Voice round-trip ≤ 10 seconds

**Note**: Verify Amazon Transcribe support for Marathi (`mr-IN`) and Telugu (`te-IN`). If unavailable, voice input falls back to Hindi-only for MVP; text input works for all three dialects.

## 5. API Design

### 5.1 API Gateway Configuration

**API Name**: `agrinexus-api`  
**Type**: REST API  
**Endpoint Type**: Regional

**Resources**:
```
/webhook
  POST - Receive WhatsApp messages
  GET - Webhook verification
```

**Integration**: Lambda Proxy Integration

**Security**:
- API Key: Not required (signature validation in Lambda)
- Resource Policy: IP whitelist for WhatsApp servers
- Throttling: 1000 requests/second, 5000 burst

### 5.2 WhatsApp Message Sending

**Method**: WhatsApp Business API via HTTP

**Endpoint**: `https://graph.facebook.com/v18.0/{phone_number_id}/messages`

**Request Format**:
```python
def send_whatsapp_message(to_number, message_text, message_type='text'):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'messaging_product': 'whatsapp',
        'to': to_number,
        'type': message_type,
        'text': {
            'body': message_text
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()
```

## 6. Security Design

### 6.1 Webhook Signature Validation

```python
import hmac
import hashlib

def validate_signature(payload, signature, secret):
    """
    Validate WhatsApp webhook signature
    """
    expected_signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Remove 'sha256=' prefix from signature
    provided_signature = signature.replace('sha256=', '')
    
    return hmac.compare_digest(expected_signature, provided_signature)
```

### 6.2 IAM Roles

**Lambda Execution Role**:
```yaml
LambdaExecutionRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Statement:
        - Effect: Allow
          Principal:
            Service: lambda.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    Policies:
      - PolicyName: DynamoDBAccess
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action:
                - dynamodb:GetItem
                - dynamodb:PutItem
                - dynamodb:Query
                - dynamodb:UpdateItem
              Resource:
                - !GetAtt AgriNexusTable.Arn
                - !Sub "${AgriNexusTable.Arn}/index/*"
      - PolicyName: BedrockAccess
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
                - bedrock:InvokeAgent
              Resource: "*"
      - PolicyName: S3Access
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action:
                - s3:GetObject
                - s3:PutObject
                - s3:DeleteObject
              Resource:
                - !Sub "${TempImagesBucket.Arn}/*"
```

### 6.3 Data Privacy

**PII Minimization**:
- Store only phone number (userId)
- No names, addresses, or sensitive personal data
- Location stored as region name (not precise GPS)

**Data Retention**:
- Conversations: 90 days (TTL)
- Nudges: 180 days (TTL)
- User profiles: Retained until deletion request

**GDPR Compliance**:
- Right to access: GET /profile endpoint
- Right to deletion: DELETE /profile endpoint (soft delete with 30-day grace period)
- Data portability: Export user data as JSON

## 7. Testing Strategy

### 7.1 Unit Tests

**Framework**: pytest

**Coverage Target**: 70%

**Test Cases**:
```python
# test_onboarding.py
def test_language_selection():
    response = onboarding_handler.process_step('language', '1')  # Hindi
    assert response['language'] == 'hi'
    assert response['next_step'] == 'location'

def test_incomplete_profile_resume():
    profile = {'onboardingStep': 'crops', 'language': 'hi'}
    response = onboarding_handler.resume(profile)
    assert 'Aap kya ugaate hain?' in response['message']

# test_conversation.py
def test_code_switching_detection():
    text = "Mere cotton mein pests hain"
    lang, is_mixed = detect_language(text)
    assert lang == 'hi'
    assert is_mixed == True

# test_nudge_engine.py
def test_weather_evaluation():
    weather = {'temperature': 28, 'windSpeed': 6, 'rainForecast24h': 0}
    result = evaluate_weather_conditions(weather, {})
    assert result['favorable'] == True
    assert result['activity'] == 'spray_pesticide'
```

### 7.2 Integration Tests

**Test Scenarios**:
1. End-to-end onboarding flow
2. Message → Bedrock → Response flow
3. Image upload → Vision analysis → Response
4. Weather poll → Nudge send → Reminder → Response detection
5. Step Functions execution with mock responses

### 7.3 Load Testing

**Tool**: Locust

**Scenarios**:
- 100 concurrent users sending messages
- 1000 messages/minute sustained load
- Burst traffic: 500 messages in 10 seconds

**Success Criteria**:
- 95th percentile latency < 5 seconds
- Error rate < 1%
- No Lambda throttling

## 8. Monitoring Design

### 8.1 CloudWatch Dashboards

**Dashboard**: AgriNexus-Operations

**Widgets**:
1. Message Volume (last 24 hours)
2. Response Time (p50, p95, p99)
3. Error Rate by Lambda function
4. Bedrock Token Usage
5. DynamoDB Consumed Capacity
6. Nudge Completion Rate
7. Cost Estimate (current month)

### 8.2 Alarms

```yaml
HighErrorRateAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: AgriNexus-HighErrorRate
    MetricName: Errors
    Namespace: AWS/Lambda
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 1
    Threshold: 10
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref AlertTopic

CostAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: AgriNexus-CostThreshold
    MetricName: EstimatedCharges
    Namespace: AWS/Billing
    Statistic: Maximum
    Period: 21600
    EvaluationPeriods: 1
    Threshold: 50
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref AlertTopic
```

## 9. Deployment Design

### 9.1 SAM Template Structure

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: python3.11
    Timeout: 30
    MemorySize: 256
    Environment:
      Variables:
        TABLE_NAME: !Ref AgriNexusTable
        TEMP_BUCKET: !Ref TempImagesBucket

Resources:
  # DynamoDB Table
  AgriNexusTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: agrinexus-data
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: PK
          AttributeType: S
        - AttributeName: SK
          AttributeType: S
        - AttributeName: sessionId
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: N
        - AttributeName: status
          AttributeType: S
        - AttributeName: scheduledReminderAt
          AttributeType: N
      KeySchema:
        - AttributeName: PK
          KeyType: HASH
        - AttributeName: SK
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: SessionIndex
          KeySchema:
            - AttributeName: sessionId
              KeyType: HASH
            - AttributeName: timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: StatusIndex
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: scheduledReminderAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        Enabled: true
        AttributeName: TTL
  
  # Lambda Functions
  WebhookHandler:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/webhook-handler/
      Handler: app.lambda_handler
      Events:
        WebhookPost:
          Type: Api
          Properties:
            Path: /webhook
            Method: post
            RestApiId: !Ref AgriNexusApi
  
  # Step Functions State Machine
  NudgeWorkflow:
    Type: AWS::Serverless::StateMachine
    Properties:
      DefinitionUri: statemachine/nudge-workflow.asl.json
      Role: !GetAtt StepFunctionsRole.Arn
      Events:
        ScheduledExecution:
          Type: Schedule
          Properties:
            Schedule: rate(6 hours)
```

### 9.2 Deployment Commands

```bash
# Build
sam build

# Deploy to dev
sam deploy --config-env dev --parameter-overrides Environment=dev

# Deploy to prod
sam deploy --config-env prod --parameter-overrides Environment=prod
```

## 10. Cost Optimization Strategies

1. **Response Caching**: Cache common Bedrock responses for 1 hour
2. **Batch Writes**: Batch DynamoDB writes where possible
3. **S3 Lifecycle**: Delete temp images after 24 hours
4. **Lambda Memory**: Right-size memory based on profiling
5. **DynamoDB On-Demand**: Use on-demand pricing initially, switch to provisioned if usage is predictable
6. **Bedrock Prompt Optimization**: Minimize token usage with concise prompts

---

**Design Status**: Complete  
**Next Phase**: Implementation (Tasks)  
**Review Date**: February 14, 2026
