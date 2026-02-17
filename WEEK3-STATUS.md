# Week 3 - Voice + Vision + Polish

## Timeline: 5-6 days
**Started:** 2026-02-17

## Pre-Week 3 Checklist
- [x] WhatsApp webhook is live and receiving messages
- [x] Onboarding flow works with Reply Buttons (all 4 languages: English, Hindi, Marathi, Telugu)
- [x] Nudge closed-loop tested (nudge → "हो गया" → DONE)
- [ ] Template weather_nudge_spray status (check Meta dashboard)

## Priority Order
1. **Voice Input (Amazon Transcribe)** - Day 1-2 ⏳ IN PROGRESS
2. **Voice Output (Amazon Polly)** - Day 2-3
3. **Vision (Claude 3 Sonnet Vision)** - Day 3-4
4. **Latency Optimization** - Day 4-5
5. **Polish Items** - Day 5-6

---

## Priority 1: Voice Input (Amazon Transcribe) - Day 1-2

### Why Priority #1?
Rural Indian farmers have limited literacy. Voice notes are their natural interaction mode on WhatsApp. This is the accessibility differentiator.

### Implementation Plan

#### 1.1 Create voice-processor Lambda ⏳
- [ ] Create `src/voice/processor.py`
- [ ] Create `src/voice/requirements.txt`
- [ ] Implement voice note download from WhatsApp
- [ ] Upload to S3 temp bucket
- [ ] Start Amazon Transcribe job
- [ ] Poll for completion
- [ ] Extract transcribed text
- [ ] Pass to conversation processor
- [ ] Cleanup temp files

#### 1.2 Update webhook handler routing
- [ ] Detect `message.type == "audio"`
- [ ] Send immediate acknowledgment
- [ ] Route to voice processor

#### 1.3 Add to SAM template
- [ ] Add VoiceProcessor Lambda
- [ ] Add TempAudioBucket S3 bucket
- [ ] Add IAM policies (Transcribe, S3, Secrets Manager)
- [ ] Add lifecycle policy (delete after 24 hours)

#### 1.4 Transcribe language verification
- [x] Hindi (hi-IN) - CONFIRMED supported
- [ ] Marathi (mr-IN) - CHECK if supported
- [ ] Telugu (te-IN) - CHECK if supported
- [ ] English (en-IN) - CONFIRMED supported

### Technical Notes

**Transcribe Language Support:**
- Hindi (hi-IN): ✅ Confirmed
- English (en-IN): ✅ Confirmed
- Marathi: Need to verify if mr-IN is supported
- Telugu: Need to verify if te-IN is supported

**Audio Format:**
- WhatsApp sends: OGG/OPUS format
- Transcribe accepts: OGG with opus codec (try first)
- Fallback: Convert to WAV/FLAC using FFmpeg Lambda Layer

**Confidence Threshold:**
- If confidence ≥ 0.5: Process as normal
- If confidence < 0.5: Send fallback message asking to resend or type

**Processing Flow:**
```
WhatsApp Voice Note → Webhook → Download → S3 Upload → Transcribe Job → 
Poll Result → Extract Text → Conversation Processor → Response
```

---

## Priority 2: Voice Output (Amazon Polly) - Day 2-3

### Implementation Plan

#### 2.1 Add Polly to conversation response flow
- [ ] Generate audio response after Bedrock text response
- [ ] Upload MP3 to S3 with presigned URL
- [ ] Send audio via WhatsApp

#### 2.2 Polly voice mapping
- Hindi: Aditi (Neural) ✅
- English: Aditi (Indian accent) ✅
- Marathi: Aditi (fallback to Hindi) ⚠️
- Telugu: No native voice - text only ⚠️

#### 2.3 Response logic
- If user sent voice note OR has voice preference: send audio + text
- Otherwise: text only

---

## Priority 3: Vision - Pest Image Diagnosis - Day 3-4

### Implementation Plan

#### 3.1 Create vision-processor Lambda
- [ ] Create `src/vision/processor.py`
- [ ] Download image from WhatsApp
- [ ] Upload to S3 temp bucket
- [ ] Call Claude 3 Sonnet Vision via `invoke_model`
- [ ] Parse diagnosis
- [ ] Respond in user's dialect
- [ ] Cleanup temp image

#### 3.2 Claude Vision prompt
- Analyze crop image
- Identify pest/disease/condition
- Provide confidence level
- Recommend action
- Indicate urgency
- Include KVK disclaimer
- Avoid banned pesticides

#### 3.3 Low confidence handling
- Ask for clearer photo
- Provide guidance on taking better photos

---

## Priority 4: Latency Optimization - Day 4-5

### Implementation Plan

#### 4.1 Secrets Manager caching
- [ ] Implement module-level cache
- [ ] Avoid repeated `get_secret_value` calls

#### 4.2 Bedrock session reuse
- [ ] Use phone number as session ID
- [ ] Maintain conversation context

#### 4.3 Warm-up strategy
- [ ] CloudWatch scheduled event every 5 minutes
- [ ] Prevent cold starts for critical Lambdas

---

## Priority 5: Polish Items - Day 5-6

### Implementation Plan

#### 5.1 DLQ apology messages
- [ ] Verify all 4 dialects covered
- [ ] Hindi, Marathi, Telugu, English

#### 5.2 HELP command
- [ ] Implement HELP menu
- [ ] Show available commands
- [ ] Include RESET, STOP, DELETE MY DATA, ABOUT

#### 5.3 WhatsApp template status
- [ ] Check weather_nudge_spray approval status
- [ ] Document workaround if still pending

---

## Week 3 Acceptance Criteria

| Test | Criteria | Priority | Status |
|------|----------|----------|--------|
| Voice input (Hindi) | Send voice note → get text response | P0 | ⏳ |
| Voice output (Hindi) | Voice query → receive audio response | P1 | ⏳ |
| Vision (cotton pest) | Send leaf photo → get diagnosis in Hindi | P1 | ⏳ |
| Latency (warm) | Text response < 10 seconds on warm invocation | P0 | ⏳ |
| HELP command | Send "HELP" → get menu | P2 | ⏳ |
| DLQ messages | All 4 dialects covered | P2 | ⏳ |

---

## What NOT to Do ❌

- ❌ Do NOT build custom vocabulary for Transcribe (post-MVP)
- ❌ Do NOT implement sentiment detection
- ❌ Do NOT build analytics dashboard yet (Week 4)
- ❌ Do NOT add more KB documents
- ❌ Do NOT implement feedback system
- ❌ Do NOT spend more than 1 day on latency optimization

---

## Next Steps

1. Verify Transcribe language support for Marathi and Telugu
2. Create voice-processor Lambda
3. Update webhook handler for audio routing
4. Test with real voice notes

