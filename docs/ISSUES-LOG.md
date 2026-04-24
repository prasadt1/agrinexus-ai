# Issues Log (Resolved)

This file tracks notable issues encountered while building and deploying AgriNexus AI and how they were resolved.

> Note: This is a **public** troubleshooting history intended for judges/reviewers. It avoids secrets, phone numbers, and account-specific details.

---

## April 2026 — Production Readiness & Cost Optimization

### 2026-04-23 — Vision analysis: non-agri images were incorrectly diagnosed

- **Symptom**: UI screenshots / leaf logos / scenery / selfies were sometimes treated as crop photos and diagnosed.
- **Root cause**: The vision flow was optimized for "always return an agronomy answer," so non-agri images could slip through without a strict eligibility gate.
- **Fix**:
  - Added a **2-stage image eligibility gate** in the WhatsApp pipeline:
    - Classify image as `AGRI_PHOTO | NON_AGRI | EXPLICIT | UNKNOWN`
    - Only run crop diagnosis for `AGRI_PHOTO`
  - Do not save non-agri/explicit images to S3.
- **Verification**: Unit tests around the gating behavior. Redeploy `MessageProcessor` and re-test with non-agri examples.

### 2026-04-05 — Nudge expiry logic implementation

- **Symptom**: Nudges stayed in REMINDED status indefinitely after T+48h reminder with no closure mechanism.
- **Root cause**: Only two statuses existed (SENT, REMINDED) with no terminal states for incomplete nudges.
- **Fix**: Added EXPIRED status. Response detector marks nudge as EXPIRED when farmer says "not yet" after T+48h. Added T+72h auto-expiry via EventBridge Scheduler.
- **Impact**: Clean nudge lifecycle with proper closure. Analytics can now track completion vs expiry rates.

### 2026-04-05 — Voice ACK latency optimization

- **Symptom**: Voice ACK message ("We received your message...") took 5-6 seconds to arrive.
- **Root cause**: ACK was sent from VoiceProcessor Lambda after SQS delivery, cold start, media download, S3 upload, and Transcribe job start.
- **Fix**: Moved ACK to webhook handler immediately after deduplication check (before SQS enqueue).
- **Impact**: ACK latency reduced from 5-6s to 1-2s. Users get immediate feedback.

### 2026-04-04 — S3 vector store migration (cost savings)

- **Symptom**: OpenSearch Serverless cost $174/month fixed, burning through AWS credits rapidly. Deleted collection on March 22 to stop burn, but RAG was broken.
- **Root cause**: OpenSearch Serverless has fixed cost (0.5 OCU × 2 × $0.24/hr × 730hr).
- **Fix**: Migrated from OpenSearch Serverless to Amazon Bedrock Knowledge Base with S3 vector store. Created new S3 bucket `agrinexus-kb-vectors`, uploaded all 8 FAO/ICAR/NIPHM/PAU PDFs.
- **Impact**: Reduced from $174/month fixed to <$1/month variable. Savings: ~$173/month. System now entirely pay-per-use.

### 2026-04-04 — DynamoDB float type error

- **Symptom**: Processor Lambda failing with "Float types are not supported. Use Decimal types instead" when storing weather data.
- **Root cause**: DynamoDB Python SDK requires Decimal type for numbers, not float. Weather API returns floats.
- **Fix**: Added `convert_floats_to_decimal()` helper function to recursively convert all floats to Decimal before DynamoDB writes.
- **Impact**: Weather nudges now work correctly.

### 2026-04-04 — Voice ACK duplicate messages

- **Symptom**: Users received duplicate "Question received" acknowledgment messages when sending voice notes.
- **Root cause**: ACK was sent inside polling loop in VoiceProcessor, potentially multiple times.
- **Fix**: Moved ACK to single location before polling loop starts.
- **Impact**: Clean single ACK per voice message.

---

## March 2026 — Cost Optimization & Code Quality Sprint

### 2026-03-22 — AWS cost optimization sprint

- **Symptom**: Received AWS Free Tier alert (SQS at 85% of 1M limit). OpenSearch Serverless burning $5.80/day.
- **Fix**: Deployed 8 optimizations:
  1. SQS long polling (20s wait time) - 70-80% reduction in API calls
  2. Secrets Manager caching (5-min TTL) - 90% reduction in calls
  3. Lambda memory right-sizing (512MB → 256MB for webhook/weather)
  4. DynamoDB query optimization (replaced full table SCAN with GSI queries)
  5. CloudWatch logging reduction (removed debug payloads)
  6. Transcribe polling interval (1s → 3s)
  7. S3 lifecycle for images (7-day expiry)
  8. Emergency: Deleted OpenSearch Serverless collection
