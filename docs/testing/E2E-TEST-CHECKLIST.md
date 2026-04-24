# End-to-End Test Checklist - Pre-Demo Verification

**Date:** April 18, 2026, 11:15 AM CET  
**Purpose:** Verify all features work before public demo sharing  
**Test User:** +49 1764 7009148  
**Bot Number:** +49 1512 0105731

---

## Test Status Legend
- ⏳ Not Started
- 🔄 In Progress
- ✅ Passed
- ❌ Failed
- ⚠️ Needs Attention

---

## 0. Automated smoke (run first)

From repo root (optional env: `KNOWLEDGE_BASE_ID`, `WEB_CHAT_URL` for steps 3–4):

```bash
chmod +x scripts/e2e-smoke.sh scripts/reset-profile.sh
./scripts/e2e-smoke.sh
```

Record last run: **date** ________ **result** ________ **notes** ________

Operational context: [docs/operations/RUNBOOK-ALERTS.md](docs/operations/RUNBOOK-ALERTS.md) (new alarms, DLQ, web abuse envelope).

---

## 1. Infrastructure Health Check

### 1.1 Lambda Functions
- [ ] ⏳ WebhookHandler - Check recent invocations
- [ ] ⏳ MessageProcessor - Check error rate
- [ ] ⏳ VoiceProcessor - Check recent runs
- [ ] ⏳ WebChatHandler - Check public demo endpoint
- [ ] ⏳ NudgeSender - Check last execution
- [ ] ⏳ ReminderSender - Check configuration
- [ ] ⏳ ResponseDetector - Check DynamoDB stream
- [ ] ⏳ WeatherPoller - Check schedule
- [ ] ⏳ DLQHandler - Check dead letter queue

### 1.2 API Endpoints
- [ ] ⏳ WhatsApp Webhook - GET verification
- [ ] ⏳ WhatsApp Webhook - POST message handling
- [ ] ⏳ Web Chat API - CORS enabled
- [ ] ⏳ Web Chat API - Rate limiting active

### 1.3 Data Stores
- [ ] ⏳ DynamoDB - Table accessible
- [ ] ⏳ DynamoDB Streams - Enabled and connected
- [ ] ⏳ S3 Bucket - Temp audio storage accessible
- [ ] ⏳ Bedrock KB - Knowledge base responding

---

## 2. WhatsApp Flow Tests

### 2.1 Onboarding Flow (Fresh User)
**Prerequisites:** Reset user data for your test WhatsApp digits (E.164 without `+`, e.g. `1555123456789`)

- [ ] ⏳ Send "Hi" → Receive language selection list
- [ ] ⏳ Select "हिंदी (Hindi)" → Receive district buttons
- [ ] ⏳ Click "लातूर" (Latur) → Receive crop buttons
- [ ] ⏳ Click "गेहूं" (Wheat) → Receive consent buttons
- [ ] ⏳ Click "हाँ ✅" → Receive completion message
- [ ] ⏳ Verify profile in DynamoDB (dialect=hi, location=Latur, crop=Wheat)

**Expected Time:** 2 minutes  
**Critical:** Must work for first-time users

### 2.2 Text RAG Query
**Prerequisites:** User onboarded

Use a **golden-style** question so the KB is likely to return grounded text (same family as [tests/test_golden_questions.py](tests/test_golden_questions.py) and the web demo sample pills). Wheat / yellowing questions may correctly **refuse** if the KB chunk does not match.

- [ ] ⏳ Send: `Cotton mein aphids ka control kaise karein?` (or Hindi: `कपास में माहू कीट कैसे नियंत्रित करें?`)
- [ ] ⏳ Receive response in expected language within 10 seconds
- [ ] ⏳ Verify response has source citation (or proper KVK-style refusal without fake source line)
- [ ] ⏳ Check no fake "स्रोत: FAO/ICAR" on refusal responses
- [ ] ⏳ Verify message saved in DynamoDB

**Expected Time:** 5-10 seconds  
**Critical:** Core feature for public demo

