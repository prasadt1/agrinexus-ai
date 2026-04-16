# ADR 0004: Voice Processing Pipeline

**Date:** 2026-04-15  
**Status:** Accepted  
**Deciders:** Development Team  

## Context

Farmers prefer voice input over typing, especially in regional languages. WhatsApp voice notes need to be:
1. Transcribed to text (Amazon Transcribe)
2. Processed through Bedrock RAG
3. Optionally converted back to voice (Amazon Polly)

The challenge: Voice processing takes 5-10 seconds (download + transcribe), but WhatsApp expects webhook response in <2 seconds.

## Decision

**Use a separate Voice Queue with immediate ACK, then transcribe and route to Message Queue for RAG processing.**

### Architecture

```
WhatsApp Audio → Webhook → Voice ACK (immediate) → Voice Queue
                                                        ↓
                                            Voice Processor Lambda
                                                        ↓
                                    Download → S3 → Transcribe → Text
                                                        ↓
                                                  Message Queue
                                                        ↓
                                              Message Processor (RAG)
                                                        ↓
                                            WhatsApp (text + optional audio)
```

## Key Design Decisions

### 1. Immediate Voice ACK
**Send acknowledgment BEFORE transcription starts**

```python
# In webhook handler (before queuing)
if message_type == 'audio':
    send_voice_received_ack(from_number)  # "आपका संदेश मिल गया..."
    # Then queue to Voice Queue
```

**Rationale:**
- Farmer gets feedback in <1 second
- Prevents "did my message send?" confusion
- WhatsApp webhook returns 200 OK quickly

### 2. Separate Voice Queue
**Why not process audio in Message Processor?**

- Voice processing takes 5-10 seconds (vs <1s for text)
- Would block text messages in FIFO queue
- Different Lambda timeout/memory requirements
- Allows independent scaling

### 3. Transcribe → Message Queue Pattern
**Why not send reply directly from Voice Processor?**

```
Voice Processor → Transcribe → Message Queue → Message Processor → Reply
```

**Rationale:**
- Reuses existing RAG logic (no duplication)
- Consistent response format (citations, helpline footer)
- Voice Processor focuses on transcription only
- Message Processor handles all RAG queries uniformly

### 4. S3 Temporary Storage
**Audio files stored in S3 with 1-day lifecycle**

```yaml
TempAudioBucket:
  LifecycleConfiguration:
    Rules:
      - Id: DeleteOldAudio
        Prefix: voice/
        ExpirationInDays: 1
```

**Rationale:**
- Transcribe requires S3 input (can't use in-memory)
- 1-day retention for debugging
- Auto-cleanup prevents storage costs

### 5. Optional Voice Response
**Text-first, then optional audio**

```python
# Always send full text first
send_whatsapp_message(from_number, reply_text)

# Then optionally send audio (truncated to 700 chars)
if send_voice:
    tts_text = truncate_for_voice(reply_text)
    audio_url = text_to_speech(tts_text, dialect, from_number)
    send_whatsapp_message(from_number, '', audio_url=audio_url)
```

**Rationale:**
- WhatsApp audio messages don't show body text
- Farmer can read full answer immediately
- Audio is supplementary (for accessibility)
- Truncation keeps Polly costs low

## Consequences

### Positive
- ✅ **Fast feedback** - Voice ACK in <1 second
- ✅ **No blocking** - Voice processing doesn't delay text messages
- ✅ **Reusable RAG** - Single code path for all queries
- ✅ **Cost-efficient** - S3 auto-cleanup, truncated TTS
- ✅ **Accessible** - Voice input + optional voice output

### Negative
- ⚠️ **Complexity** - Two-stage processing (transcribe → RAG)
- ⚠️ **Latency** - Total time: 5-10s transcribe + 13s RAG = 18-23s
- ⚠️ **Cost** - Transcribe ($0.024/min) + Polly ($4/million chars)

### Neutral
- Voice ACK is in user's dialect (requires profile lookup)
- Transcribe supports Hindi, Marathi, Telugu, English auto-detection

## Implementation Details

### Voice ACK Messages (Dialect-Aware)
```python
VOICE_RECEIVED_ACK = {
    'hi': 'आपका संदेश मिल गया। जवाब तैयार कर रहे हैं…',
    'mr': 'तुमचा संदेश मिळाला. उत्तर तयार करत आहोत…',
    'te': 'మీ సందేశం అందింది. సమాధానం సిద్ధం చేస్తున్నాము…',
    'en': 'We received your message and are preparing a reply…',
}
```

### Transcribe Configuration
```python
transcribe.start_transcription_job(
    TranscriptionJobName=job_name,
    Media={'MediaFileUri': s3_uri},
    MediaFormat='ogg',  # WhatsApp uses OGG Opus
    LanguageCode='hi-IN',  # Or auto-detect
    Settings={
        'ShowSpeakerLabels': False,
        'MaxSpeakerLabels': 1
    }
)
```

### Voice Truncation Strategy
```python
def truncate_for_voice(text: str, max_chars: int = 700) -> str:
    """Truncate at sentence boundary, keep first 700 chars"""
    if len(text) <= max_chars:
        return text
    
    # Find last sentence boundary before max_chars
    truncated = text[:max_chars]
    last_period = max(
        truncated.rfind('।'),  # Hindi/Marathi
        truncated.rfind('.'),  # English
        truncated.rfind('?'),
        truncated.rfind('!')
    )
    
    if last_period > 0:
        return truncated[:last_period + 1]
    return truncated
```

**Rationale:**
- Full answer always sent as text
- Audio is summary (first 700 chars ≈ 1 minute)
- Keeps Polly costs low (~$0.003 per response)

## Alternatives Considered

### 1. Synchronous Transcription in Webhook (Rejected)
- **Pros:** Simpler flow
- **Cons:** 
  - Can't meet 2-second WhatsApp timeout
  - Would cause webhook failures
  - No immediate user feedback

### 2. Direct Voice → RAG (No Transcribe) (Rejected)
- **Pros:** Lower latency, lower cost
- **Cons:**
  - Bedrock doesn't support audio input directly
  - Would need custom speech-to-text model
  - Less accurate than Transcribe

### 3. Always Send Voice Response (Rejected)
- **Pros:** Consistent UX
- **Cons:**
  - High Polly costs ($4/million chars)
  - Slower (TTS takes 2-3 seconds)
  - WhatsApp audio doesn't show text (bad UX)

### 4. Store Full Audio Permanently (Rejected)
- **Pros:** Audit trail, training data
- **Cons:**
  - Privacy concerns (farmer voice recordings)
  - Storage costs ($0.023/GB/month)
  - GDPR/data retention compliance

## Performance Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Voice ACK latency | <2s | <1s ✅ |
| Transcription time | <10s | 5-8s ✅ |
| Total response time | <25s | 18-23s ✅ |
| Transcription accuracy | >90% | ~95% ✅ |
| Cost per voice query | <$0.01 | ~$0.005 ✅ |

## Related Decisions
- ADR 0003: WhatsApp Integration Architecture
- ADR 0005: Bedrock RAG Source Attribution

## References
- [Amazon Transcribe Pricing](https://aws.amazon.com/transcribe/pricing/)
- [Amazon Polly Pricing](https://aws.amazon.com/polly/pricing/)
- [WhatsApp Audio Message Format](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media)