- **Impact**: Estimated monthly savings: $165-520. System now costs ~$0-2/month (all pay-per-use).

### 2026-03-05 — Lambda packaging issue (CommonLayer)

- **Symptom**: Consolidation refactor broke Lambda packaging - `from common.whatsapp import` would fail at runtime with ModuleNotFoundError.
- **Root cause**: SAM packages each Lambda from its own CodeUri directory. `src/common/` not accessible from `src/nudge/` or `src/voice/`.
- **Fix**: Created Lambda Layer (CommonLayer) to share common module across all Lambdas. Added layer to 6 Lambdas.
- **Impact**: All imports now work correctly, no runtime failures.

### 2026-03-05 — Telugu list message implementation

- **Symptom**: Telugu language fix changed response type to 'list' but no `send_whatsapp_list()` function existed. Complete UX failure for Telugu farmers.
- **Root cause**: WhatsApp list message requires different API payload format than buttons.
- **Fix**: Implemented `send_whatsapp_list()` function with proper WhatsApp interactive list format. Updated onboarding response and handler routing.
- **Impact**: Telugu farmers can now select their language with interactive list UI.

### 2026-03-05 — VoiceProcessor Lambda timeout

- **Symptom**: 60-second polling loop vs 30-second Lambda timeout - voice transcription would timeout before completion.
- **Fix**: Increased VoiceProcessor timeout to 90 seconds in template-week2.yaml.
- **Impact**: Voice messages now process successfully without timeout errors.

### 2026-03-05 — Image format detection

- **Symptom**: Hardcoded to image/jpeg - PNG and WebP images would fail.
- **Fix**: Added magic byte detection for JPEG (`\xff\xd8`), PNG (`\x89PNG`), WebP (`RIFF...WEBP`). Set media_type dynamically.
- **Impact**: Vision analysis works correctly for PNG and WebP images, not just JPEG.

### 2026-03-05 — PII redaction in logs

- **Symptom**: Phone numbers and message content logged at INFO level - GDPR/privacy risk.
- **Fix**: Added `redact_phone()` helper function (shows only first 3 digits). Redacted phone numbers in log statements. Removed message content from INFO logs.
- **Impact**: CloudWatch logs no longer expose full phone numbers or message content.

---

## February 2026 — MVP Development & Core Features

### 2026-02-28 — Voice output engine fix

- **Symptom**: English voice output failing with error "This voice does not support the selected engine: standard".
- **Root cause**: Kajal (English Indian voice) requires 'neural' engine, but code was using 'standard' engine for all voices.
- **Fix**: Updated `get_polly_voice()` to return engine type. English (Kajal) uses 'neural', Hindi/Marathi (Aditi) uses 'standard'.
- **Impact**: English voice responses now work correctly, end-to-end voice testing complete.

### 2026-02-27 — Duplicate nudges (6h apart)

- **Symptom**: Weather poller runs every 6 hours, creating new spray nudge each time even if farmer already has pending nudge. Farmers receiving 3-4 identical nudges per day.
- **Root cause**: Nudge sender didn't check for existing pending nudges before creating new ones.
- **Fix**: Added `has_pending_nudge()` function that checks for existing pending nudges for same activity on same day.
- **Impact**: Farmers receive max 1 nudge per activity per day, plus T+24h and T+48h reminders if not completed.

### 2026-02-27 — DONE/NOT YET keyword filtering

- **Symptom**: When user replies "अभी नहीं" (NOT YET), system sends multiple confusing messages: acknowledgment from detector + RAG response from processor + farming-only message.
- **Root cause**: Processor Lambda was processing ALL text messages including DONE/NOT YET keywords.
- **Fix**: Added keyword filter in processor to skip DONE/NOT YET messages. These are now ONLY handled by response detector.
- **Impact**: Clean single response to DONE/NOT YET, no more duplicate/confusing messages.

### 2026-02-23 — Domain restriction (agricultural scope only)

