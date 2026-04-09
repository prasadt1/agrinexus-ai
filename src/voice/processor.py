"""
Voice Processor
Handles WhatsApp voice notes using Amazon Transcribe
"""
import json
import os
import boto3
import time
import urllib.request
from typing import Dict, Any, Optional
from common.whatsapp import get_whatsapp_credentials, send_whatsapp_message

transcribe = boto3.client('transcribe')
s3 = boto3.client('s3')
sqs = boto3.client('sqs')

TEMP_BUCKET = os.environ['TEMP_AUDIO_BUCKET']
QUEUE_URL = os.environ['QUEUE_URL']
TABLE_NAME = os.environ['TABLE_NAME']
# WhatsApp voice notes are typically small; cap to avoid runaway Transcribe cost
VOICE_INPUT_MAX_BYTES = int(os.environ.get('VOICE_INPUT_MAX_BYTES', str(5 * 1024 * 1024)))
# Max time to poll Transcribe (Lambda timeout is 90s; leave margin for download + queue)
TRANSCRIBE_MAX_POLL_SEC = float(os.environ.get('TRANSCRIBE_MAX_POLL_SEC', '78'))

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


def get_whatsapp_media_url(media_id: str) -> str:
    """Get media URL from WhatsApp"""
    access_token, _ = get_whatsapp_credentials()
    
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        return data['url']


def download_media(media_url: str) -> bytes:
    """Download media from WhatsApp"""
    access_token, _ = get_whatsapp_credentials()
    
    headers = {"Authorization": f"Bearer {access_token}"}
    req = urllib.request.Request(media_url, headers=headers)
    
    with urllib.request.urlopen(req) as response:
        return response.read()


def get_transcribe_language(dialect: str) -> str:
    """Map user dialect to Transcribe language code"""
    mapping = {
        'hi': 'hi-IN',
        'mr': 'mr-IN',
        'te': 'te-IN',
        'en': 'en-IN',
    }
    return mapping.get(dialect, 'hi-IN')


def get_average_confidence(transcript_data: Dict) -> float:
    """Calculate average confidence from transcript"""
    try:
        items = transcript_data['results']['items']
        confidences = [
            float(item['alternatives'][0]['confidence'])
            for item in items
            if 'confidence' in item.get('alternatives', [{}])[0]
        ]
        return sum(confidences) / len(confidences) if confidences else 0.0
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


def _finalize_transcription(
    result: Dict[str, Any], job_name: str, s3_key: str
) -> Dict[str, Any]:
    """Download transcript JSON, score confidence, cleanup S3 + Transcribe job."""
    transcript_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
    req = urllib.request.Request(transcript_uri)
    with urllib.request.urlopen(req) as response:
        transcript_data = json.loads(response.read())
    transcript_text = transcript_data['results']['transcripts'][0]['transcript']
    confidence = get_average_confidence(transcript_data)
    print(f"Transcription complete: '{transcript_text}' (confidence: {confidence:.2f})")
    s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
    transcribe.delete_transcription_job(TranscriptionJobName=job_name)
    if confidence >= 0.5:
        return {'success': True, 'text': transcript_text, 'confidence': confidence, 'source': 'voice'}
    return {
        'success': False,
        'error': 'low_confidence',
        'confidence': confidence,
        'text': transcript_text
    }


