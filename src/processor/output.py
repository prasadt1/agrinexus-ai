"""
Voice Output Module
Converts text responses to speech using Amazon Polly
"""
import boto3
import os
from typing import Optional, Tuple

polly = boto3.client('polly', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

# Set by SAM at deploy; for local runs set TEMP_AUDIO_BUCKET (no default to avoid leaking account IDs)
TEMP_BUCKET = os.environ.get('TEMP_AUDIO_BUCKET', '')

# Polly TTS length cap (~45–90s typical for hi-IN; tune via env for shorter voice notes)
VOICE_TTS_MAX_CHARS = int(os.environ.get('VOICE_TTS_MAX_CHARS', '700'))


def truncate_for_voice(text: str, max_chars: Optional[int] = None) -> str:
    """
    Shorten text for TTS while preferring sentence boundaries.
    Full reply text should still be sent separately in chat when truncated.
    """
    if max_chars is None:
        max_chars = VOICE_TTS_MAX_CHARS
    text = (text or '').strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in ('।\n', '.\n', '?\n', '!\n', '। ', '. ', '? ', '! ', '।', '\n'):
        idx = cut.rfind(sep)
        if idx >= max_chars // 2:
            return cut[: idx + len(sep)].strip()
    return cut.rstrip() + '…'


def voice_truncation_prefix(dialect: str) -> str:
    """Spoken intro when TTS is shorter than the full text reply."""
    prefixes = {
        'hi': 'पूरा जवाब ऊपर टेक्स्ट में है। संक्षेप में: ',
        'mr': 'पूर्ण उत्तर वर टेक्स्टमध्ये आहे. संक्षेपात: ',
        'te': 'పూర్తి సమాధానం పైన టెక్స్ట్‌లో ఉంది. సంక్షిప్తంగా: ',
        'en': 'The full answer is in the text message above. In brief: ',
    }
    return prefixes.get(dialect, prefixes['en'])


def get_polly_voice(dialect: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Map user dialect to Polly voice, language code, and engine
    
    Supported:
    - Hindi: Aditi (hi-IN) - Native Hindi support ✅
    - English: Kajal (en-IN) - Neural engine required ✅
    - Marathi: Aditi (hi-IN) - Fallback (Marathi farmers understand Hindi) ⚠️
    - Telugu: Text-only (no native voice) ⚠️
    
    Returns: (voice_id, language_code, engine)
    """
    voice_map = {
        'hi': ('Aditi', 'hi-IN', 'standard'),      # Hindi - Native support, standard engine
        'mr': ('Aditi', 'hi-IN', 'standard'),      # Marathi - Use Hindi voice (understood by Marathi speakers)
        'te': (None, None, None),                  # Telugu - No voice support, text only
        'en': ('Kajal', 'en-IN', 'neural')         # English (Indian) - Bilingual neural voice (requires neural engine)
    }
    return voice_map.get(dialect, ('Aditi', 'hi-IN', 'standard'))


def text_to_speech(text: str, dialect: str, phone_number: str) -> Optional[str]:
    """
    Convert text to speech using Amazon Polly
    
    Args:
        text: Text to convert to speech
        dialect: User's dialect (hi, mr, te, en)
        phone_number: User's phone number (for S3 key)
    
    Returns:
        S3 URL of audio file, or None if failed/not supported
    """
    try:
        voice_id, language_code, engine = get_polly_voice(dialect)
        
        # Telugu not supported - return None
        if voice_id is None:
            print(f"Voice output not supported for dialect: {dialect}")
            return None
        
        # Polly limit is 3000 chars for standard API
        if len(text) > 2900:
            text = text[:2900] + '…'

        print(f"Converting text to speech: dialect={dialect}, voice={voice_id}, lang={language_code}, engine={engine}")
        print(f"Text preview: {text[:100]}... ({len(text)} chars)")
        
        # Synthesize speech with appropriate engine
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            LanguageCode=language_code,
            Engine=engine  # 'standard' for Aditi, 'neural' for Kajal
        )
        
        # Upload to S3
        import time
        timestamp = int(time.time())
        s3_key = f"voice-output/{phone_number}/{timestamp}.mp3"
        
        s3.put_object(
            Bucket=TEMP_BUCKET,
            Key=s3_key,
            Body=response['AudioStream'].read(),
            ContentType='audio/mpeg'
        )
        
        # Generate presigned URL (valid for 1 hour)
        audio_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': TEMP_BUCKET, 'Key': s3_key},
            ExpiresIn=3600
        )
        
        print(f"Voice output generated: {audio_url}")
        return audio_url
        
    except Exception as e:
        print(f"Error generating voice output: {e}")
        return None


def should_send_voice_response(user_profile: dict, message: dict = None) -> bool:
    """
    Determine if user should receive voice responses
    
    Criteria:
    - User dialect is Hindi or English (Polly supports these)
    - AND (User has voicePreference enabled OR user sent a voice note)
    
    Note: Marathi uses Hindi voice (understood by Marathi speakers)
    Telugu not supported - text only
    """
    dialect = user_profile.get('dialect', 'en')
    
    # Only enable voice for Hindi, Marathi (Hindi fallback), and English
    if dialect not in ['hi', 'mr', 'en']:
        return False
    
    # Check if user sent voice note
    if message and message.get('_source') == 'voice':
        return True
    
    # Check user preference
    if user_profile.get('voicePreference', False):
        return True
    
    return False