- **Symptom**: System was answering medical/health questions (e.g., "I have fever, what can I take?").
- **Risk**: Liability and scope creep - agricultural advisory should not provide medical advice.
- **Fix**: Updated RAG prompt with explicit domain restrictions - only answers farming questions. Non-farming questions now receive: "I can only help with farming questions."
- **Impact**: Prevents liability issues and keeps system focused on agricultural domain.

### 2026-02-23 — Guardrail configuration fix

- **Symptom**: Processor Lambda failing with "Invalid guardrail identifier" error.
- **Root cause**: Passing "1" as guardrail ID instead of empty string (guardrails are optional).
- **Fix**: Updated Lambda environment variable to empty string, added check in code to only include guardrail config if ID is non-empty.
- **Impact**: RAG queries now work correctly without requiring Bedrock Guardrails.

### 2026-02-23 — Lambda module import fix

- **Symptom**: Processor Lambda failing with "No module named 'output'" error.
- **Root cause**: Processor handler imports voice/vision modules from separate Lambda packages (different CodeUri).
- **Fix**: Copied `output.py` and `analyzer.py` to processor directory, updated imports to use local modules.
- **Impact**: Voice output and vision analysis now work correctly from processor Lambda.

### 2026-02-17 — Interactive button message type handling

- **Symptom**: When users clicked reply buttons, WhatsApp sent `message.type == "interactive"` but processor only handled `type == "text"`, causing button clicks to be ignored.
- **Fix**: Updated processor to extract text from both `message.text.body` (text messages) and `message.interactive.button_reply.title` (button clicks).
- **Impact**: All button clicks now work correctly; onboarding flow completes without requiring users to type.

### 2026-02-17 — Telugu crop button detection

- **Symptom**: Users typing Telugu crop names (గోధుమ, పత్తి, సోయాబీన్) weren't recognized, causing onboarding to loop on crop selection.
- **Fix**: Added Telugu script keywords to crop detection logic. Now checks for పత్తి (cotton), గోధుమ (wheat), సోయాబీన్ (soybean), మొక్కజొన్న (maize).
- **Impact**: Telugu onboarding flow completes successfully with both button clicks and text input.

### 2026-02-17 — English language support in RAG queries

- **Symptom**: English onboarding worked but RAG queries returned Hindi responses despite user selecting English dialect.
- **Fix**: Updated `query_bedrock()` function to use language-specific instructions for each dialect (hi, mr, te, en) instead of generic dialect code.
- **Impact**: All 4 languages (Hindi, Marathi, Telugu, English) now respond correctly in their respective languages.

### 2026-02-10 — Response latency (5 minutes → sub-10 seconds)

- **Symptom**: First RAG response took ~5 minutes due to cold start chain (Lambda → SQS FIFO → Lambda → Bedrock KB → Bedrock Agent).
- **Fix**: Added immediate acknowledgment message ("Processing your question...") for perceived performance.
- **Impact**: Acceptable UX for demo; subsequent warm invocations complete in <10 seconds.

### 2026-02-10 — Webhook handler zero application logs

- **Symptom**: Lambda was executing (START/END visible in CloudWatch) but zero application log lines — no way to debug message processing.
- **Fix**: Added structured logging (logger.info with event payload, HTTP method, message content) throughout the handler chain.
- **Impact**: Full observability of message flow from webhook to response.

### 2026-02-10 — DynamoDB idempotency for WhatsApp webhooks

- **Symptom**: WhatsApp/Meta can retry webhook deliveries, causing duplicate message processing.
- **Fix**: Added wamid-based deduplication check in DynamoDB before SQS queuing. 24-hour TTL on dedup records.
- **Impact**: Guaranteed exactly-once processing regardless of webhook retries.

### 2026-02-09 — Step Functions wait state cost trap

- **Symptom**: Original design used Standard Workflow Wait states (24h + 72h), keeping executions alive for ~4 days. At scale, burns state transitions and concurrent execution limits.
- **Fix**: Replaced with EventBridge Scheduler pattern. Step Functions workflow completes in seconds. Reminders handled by separate EventBridge scheduled events at T+24h, T+48h, T+72h.
- **Impact**: Dramatic cost reduction; executions measured in seconds not days.

---

## Adding a new entry

When adding a new entry:

- Include **date**, **symptom**, **root cause**, **fix**, **impact/verification**
- Do not include secrets, tokens, or real phone numbers
