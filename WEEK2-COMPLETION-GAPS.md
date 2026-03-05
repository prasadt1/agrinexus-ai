# Week 2 Completion Gaps Analysis

## Status Overview

| Component | Code Written | Template Defined | Deployed | Tested | Status |
|-----------|--------------|------------------|----------|--------|--------|
| WhatsApp Webhook | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| Message Processor | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| Onboarding Flow | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| Weather Poller | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| Nudge Sender | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| Reminder Sender | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| Response Detector | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| Step Functions | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| EventBridge Scheduler | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |
| DLQ Handler | ✅ | ✅ | ❌ | ❌ | **NOT DEPLOYED** |

## Critical Gaps (Blocking Demo)

### 1. ❌ WhatsApp Integration Not Live
**Status**: Code written, not deployed or configured

**What's Missing**:
- [ ] Deploy API Gateway + Webhook Lambda
- [ ] Get API Gateway endpoint URL
- [ ] Configure webhook in Meta for Developers dashboard
- [ ] Set verify token in Secrets Manager
- [ ] Test webhook verification (GET request)
- [ ] Test message reception (POST request)
- [ ] Verify signature validation works

**Blocker**: Cannot receive messages from WhatsApp until this is done

**Action Required**:
```bash
# 1. Deploy
sam build -t template-week2.yaml
sam deploy --guided

# 2. Get webhook URL
aws cloudformation describe-stacks \
  --stack-name agrinexus-week2 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
  --output text

# 3. Update secrets
aws secretsmanager update-secret \
  --secret-id agrinexus-whatsapp-dev \
  --secret-string '{
    "VERIFY_TOKEN": "agrinexus_verify_123",
    "ACCESS_TOKEN": "YOUR_META_ACCESS_TOKEN",
    "PHONE_NUMBER_ID": "YOUR_PHONE_NUMBER_ID",
    "WEBHOOK_SECRET": "YOUR_WEBHOOK_SECRET"
  }'

# 4. Configure in Meta dashboard
# Go to: https://developers.facebook.com/apps/
# Navigate to: WhatsApp > Configuration > Webhook
# Paste webhook URL and verify token
```

### 2. ❌ WhatsApp Message Templates Not Created
**Status**: Not created in Meta dashboard

**What's Missing**:
- [ ] Create nudge template in Meta WhatsApp Manager
- [ ] Get template approved by Meta
- [ ] Update code to use template name
- [ ] Test template sending

**Blocker**: Cannot send proactive nudges without approved templates

**Template Example**:
```
Name: spray_weather_nudge_hi
Category: UTILITY
Language: Hindi (hi)
Body: आज स्प्रे करने के लिए अच्छा मौसम है। हवा {{1}} km/h है और बारिश नहीं होगी। क्या आपने स्प्रे कर दिया?

कृपया "हो गया" भेजें जब आप स्प्रे कर लें।
```

**Action Required**:
1. Go to Meta Business Manager
2. Navigate to WhatsApp Manager > Message Templates
3. Create templates for each dialect (Hindi, Marathi, Telugu)
4. Submit for approval (takes 24-48 hours)
5. Update `src/nudge/sender.py` to use template names

### 3. ❌ WhatsApp API Integration Incomplete
**Status**: Stub functions only

**What's Missing in Code**:
```python
# src/processor/handler.py
def send_whatsapp_message(phone_number: str, message: str):
    """Send message via WhatsApp Business API"""
    # TODO: Implement WhatsApp API call
    print(f"Sending to {phone_number}: {message}")
```

**Needs Implementation**:
```python
def send_whatsapp_message(phone_number: str, message: str):
    """Send message via WhatsApp Business API"""
    secret_response = secrets.get_secret_value(SecretId='agrinexus-whatsapp-dev')
    creds = json.loads(secret_response['SecretString'])
    
    url = f"https://graph.facebook.com/v18.0/{creds['PHONE_NUMBER_ID']}/messages"
    headers = {
        'Authorization': f"Bearer {creds['ACCESS_TOKEN']}",
        'Content-Type': 'application/json'
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'text',
        'text': {'body': message}
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
```

