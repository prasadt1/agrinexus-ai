# ADR 0007: EventBridge Scheduler vs Step Functions Wait States for Nudge Reminders

**Date:** 2026-04-15  
**Status:** Accepted  
**Deciders:** Development Team  

## Context

The behavioral nudge engine sends follow-up reminders at T+24h, T+48h, and T+72h after the initial nudge. We need a mechanism to schedule these delayed executions. Two AWS services can handle this:

1. **Step Functions Wait States** - Keep execution open, wait, then continue
2. **EventBridge Scheduler** - Schedule one-time Lambda invocations

## Problem

**How do we schedule T+24h, T+48h, T+72h reminders without keeping Step Functions executions running for 3 days?**

### Cost Comparison

#### Step Functions Wait State Approach
```json
{
  "Type": "Wait",
  "Seconds": 86400,  // 24 hours
  "Next": "SendReminder"
}
```

**Cost calculation (per nudge):**
- Step Functions: $25 per million state transitions
- 1 nudge = 8 state transitions (start → wait → remind → wait → remind → wait → expire → end)
- Cost per nudge: 8 × $0.000025 = **$0.0002**
- **BUT:** Execution stays open for 72 hours (3 days)
- Max execution time: 1 year (but not recommended for >1 day)

#### EventBridge Scheduler Approach
```python
scheduler.create_schedule(
    Name=f'reminder-{nudge_id}-24h',
    ScheduleExpression=f'at({time_24h_later})',
    Target={'Arn': reminder_lambda_arn}
)
```

**Cost calculation (per nudge):**
- EventBridge Scheduler: $1.00 per million invocations
- 1 nudge = 3 schedules (T+24h, T+48h, T+72h)
- Cost per nudge: 3 × $0.000001 = **$0.000003**
- Execution exits immediately (no long-running state)

### Cost at Scale

| Metric | Step Functions Wait | EventBridge Scheduler |
|--------|---------------------|----------------------|
| Cost per nudge | $0.0002 | $0.000003 |
| Cost per 1,000 nudges | $0.20 | $0.003 |
| Cost per 100,000 nudges | $20.00 | $0.30 |
| **Cost per 1M nudges** | **$200** | **$3** |

**EventBridge Scheduler is 67x cheaper at scale.**

## Decision

**Use EventBridge Scheduler for T+24h, T+48h, T+72h reminders. Step Functions only orchestrates the initial nudge send.**

### Architecture

```
Weather Poller → Step Functions (short-lived) → Nudge Sender Lambda
                                                        ↓
                                    Create 3 EventBridge Schedules:
                                    - T+24h → Reminder Lambda
                                    - T+48h → Reminder Lambda  
                                    - T+72h → Reminder Lambda (auto-expire)
                                                        ↓
                                            Response Detector (DynamoDB Streams)
                                                        ↓
                                            If "DONE" → Cancel remaining schedules
```

### Implementation

#### Nudge Sender Creates Schedules
```python
def create_reminder_schedule(phone_number: str, nudge_id: str, hours_offset: int):
    schedule_time = datetime.utcnow() + timedelta(hours=hours_offset)
    
    scheduler.create_schedule(
        Name=f'reminder-{nudge_id}-{hours_offset}h',
        ScheduleExpression=f'at({schedule_time.strftime("%Y-%m-%dT%H:%M:%S")})',
        Target={
            'Arn': os.environ['REMINDER_LAMBDA_ARN'],
            'RoleArn': os.environ['SCHEDULER_ROLE_ARN'],
            'Input': json.dumps({
                'phone_number': phone_number,
                'nudge_id': nudge_id,
                'reminder_type': f'T+{hours_offset}h'
            })
        },
        FlexibleTimeWindow={'Mode': 'OFF'}
    )

# Create all 3 schedules
create_reminder_schedule(phone_number, nudge_id, 24)
create_reminder_schedule(phone_number, nudge_id, 48)
create_reminder_schedule(phone_number, nudge_id, 72)  # Auto-expire
```

#### Response Detector Cancels Schedules
```python
def cancel_remaining_schedules(nudge_id: str):
    """Cancel T+48h and T+72h if farmer responds 'DONE' at T+24h"""
    for hours in [48, 72]:
        schedule_name = f'reminder-{nudge_id}-{hours}h'
        try:
            scheduler.delete_schedule(Name=schedule_name)
        except scheduler.exceptions.ResourceNotFoundException:
            pass  # Already executed or doesn't exist
```

#### Step Functions (Short-Lived)
```json
{
  "Comment": "Nudge workflow - exits immediately after sending",
  "StartAt": "QueryFarmers",
  "States": {
    "QueryFarmers": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:getItem",
      "Next": "SendNudge"
    },
    "SendNudge": {
      "Type": "Task",
      "Resource": "${NudgeSenderArn}",
      "End": true
    }
  }
}
```

**Execution time: <5 seconds** (vs 72 hours with Wait states)

## Consequences

### Positive
- ✅ **67x cheaper** - $3 vs $200 per million nudges
- ✅ **No long-running executions** - Step Functions exits in <5s
- ✅ **Cancellable** - Can delete schedules if farmer responds "DONE"
- ✅ **Scalable** - EventBridge Scheduler handles millions of schedules
- ✅ **Reliable** - One-time schedules, no execution timeout risk
- ✅ **Observable** - Each reminder is a separate Lambda invocation (easier to debug)

