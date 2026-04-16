# ADR 0003: WhatsApp Integration Architecture

**Date:** 2026-04-15  
**Status:** Accepted  
**Deciders:** Development Team  

## Context

AgriNexus AI needs to integrate with WhatsApp Business API to provide a low-friction user experience for farmers. The integration must handle:
- Webhook verification and message receipt
- Signature validation for security
- Message deduplication (WhatsApp can send duplicates)
- Async processing (Bedrock RAG takes ~13 seconds)
- Voice message handling (requires transcription)
- Rate limiting to prevent abuse

## Decision

**Use a webhook → SQS → processor architecture with separate queues for text and voice messages.**

### Architecture

```
WhatsApp → API Gateway → Webhook Lambda → SQS Queues → Processor Lambdas
                              ↓
                         DynamoDB (dedup)
```

### Key Components

1. **Webhook Lambda** (`agrinexus-webhook-dev`)
   - Validates `X-Hub-Signature-256` using HMAC-SHA256
   - Deduplicates messages using DynamoDB conditional writes on `WAMID#`
   - Routes audio to Voice Queue, text/image to Message Queue
   - Sends immediate voice ACK for audio messages (before queue)
   - Returns 200 OK within 2 seconds (WhatsApp requirement)

2. **Message Queue** (FIFO)
   - Processes text and image messages
   - `MessageGroupId = phone_number` for per-user ordering
   - `MessageDeduplicationId = wamid` for idempotency

3. **Voice Queue** (FIFO)
   - Processes audio messages separately (longer processing time)
   - Voice Processor downloads audio, transcribes, then sends to Message Queue

4. **Message Processor Lambda**
   - Handles onboarding state machine
   - Queries Bedrock RAG (~13 seconds)
   - Sends replies via WhatsApp Graph API

## Consequences

### Positive
- ✅ **Fast webhook response** - Returns 200 OK in <500ms (WhatsApp requires <2s)
- ✅ **Reliable processing** - SQS handles retries, DLQ for failures
- ✅ **Deduplication** - Prevents duplicate processing of same message
- ✅ **Voice ACK** - Immediate feedback for voice messages (before transcription)
- ✅ **Scalability** - SQS buffers load, Lambdas scale independently
- ✅ **Ordering** - FIFO queues maintain per-user message order

### Negative
- ⚠️ **Complexity** - More components than direct webhook → Lambda
- ⚠️ **Cost** - SQS API calls (~$0.40/million requests)
- ⚠️ **Latency** - Additional ~100ms for SQS enqueue/dequeue

### Neutral
- Voice messages take longer (transcription + RAG) but user gets immediate ACK
- Rate limiting at webhook prevents queue flooding

## Alternatives Considered

### 1. Direct Webhook → Lambda (Rejected)
- **Pros:** Simpler, lower latency
- **Cons:** 
  - Can't meet 2-second WhatsApp timeout with 13-second RAG
  - No built-in retry mechanism
  - No deduplication
  - Lambda concurrency limits could cause 429 errors

### 2. Step Functions Orchestration (Rejected)
- **Pros:** Visual workflow, built-in error handling
- **Cons:**
  - Overkill for simple message processing
  - Higher cost ($25 per million state transitions)
  - Slower than direct SQS

### 3. Single Queue for All Messages (Rejected)
- **Pros:** Simpler architecture
- **Cons:**
  - Voice messages (slow) would block text messages
  - Can't optimize Lambda memory/timeout per message type

## Implementation Details

### Webhook Signature Validation
```python
def verify_signature(payload: str, signature: str) -> bool:
    app_secret = get_app_secret()  # From Secrets Manager
    expected = hmac.new(
        app_secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.replace('sha256=', ''))
```

### Deduplication Strategy
- Store `WAMID#` in DynamoDB with 24-hour TTL
- Use conditional write: `attribute_not_exists(PK)`
- If write fails → duplicate detected → skip processing

### Voice ACK Timing
```
Audio message arrives → Webhook validates → Dedup check → 
Send "Voice received" ACK → Queue to Voice Queue → Return 200 OK
```

This ensures farmers get immediate feedback (<1 second) even though transcription takes 5-10 seconds.

## Security Considerations

1. **Signature Validation:** All webhook POSTs must have valid `X-Hub-Signature-256`
2. **Secrets Management:** WhatsApp credentials stored in AWS Secrets Manager with 5-minute cache
3. **Rate Limiting:** 10 messages per user per hour (configurable)
4. **DONE/NOT YET Skip:** These keywords skip RAG processing (handled by Response Detector)

## Related Decisions
- ADR 0002: Common Layer Dependency Management
- ADR 0004: Voice Processing Pipeline
- ADR 0005: Bedrock RAG Source Attribution

## References
- [WhatsApp Business API Webhooks](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks)
- [AWS SQS FIFO Queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html)
