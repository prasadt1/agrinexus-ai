# Voice Pipeline Testing Guide

Since WhatsApp test numbers don't support media (voice notes, images), we test the voice pipeline in isolation to prove it works.

## What We're Testing

The voice pipeline has these components:
1. **WhatsApp Media Download** - Simple HTTP GET (trivial, not tested)
2. **Amazon Transcribe** - Speech-to-text in 4 languages ✅ TESTED
3. **Text Processing** - RAG query with transcribed text ✅ TESTED
4. **Response Generation** - Bedrock KB response ✅ TESTED

## Test Scripts

### Option 1: Simple Test (Recommended)

Test with your own audio file:

```bash
# Record yourself saying a question in Hindi/English/Marathi/Telugu
# Save as MP3 (or convert: ffmpeg -i voice.m4a voice.mp3)

python tests/test_voice_simple.py voice.mp3 hi-IN
```

**Example questions to record**:
- Hindi: "कपास में कीट कैसे नियंत्रित करें"
- English: "How do I control cotton pests"
- Marathi: "कापसातील किडे कसे नियंत्रित करावे"
- Telugu: "పత్తిలో తెగుళ్లను ఎలా నియంత్రించాలి"

### Option 2: Full Pipeline Test

Tests Transcribe → SQS → Processor → RAG → Response:

```bash
python tests/test_voice_pipeline.py
```

This script:
1. Creates test user profile
2. Generates audio using Amazon Polly
3. Uploads to S3
4. Transcribes with Amazon Transcribe
5. Queues for message processing
6. Checks for RAG response
7. Cleans up

## Expected Results

### Successful Test Output

```
Testing voice transcription...
Audio file: voice.mp3
Language: hi-IN
------------------------------------------------------------

1. Uploading to S3...
   ✓ Uploaded: s3://agrinexus-temp-audio-dev-043624892076/test/voice-test-1234567890.mp3

2. Starting transcription job: test-1234567890
   ⏳ Waiting for completion...

3. ✓ Transcription complete!

============================================================
TRANSCRIPT: कपास में कीट कैसे नियंत्रित करें
CONFIDENCE: 92.45%
============================================================

✓ PASS: Confidence above threshold (0.5)

4. Cleaning up...
   ✓ Deleted transcription job and S3 object
```

## What This Proves

✅ **Amazon Transcribe works** with all 4 languages (hi-IN, mr-IN, te-IN, en-IN)  
✅ **Confidence scoring works** (threshold 0.5)  
✅ **S3 upload/download works**  
✅ **Transcribed text flows to message processor**  
✅ **RAG responds to voice-originated queries**

## What's Not Tested (But Trivial)

❌ **WhatsApp media download** - Just an HTTP GET with Bearer token:
```python
url = f"https://graph.facebook.com/v22.0/{media_id}"
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(url, headers=headers)
audio_bytes = response.content
```

This is standard HTTP and will work with a real WhatsApp Business number.

## For Competition Demo

Show judges:
1. **Test script output** (proves Transcribe works)
2. **Architecture diagram** (shows end-to-end flow)
3. **Code walkthrough** (src/voice/processor.py)
4. **CloudWatch logs** (shows real invocations)

Explain: "WhatsApp test numbers don't support media, but we've tested the complex parts (Transcribe, multi-language, confidence handling) in isolation. The media download is a simple HTTP GET that works with real numbers."

## Troubleshooting

### "No such file or directory"
Make sure audio file path is correct:
```bash
ls -la voice.mp3
python tests/test_voice_simple.py ./voice.mp3 hi-IN
```

### "Transcription failed"
Check audio format:
- Supported: MP3, MP4, WAV, FLAC, OGG, AMR, WebM
- Convert if needed: `ffmpeg -i input.m4a output.mp3`

### "Low confidence"
- Speak clearly and slowly
- Reduce background noise
- Use a better microphone
- Try a shorter phrase

### "Timeout"
- Audio file might be too long (>60 seconds)
- Network issues with Transcribe API
- Try again or check AWS service health

## Next Steps

After voice testing:
1. ✅ Voice Input (Transcribe) - TESTED
2. ⏳ Voice Output (Polly) - Next
3. ⏳ Vision (Claude 3 Sonnet) - After Polly
4. ⏳ Real WhatsApp number (optional) - For end-to-end demo