def process_voice_note(message: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Process incoming WhatsApp voice note"""
    phone = message['from']
    audio_id = message['audio']['id']
    timestamp = message['timestamp']
    dialect = user_profile.get('dialect', 'hi')
    
    print(f"Processing voice note from {phone}, audio_id: {audio_id}")
    
    try:
        # Voice "received" ACK is sent in webhook handler (before SQS) for minimal delay.

        # 1. Download audio from WhatsApp
        print("Downloading audio from WhatsApp...")
        audio_url = get_whatsapp_media_url(audio_id)
        audio_bytes = download_media(audio_url)
        print(f"Downloaded {len(audio_bytes)} bytes")
        if len(audio_bytes) > VOICE_INPUT_MAX_BYTES:
            return {'success': False, 'error': 'voice_too_large'}
        
        # 2. Upload to S3
        s3_key = f"voice/{phone}/{timestamp}.ogg"
        s3.put_object(Bucket=TEMP_BUCKET, Key=s3_key, Body=audio_bytes, ContentType='audio/ogg')
        print(f"Uploaded to S3: s3://{TEMP_BUCKET}/{s3_key}")
        
        # 3. Start transcription
        job_name = f"agrinexus-{phone}-{timestamp}".replace('+', '')
        language_code = get_transcribe_language(dialect)
        
        print(f"Starting transcription job: {job_name}, language: {language_code}")
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': f's3://{TEMP_BUCKET}/{s3_key}'},
            MediaFormat='ogg',
            LanguageCode=language_code,
            Settings={
                'ShowSpeakerLabels': False
            }
        )

        # 4. Poll until COMPLETED/FAILED or TRANSCRIBE_MAX_POLL_SEC (Transcribe can take 60s+ when busy)
        poll_start = time.monotonic()
        attempt = 0
        result = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = result['TranscriptionJob']['TranscriptionJobStatus']
        print(f"Transcription status: {status} (elapsed: 0s, first poll)")

        if status == 'COMPLETED':
            return _finalize_transcription(result, job_name, s3_key)
        if status == 'FAILED':
            print(f"Transcription failed: {result}")
            s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
            return {'success': False, 'error': 'transcription_failed'}

        while True:
            elapsed = int(time.monotonic() - poll_start)
            if elapsed >= TRANSCRIBE_MAX_POLL_SEC:
                break
            wait_time = 1 if attempt < 10 else 2
            remaining = TRANSCRIBE_MAX_POLL_SEC - elapsed
            if remaining <= 0:
                break
            time.sleep(min(wait_time, remaining))
            attempt += 1
            result = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            status = result['TranscriptionJob']['TranscriptionJobStatus']
            elapsed = int(time.monotonic() - poll_start)
            print(f"Transcription status: {status} (elapsed: {elapsed}s)")

            if status == 'COMPLETED':
                return _finalize_transcription(result, job_name, s3_key)
            if status == 'FAILED':
                print(f"Transcription failed: {result}")
                s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
                return {'success': False, 'error': 'transcription_failed'}

        # Timeout — Transcribe still IN_PROGRESS; cleanup without failing on delete
        print("Transcription timeout (poll budget exhausted)")
        try:
            s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
        except Exception as ex:
            print(f"S3 delete after timeout: {ex}")
        try:
            transcribe.delete_transcription_job(TranscriptionJobName=job_name)
        except Exception as ex:
            print(f"DeleteTranscriptionJob after timeout (ignored): {ex}")
        return {'success': False, 'error': 'timeout'}
    
    except Exception as e:
        print(f"Error processing voice note: {e}")
        # Avoid returning raw exception strings (breaks error_messages lookup in lambda_handler)
        return {'success': False, 'error': 'transcription_failed'}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process voice notes from SQS"""
    for record in event['Records']:
        body = json.loads(record['body'])
        
        wamid = body['wamid']
        from_number = body['from']
        message = body['message']
        
        # Get user profile
        response = table.get_item(
            Key={
                'PK': f'USER#{from_number}',
                'SK': 'PROFILE'
            }
        )
        user_profile = response.get('Item', {})
        dialect = user_profile.get('dialect', 'hi')
        
        # Process voice note
        result = process_voice_note(message, user_profile)
        
        if result['success']:
            # Queue transcribed text for normal processing
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({
                    'wamid': wamid,
                    'from': from_number,
                    'type': 'text',  # Treat as text message
                    'message': {
                        'from': from_number,
                        'id': wamid,
                        'timestamp': message['timestamp'],
                        'type': 'text',
                        'text': {'body': result['text']},
                        '_source': 'voice',  # Mark as voice-originated
                        '_confidence': result['confidence']
                    },
                    'metadata': body.get('metadata', {})
                }),
                MessageGroupId=from_number,
                MessageDeduplicationId=f"{wamid}-transcribed"
            )
            print(f"Queued transcribed text for processing: {result['text']}")
        else:
            # Send error message
            error_messages = {
                'low_confidence': {
                    'hi': f"माफ़ करें, आपकी आवाज़ साफ़ नहीं सुनाई दी। कृपया फिर से बोलें या टाइप करें।\n\n(सुना गया: {result.get('text', '')})",
                    'mr': f"माफ करा, तुमचा आवाज स्पष्ट ऐकू आला नाही. कृपया पुन्हा बोला किंवा टाइप करा.\n\n(ऐकले: {result.get('text', '')})",
                    'te': f"క్షమించండి, మీ వాయిస్ స్పష్టంగా వినబడలేదు. దయచేసి మళ్లీ చెప్పండి లేదా టైప్ చేయండి.\n\n(విన్నది: {result.get('text', '')})",
                    'en': f"Sorry, your voice wasn't clear. Please speak again or type your message.\n\n(Heard: {result.get('text', '')})"
                },
                'transcription_failed': {
                    'hi': 'माफ़ करें, आवाज़ को समझने में समस्या हुई। कृपया टाइप करें।',
                    'mr': 'माफ करा, आवाज समजण्यात अडचण आली. कृपया टाइप करा.',
                    'te': 'క్షమించండి, వాయిస్ అర్థం చేసుకోవడంలో సమస్య. దయచేసి టైప్ చేయండి.',
                    'en': 'Sorry, there was a problem understanding your voice. Please type your message.'
                },
                'timeout': {
                    'hi': 'माफ़ करें, आवाज़ को समझने में समय ज़्यादा लगा। कृपया छोटा वॉइस नोट भेजें या टाइप करें।',
                    'mr': 'माफ करा, आवाज ओळखण्यास वेळ जास्त लागला. कृपया लहान व्हॉइस नोट पाठवा किंवा टाइप करा.',
                    'te': 'క్షమించండి, వాయిస్ ప్రాసెస్ చేయడానికి సమయం ఎక్కువ పట్టింది. దయచేసి చిన్న నోట్ పంపండి లేదా టైప్ చేయండి.',
                    'en': 'Sorry, voice processing took too long. Please send a shorter voice note or type your question.'
                },
                'voice_too_large': {
                    'hi': 'माफ़ करें, आवाज़ फ़ाइल बहुत बड़ी है। कृपया छोटा वॉइस नोट भेजें या टाइप करें।',
                    'mr': 'माफ करा, आवाज फाइल खूप मोठी आहे. कृपया लहान व्हॉइस नोट पाठवा किंवा टाइप करा.',
                    'te': 'క్షమించండి, వాయిస్ ఫైల్ చాలా పెద్దది. దయచేసి చిన్న వాయిస్ నోట్ పంపండి లేదా టైప్ చేయండి.',
                    'en': 'Sorry, this voice file is too large. Please send a shorter voice note or type your message.'
                }
            }
            
            error_type = result.get('error', 'transcription_failed')
            if error_type not in error_messages:
                error_type = 'transcription_failed'
            error_msg = error_messages[error_type]
            send_whatsapp_message(from_number, error_msg.get(dialect, error_msg['hi']))
    
    return {'statusCode': 200}