### Negative
- ⚠️ **More components** - EventBridge Scheduler + IAM role + delete logic
- ⚠️ **Schedule management** - Must track and delete schedules on "DONE"
- ⚠️ **No visual workflow** - Can't see T+24h/T+48h in Step Functions graph

### Neutral
- EventBridge Scheduler has 1-minute precision (sufficient for our use case)
- Schedules are one-time (deleted after execution)
- Max 1 million schedules per account (we're nowhere near this)

## Alternatives Considered

### 1. Step Functions Wait States (Rejected)
```json
{
  "Type": "Wait",
  "Seconds": 86400,
  "Next": "SendT24hReminder"
}
```

**Pros:**
- Visual workflow in Step Functions console
- Single orchestration (no external scheduler)
- Built-in error handling

**Cons:**
- **67x more expensive** ($200 vs $3 per million)
- Execution stays open for 72 hours (resource waste)
- Can't easily cancel mid-execution (need to track execution ARNs)
- Not recommended for >24 hour waits (AWS best practice)
- Risk of execution timeout (max 1 year, but not intended for days)

### 2. SQS Delay Queues (Rejected)
```python
sqs.send_message(
    QueueUrl=queue_url,
    MessageBody=json.dumps(reminder),
    DelaySeconds=86400  # Max 15 minutes!
)
```

**Pros:**
- Simple, familiar pattern
- Built-in retry logic

**Cons:**
- **Max delay: 15 minutes** (not 24 hours!)
- Would need custom delay mechanism (DynamoDB + polling)
- Can't cancel delayed messages
- Not designed for long delays

### 3. DynamoDB TTL + Streams (Rejected)
```python
# Set TTL for T+24h
table.put_item(Item={
    'PK': f'REMINDER#{nudge_id}',
    'ttl': int(time.time()) + 86400
})

# DynamoDB Streams triggers Lambda when TTL expires
```

**Pros:**
- No additional service (already using DynamoDB)
- Automatic cleanup

**Cons:**
- **TTL is not precise** (can take up to 48 hours to expire!)
- Can't cancel TTL items reliably
- Not designed for scheduled tasks
- Streams trigger is eventual consistency

### 4. CloudWatch Events (Legacy) (Rejected)
```python
events.put_rule(
    Name=f'reminder-{nudge_id}',
    ScheduleExpression=f'at({time})'
)
```

**Pros:**
- Similar to EventBridge Scheduler

**Cons:**
- **Legacy service** (EventBridge Scheduler is newer, better)
- More complex API (rules + targets vs single schedule)
- No one-time schedules (must delete rule after execution)
- EventBridge Scheduler is purpose-built for this use case

## Performance Characteristics

| Metric | Step Functions Wait | EventBridge Scheduler |
|--------|---------------------|----------------------|
| Precision | Exact (second-level) | ±1 minute |
| Max delay | 1 year | 1 year |
| Cancellation | Complex (track ARN) | Simple (delete schedule) |
| Execution time | 72 hours | <1 second |
| Cost per 1M | $200 | $3 |
| Observability | Single execution | 3 separate invocations |

## Real-World Example

**Scenario:** 10,000 farmers receive nudges per day

### Step Functions Wait Approach
- 10,000 executions × 8 state transitions = 80,000 transitions/day
- Cost: 80,000 × $0.000025 = **$2/day = $730/year**
- 10,000 executions running for 72 hours each (resource waste)

### EventBridge Scheduler Approach
- 10,000 nudges × 3 schedules = 30,000 schedules/day
- Cost: 30,000 × $0.000001 = **$0.03/day = $11/year**
- Step Functions executions exit in <5 seconds

**Savings: $719/year (98.5% reduction)**

## Demo Tier Behavior

For `demo_tier: public` users, we skip T+24h/T+48h reminders:

```python
is_demo_user = profile.get('demo_tier') == 'public'

if is_demo_user:
    print(f"Demo user - sending one nudge only, no follow-ups")
    # Don't create EventBridge schedules
else:
    # Production users get full closed-loop
    create_reminder_schedule(phone_number, nudge_id, 24)
    create_reminder_schedule(phone_number, nudge_id, 48)
    create_reminder_schedule(phone_number, nudge_id, 72)
```

This further reduces costs for public demo users.

## Related Decisions
- ADR 0003: WhatsApp Integration Architecture
- ADR 0008: S3 Vectors vs OpenSearch for Knowledge Base

## References
- [EventBridge Scheduler Pricing](https://aws.amazon.com/eventbridge/scheduler/pricing/)
- [Step Functions Pricing](https://aws.amazon.com/step-functions/pricing/)
- [AWS Best Practices: Long-Running Workflows](https://docs.aws.amazon.com/step-functions/latest/dg/bp-long-running.html)
- [EventBridge Scheduler vs CloudWatch Events](https://aws.amazon.com/blogs/compute/introducing-amazon-eventbridge-scheduler/)

## Notes
- EventBridge Scheduler launched in November 2022 (newer than Step Functions Wait)
- Purpose-built for one-time scheduled tasks
- Step Functions Wait is better for <1 hour delays (simpler, visual)
- For 24+ hour delays, EventBridge Scheduler is the clear winner
