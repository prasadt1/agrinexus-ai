# Voice Output Testing Guide

## Quick Test (Recommended)

Run the automated test script:

```bash
python tests/test_voice_output.py
```

This will:
1. Generate audio in all 4 languages (Hindi, Marathi, Telugu, English)
2. Upload to S3
3. Give you URLs to listen to the audio

## Listen to Generated Audio

After running the test, you'll see URLs like:
```
https://agrinexus-temp-audio-dev-043624892076.s3.amazonaws.com/voice-output/...
```

**Option 1: Browser**
- Copy the URL
- Paste in your browser
- Audio will play automatically

**Option 2: Download**
- Use the curl command shown in test output
- Example:
  ```bash
  curl 'https://...' -o my-audio.mp3
  open my-audio.mp3  # macOS
  ```

## Test Your Own Text

Edit `tests/test_voice_output.py` and change the test cases:

```python
test_cases = [
    {
        'text': 'Your Hindi text here',  # Change this
        'dialect': 'hi',
        'description': 'My custom test'
    }
]
```

Then run:
```bash
python tests/test_voice_output.py
```

## Test Different Voices

Available voices:
- **Hindi/Marathi/Telugu**: Aditi (female, Indian accent)
- **English**: Raveena (female, Indian accent)

To change voices, edit `src/voice/output.py`:

```python
def get_polly_voice(dialect: str) -> Tuple[str, str]:
    voice_map = {
        'hi': ('Aditi', 'hi-IN'),
        'en': ('Raveena', 'en-IN')  # Try 'Kajal' or 'Aria'
    }
```

See all available voices: https://docs.aws.amazon.com/polly/latest/dg/voicelist.html

## Test End-to-End (Requires Real WhatsApp Number)

Since test numbers don't support media:

1. **Send a voice note** to your WhatsApp Business number
2. System will:
   - Transcribe your voice (Transcribe)
   - Process with RAG (Bedrock)
   - Generate voice response (Polly)
   - Send audio back to you

3. **Or enable voice preference**:
   - Update user profile in DynamoDB
   - Set `voicePreference: true`
   - All responses will be voice

## Troubleshooting

### "Audio file not found"
- URLs expire after 1 hour
- Re-run the test to generate new URLs

### "Voice doesn't sound right"
- Aditi/Raveena use standard engine (not neural)
- Quality is good enough for agricultural advice
- Neural voices don't support Hindi/Marathi/Telugu yet

### "Can't play audio"
- Make sure you have an audio player installed
- Try downloading first: `curl 'URL' -o test.mp3`
- Then play: `open test.mp3` (macOS) or `vlc test.mp3` (Linux)

## What Gets Tested

✅ **Polly voice selection** (Aditi for Hindi/Marathi/Telugu, Raveena for English)  
✅ **Text-to-speech generation** (MP3 format)  
✅ **S3 upload** (with presigned URLs)  
✅ **Multi-language support** (4 languages)  
✅ **Audio quality** (standard engine, ~50KB per response)

## Demo Tips

For competition judges:
1. Run test script and show all 4 languages working
2. Play 1-2 audio samples (English + Hindi)
3. Explain: "Voice responses sent automatically when user sends voice note"
4. Show code: `src/voice/output.py` (simple, clean implementation)
5. Mention: "WhatsApp test numbers don't support media, but code is production-ready"