**Files to Update**:
- `src/processor/handler.py` - Message responses
- `src/nudge/sender.py` - Nudge sending
- `src/nudge/reminder.py` - Reminder sending
- `src/dlq/handler.py` - Error messages

### 4. ❌ EventBridge Scheduler Not Fully Implemented
**Status**: Template defined, code incomplete

**What's Missing**:
- [ ] Scheduler role ARN passed to nudge sender
- [ ] Reminder Lambda ARN passed to scheduler
- [ ] Test schedule creation
- [ ] Test schedule deletion
- [ ] Verify reminders fire at T+24h

**Code Issues**:
```python
# src/nudge/sender.py - Line 67
def create_reminder_schedule(phone_number: str, nudge_id: str, hours_offset: int, dialect: str):
    """Create EventBridge Scheduler for reminder"""
    schedule_time = datetime.utcnow() + timedelta(hours=hours_offset)
    
    scheduler.create_schedule(
        Name=f'reminder-{nudge_id}-{hours_offset}h',
        ScheduleExpression=f'at({schedule_time.strftime("%Y-%m-%dT%H:%M:%S")})',
        Target={
            'Arn': os.environ['REMINDER_LAMBDA_ARN'],  # ❌ NOT SET IN TEMPLATE
            'RoleArn': os.environ['SCHEDULER_ROLE_ARN'],  # ❌ NOT SET IN TEMPLATE
            'Input': json.dumps({...})
        },
        FlexibleTimeWindow={'Mode': 'OFF'}
    )
```

**Template Fix Needed**:
```yaml
NudgeSender:
  Environment:
    Variables:
      REMINDER_LAMBDA_ARN: !GetAtt ReminderSender.Arn
      SCHEDULER_ROLE_ARN: !GetAtt SchedulerRole.Arn
```

### 5. ❌ DynamoDB Streams Not Wired
**Status**: Template defines event source, not deployed

**What's Missing**:
- [ ] Deploy ResponseDetector Lambda
- [ ] Verify stream trigger works
- [ ] Test keyword detection
- [ ] Test status update
- [ ] Test scheduler deletion

**Verification**:
```bash
# Check if stream is enabled
aws dynamodb describe-table \
  --table-name agrinexus-data \
  --query 'Table.StreamSpecification'

# Check if Lambda is subscribed
aws lambda list-event-source-mappings \
  --function-name agrinexus-response-detector-dev
```

### 6. ❌ No Closed-Loop Test
**Status**: Not tested end-to-end

**Test Scenario Needed**:
```
1. Create test user profile
   PK: USER#+919876543210
   SK: PROFILE
   location: Aurangabad
   crop: Cotton
   dialect: hi

2. Trigger weather poller
   → Should detect Aurangabad (mocked perfect weather)
   → Should trigger Step Functions

3. Verify nudge sent
   → Check DynamoDB for NUDGE# record
   → Check WhatsApp message sent
   → Check EventBridge Schedule created

4. Simulate "Ho gaya" response
   → Insert MSG# record in DynamoDB
   → Wait for Streams trigger
   → Verify nudge status = DONE
   → Verify schedule deleted

5. Check CloudWatch metrics
   → NudgesSent = 1
   → NudgesCompleted = 1
   → CompletionRate = 100%
```

## Template Issues

### Issue 1: Week 1 Resources Not Imported
```yaml
# Current (WRONG):
AgriNexusTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: agrinexus-data
    # ... (same as Week 1)
```

**Problem**: This tries to CREATE a new table, but Week 1 already created it!

**Fix**: Import from Week 1 stack or use existing table
```yaml
# Option 1: Reference existing table
Parameters:
  Week1StackName:
    Type: String
    Default: agrinexus-week1

Resources:
  # Import from Week 1
  AgriNexusTable:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub 'https://s3.amazonaws.com/${Week1StackName}/template.yaml'

# Option 2: Just use table name
Globals:
  Function:
    Environment:
      Variables:
        TABLE_NAME: agrinexus-data  # Assumes Week 1 deployed this
```

### Issue 2: Missing Environment Variables
```yaml
NudgeSender:
  Environment:
    Variables:
      # ❌ MISSING:
      # REMINDER_LAMBDA_ARN
      # SCHEDULER_ROLE_ARN
```

