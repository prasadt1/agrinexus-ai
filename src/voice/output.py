"""
Voice Output Module
Converts text responses to speech using Amazon Polly
"""
import boto3
import os
from typing import Optional, Tuple

polly = boto3.client('polly', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

TEMP_BUCKET = os.environ.get('TEMP_AUDIO_BUCKET', 'agrinexus-temp-audio-dev-043624892076')


def get_polly_voice(dialect: str) -> Tuple[str, str]:
    """
    Map user dialect to Polly voice and language code
    
    Returns: (voice_id, language_code)
    """
    voice_map = {
        'hi': ('Aditi', 'hi-IN'),      # Hindi - Female
        'mr': ('Aditi', 'hi-IN'),      # Marathi - Use Hindi voice (closest)
        'te': ('Aditi', 'hi-IN'),      # Telugu - Use Hindi voice (closest)
        'en': ('Raveena', 'en-IN')     # English (Indian) - Female
    }
    return voice_map.get(dialect, ('Aditi', 'hi-IN'))


def text_to_speech(text: str, dialect: str, phone_number: str) -> Optional[str]:
    """
    Convert text to speech using Amazon Polly
    
    Args:
        text: Text to convert to speech
        dialect: User's dialect (hi, mr, te, en)
        phone_number: User's phone number (for S3 key)
    
    Returns:
        S3 URL of audio file, or None if failed
    """
    try:
        voice_id, language_code = get_polly_voice(dialect)
        
        print(f"Converting text to speech: dialect={dialect}, voice={voice_id}, lang={language_code}")
        print(f"Text preview: {text[:100]}...")
        
        # Synthesize speech
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            LanguageCode=language_code,
            Engine='neural'  # Use neural engine for better quality
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


def should_send_voice_response(user_profile: dict) -> bool:
    """
    Determine if user should receive voice responses
    
    Criteria:
    - User has voicePreference enabled, OR
    - User sent a voice note (indicated by _source: 'voice' in message)
    """
    # Check user preference
    if user_profile.get('voicePreference', False):
        return True
    
    # Default: no voice output unless explicitly requested
    return False