**Web vs WhatsApp parity:** Ask the **same** text question in [section 3.1](#31-web-chat-api) and here; both should behave similarly (same KB, different entrypoints).

### 2.3 Voice Note (Allowlisted Users Only)
**Prerequisites:** User allowlisted for voice

- [ ] ⏳ Send voice note: "गेहूं में कीड़े कैसे मारें?"
- [ ] ⏳ Receive immediate ACK: "आपकी आवाज नोंद मिली..."
- [ ] ⏳ Receive transcribed text + RAG response within 40 seconds
- [ ] ⏳ Verify audio file in S3 bucket
- [ ] ⏳ Verify Transcribe job completed

**Expected Time:** 20-40 seconds  
**Critical:** Showcase feature for judges

### 2.4 Photo Analysis (Allowlisted Users Only)
**Prerequisites:** User allowlisted for vision

- [ ] ⏳ Send crop photo (wheat leaf with issue)
- [ ] ⏳ Receive structured diagnosis in Hindi within 15 seconds
- [ ] ⏳ Verify diagnosis includes: issue, confidence, severity, safety
- [ ] ⏳ Verify image saved in S3 bucket
- [ ] ⏳ Check Claude Vision API call succeeded

**Expected Time:** 10-15 seconds  
**Critical:** Unique differentiator

### 2.5 Closed-Loop Nudge System
**Prerequisites:** User profile with demo_tier=full

#### 2.5.1 First Nudge
- [ ] ⏳ Trigger nudge manually (Latur, Wheat, favorable weather)
- [ ] ⏳ Receive nudge with crop name: "Latur: गेहूं में स्प्रे..."
- [ ] ⏳ Verify buttons: [हो गया] [अभी नहीं]
- [ ] ⏳ Click "अभी नहीं" → Receive acknowledgment
- [ ] ⏳ Verify nudge status=SENT in DynamoDB
- [ ] ⏳ Verify T+24h and T+48h schedules created in EventBridge

#### 2.5.2 T+24h Reminder
- [ ] ⏳ Trigger T+24h reminder manually
- [ ] ⏳ Receive reminder with crop name: "गेहूं में अभी तक स्प्रे नहीं किया?"
- [ ] ⏳ Verify buttons: [हो गया] [अभी नहीं]
- [ ] ⏳ Click "हो गया" → Receive completion message
- [ ] ⏳ Verify nudge status=DONE in DynamoDB
- [ ] ⏳ Verify T+48h schedule deleted from EventBridge

**Expected Time:** 5-10 seconds per interaction  
**Critical:** Core differentiator - closed-loop accountability

---

## 3. Web Demo Tests

### 3.1 Web Chat API
- [ ] ⏳ Open: https://demo.agrinexus-ai.farm/web-demo/live-2026-04-13b.html
- [ ] ⏳ Send query: "How to control cotton pests?"
- [ ] ⏳ Receive response within 10 seconds
- [ ] ⏳ Verify source citation present
- [ ] ⏳ Test rate limit: Send 6 queries in 1 hour → 6th should fail
- [ ] ⏳ Verify CORS headers allow browser access
- [ ] ⏳ Check WAF not blocking legitimate requests

**Expected Time:** 5-10 seconds per query  
**Critical:** Public-facing demo for judges

### 3.2 WhatsApp entry (redirect or deep link)
- [ ] ⏳ Open: https://demo.agrinexus-ai.farm/web-demo/chat.html — if present, verify it **redirects** to `https://wa.me/4915120105731`
- [ ] ⏳ From [live web demo](https://demo.agrinexus-ai.farm/web-demo/live-2026-04-13b.html) footer: **Start WhatsApp Chat** should target **`https://wa.me/4915120105731`** (direct deep link is OK; no redirect required)
- [ ] ⏳ Verify WhatsApp opens with bot number +49 1512 0105731

**Expected Time:** Instant  
**Critical:** Easy access for judges

---

## 4. Rate Limiting Tests

### 4.1 WhatsApp Rate Limit
- [ ] ⏳ Send 10 messages in 1 hour → All succeed
- [ ] ⏳ Send 11th message → Receive rate limit error
- [ ] ⏳ Wait 1 hour → Rate limit resets

**Expected:** 10 messages/hour per user  
**Critical:** Prevent abuse

### 4.2 Web Demo Rate Limit
- [ ] ⏳ Send 5 queries from same IP **with the same** `client_id` (browser localStorage) → All succeed
- [ ] ⏳ Send 6th query → Receive **429** (hourly cap)
- [ ] ⏳ Wait 1 hour → Rate limit resets

**Expected:** 5 questions/hour per **hashed IP** and per **client_id** (see [src/web-chat/handler.py](src/web-chat/handler.py)); plus API Gateway throttling and WAF (see [docs/operations/RUNBOOK-ALERTS.md](docs/operations/RUNBOOK-ALERTS.md)).

**Critical:** Prevent abuse

---

## 5. Error Handling Tests

### 5.1 Invalid Inputs
- [ ] ⏳ Send empty message → Graceful error
- [ ] ⏳ Send very long message (>500 chars) → Truncated or rejected
- [ ] ⏳ Send non-farming question → "I can only help with farming"
- [ ] ⏳ Send medical question → Proper refusal

### 5.2 Service Failures
- [ ] ⏳ Check DLQ for failed messages
- [ ] ⏳ Verify DLQ handler sends error messages in user's dialect
- [ ] ⏳ Check CloudWatch alarms not triggered

---

## 6. Data Retention & Privacy

### 6.1 TTL Configuration (code baseline — verify in Dynamo if needed)
- [ ] ⏳ **Conversation / RAG saves** (`save_message` in processor): **90-day** TTL on `MSG#*` items written by the processor
- [ ] ⏳ **Webhook stream copies** (messages stored for response detector in [src/webhook/handler.py](src/webhook/handler.py)): **7-day** TTL — applies to those `MSG#*` rows, **not** tied to `demo_tier` in code
- [ ] ⏳ **WhatsApp dedup** keys (`WAMID#*`): **24-hour** TTL
- [ ] ⏳ **Nudge records** ([src/nudge/sender.py](src/nudge/sender.py)): **180-day** TTL
- [ ] ⏳ **`demo_tier=public`**: affects **nudge scheduling** (single contextual nudge vs full T+24h/T+48h), not a separate user-level TTL flag in the snippets above

### 6.2 PII Redaction
- [ ] ⏳ Check logs don't contain phone numbers
- [ ] ⏳ Verify PII redaction in common layer active

---

## 7. Monitoring & Observability

### 7.1 CloudWatch Dashboard
- [ ] ⏳ Verify dashboard exists: AgriNexus-Operations-dev
- [ ] ⏳ Check Lambda metrics visible
- [ ] ⏳ Check SQS queue depth
- [ ] ⏳ Check custom metrics (NudgesSent, NudgesCompleted)

### 7.1b Stack alarms (SNS `agrinexus-alerts-dev`)
- [ ] ⏳ Nudge workflow failures alarm not firing (`agrinexus-nudge-workflow-failures-*`)
- [ ] ⏳ Cost alarm not firing (`agrinexus-high-cost-*`)
- [ ] ⏳ Processor / webhook / web-chat / voice **Errors** alarms not firing
- [ ] ⏳ Message queue **age** alarm not firing (`agrinexus-messages-queue-age-*`)
- [ ] ⏳ **DLQ depth** alarm not firing (`agrinexus-messages-dlq-depth-*`)

See [docs/operations/RUNBOOK-ALERTS.md](docs/operations/RUNBOOK-ALERTS.md).

### 7.2 X-Ray Tracing
- [ ] ⏳ Verify X-Ray traces for recent requests
- [ ] ⏳ Check end-to-end latency breakdown

### 7.3 Cost Monitoring
- [ ] ⏳ Check current daily spend < $20
- [ ] ⏳ Verify cost alarm configured

---

## 8. Security Tests

### 8.1 WhatsApp Signature Verification
- [ ] ⏳ Verify webhook validates Meta HMAC-SHA256 signatures
- [ ] ⏳ Test with invalid signature → Rejected

### 8.2 Secrets Management
- [ ] ⏳ Verify no secrets in code
- [ ] ⏳ Check Secrets Manager caching working
- [ ] ⏳ Verify secrets rotation possible

---

## 9. Performance Tests

### 9.1 Latency
- [ ] ⏳ Text query: < 10 seconds
- [ ] ⏳ Voice note: < 40 seconds
- [ ] ⏳ Photo analysis: < 15 seconds
- [ ] ⏳ Nudge delivery: < 10 seconds

### 9.2 Concurrency
- [ ] ⏳ Send 5 concurrent text queries → All succeed
- [ ] ⏳ Check Lambda concurrency metrics

---

## 10. Documentation & Links

### 10.1 Public Links
- [ ] ⏳ Article link works: https://builder.aws.com/content/3C8hBRTcsRuQrHzE3Pq243yhXTF/aideas-finalist-agrinexus-ai
- [ ] ⏳ GitHub repo accessible: https://github.com/prasadt1/agrinexus-ai
- [ ] ⏳ YouTube demo video: https://youtu.be/Hr9EcblzkwI
- [ ] ⏳ WhatsApp link: https://wa.me/4915120105731
- [ ] ⏳ Web demo: https://demo.agrinexus-ai.farm/web-demo/live-2026-04-13b.html

### 10.2 Demo Request Template
- [ ] ⏳ GitHub issue template accessible
- [ ] ⏳ Instructions clear for requesting voice/photo/nudge access

---

## Test Execution Plan

### Phase 1: Infrastructure (5 minutes)
1. Check all Lambda functions healthy
2. Verify API endpoints responding
3. Check DynamoDB and S3 accessible

### Phase 2: Core Flows (15 minutes)
1. Reset user data
2. Test onboarding flow
3. Test text RAG query
4. Test voice note (if allowlisted)
5. Test photo analysis (if allowlisted)

### Phase 3: Nudge System (10 minutes)
1. Update profile to demo_tier=full
2. Trigger first nudge
3. Test "Not Yet" response
4. Trigger T+24h reminder
5. Test "Done" response
6. Verify schedules cancelled

### Phase 4: Web Demo (5 minutes)
1. Test web chat API
2. Test rate limiting
3. Verify CORS and WAF

### Phase 5: Validation (5 minutes)
1. Check CloudWatch metrics
2. Verify no errors in logs
3. Check cost within budget

**Total Time:** ~40 minutes

---

## Critical Issues (Must Fix Before Demo)
- [ ] ⏳ None identified yet

## Nice-to-Have Improvements
- [ ] ⏳ None identified yet

---

## Sign-Off

**Tested By:** _________________  
**Date:** _________________  
**Status:** ⏳ Not Started | 🔄 In Progress | ✅ All Passed | ❌ Issues Found

**Notes:**