### Issue 3: SQS Queue Type
```yaml
MessageQueue:
  Type: AWS::SQS::Queue
  # ❌ Should be FIFO for message ordering
  Properties:
    QueueName: !Sub agrinexus-messages-${Environment}.fifo
    FifoQueue: true
    ContentBasedDeduplication: true
```

## Deployment Blockers

### Blocker 1: No Meta Credentials
- Need WhatsApp Business API account
- Need App Secret and Access Token
- Need Phone Number ID
- Need to create verify token

### Blocker 2: No Template Approval
- Templates take 24-48 hours for Meta approval
- Cannot send proactive messages without approved templates
- Need templates for all 3 dialects

### Blocker 3: Week 1 Not Deployed
- Week 2 depends on Week 1 resources
- Need DynamoDB table, Bedrock KB, Guardrails
- Need to deploy Week 1 first

## Action Plan (Priority Order)

### Phase 1: Deploy Foundation (1-2 hours)
1. ✅ Fix template to reference Week 1 resources
2. ✅ Add missing environment variables
3. ✅ Deploy Week 2 stack
4. ✅ Verify all Lambdas created
5. ✅ Get API Gateway webhook URL

### Phase 2: WhatsApp Setup (2-4 hours)
1. ❌ Create Meta for Developers account
2. ❌ Create WhatsApp Business API app
3. ❌ Get credentials (App Secret, Access Token, Phone Number ID)
4. ❌ Update Secrets Manager
5. ❌ Configure webhook in Meta dashboard
6. ❌ Test webhook verification
7. ❌ Create message templates (3 dialects)
8. ❌ Submit templates for approval (wait 24-48h)

### Phase 3: Code Completion (2-3 hours)
1. ❌ Implement `send_whatsapp_message()` in all files
2. ❌ Add `requests` to requirements.txt
3. ❌ Fix EventBridge Scheduler environment variables
4. ❌ Test scheduler creation/deletion
5. ❌ Redeploy with fixes

### Phase 4: Integration Testing (2-3 hours)
1. ❌ Create test user profile
2. ❌ Trigger weather poller manually
3. ❌ Verify nudge sent to WhatsApp
4. ❌ Send "Ho gaya" from phone
5. ❌ Verify status updated to DONE
6. ❌ Verify reminder cancelled
7. ❌ Check CloudWatch metrics

### Phase 5: Demo Preparation (1-2 hours)
1. ❌ Create demo script
2. ❌ Test full onboarding flow
3. ❌ Test nudge → reminder → completion
4. ❌ Prepare CloudWatch Dashboard
5. ❌ Document any issues

## Estimated Time to Complete

- **If Meta credentials ready**: 6-8 hours of work
- **If waiting for template approval**: +24-48 hours
- **If Week 1 not deployed**: +2-3 hours

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Template approval delayed | HIGH | MEDIUM | Start approval process immediately |
| WhatsApp API rate limits | MEDIUM | LOW | Use test numbers, limit frequency |
| EventBridge Scheduler issues | HIGH | MEDIUM | Test thoroughly, have fallback |
| DynamoDB Streams lag | LOW | LOW | Acceptable for demo |
| Cost overrun | MEDIUM | LOW | Monitor closely, use mocks |

## Next Immediate Steps

1. **Fix template.yaml** to properly reference Week 1 resources
2. **Add missing environment variables** for scheduler
3. **Implement WhatsApp API calls** in all handler files
4. **Deploy to test environment**
5. **Get Meta credentials** and configure webhook
6. **Create and submit message templates**
7. **Run closed-loop test**

## Success Criteria

Week 2 is complete when:
- [ ] Can send "Namaste" from phone and get onboarding flow
- [ ] Can complete onboarding and create profile
- [ ] Weather poller triggers nudge for Aurangabad users
- [ ] Nudge appears on WhatsApp
- [ ] Replying "Ho gaya" updates status to DONE
- [ ] Reminder is cancelled
- [ ] CloudWatch shows metrics: 1 sent, 1 completed, 100% rate
