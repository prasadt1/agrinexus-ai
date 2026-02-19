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

transcribe = boto3.client('transcribe')
s3 = boto3.client('s3')
secrets = boto3.client('secretsmanager')
sqs = boto3.client('sqs')

TEMP_BUCKET = os.environ['TEMP_AUDIO_BUCKET']
QUEUE_URL = os.environ['QUEUE_URL']
TABLE_NAME = os.environ['TABLE_NAME']
ACCESS_TOKEN_SECRET = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
PHONE_NUMBER_ID_SECRET = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


def get_whatsapp_credentials():
    """Get WhatsApp credentials from Secrets Manager"""
    token_response = secrets.get_secret_value(SecretId=ACCESS_TOKEN_SECRET)
    phone_response = secrets.get_secret_value(SecretId=PHONE_NUMBER_ID_SECRET)
    return token_response['SecretString'], phone_response['SecretString']


def send_whatsapp_message(to: str, message: str):
    """Send WhatsApp message"""
    access_token, phone_number_id = get_whatsapp_credentials()
    
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read())


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
    except:
        return 0.0


def process_voice_note(message: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Process incoming WhatsApp voice note"""
    phone = message['from']
    audio_id = message['audio']['id']
    timestamp = message['timestamp']
    dialect = user_profile.get('dialect', 'hi')
    
    print(f"Processing voice note from {phone}, audio_id: {audio_id}")
    
    try:
        # 1. Download audio from WhatsApp
        print("Downloading audio from WhatsApp...")
        audio_url = get_whatsapp_media_url(audio_id)
        audio_bytes = download_media(audio_url)
        print(f"Downloaded {len(audio_bytes)} bytes")
        
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
        
        # 4. Poll for result (max 60 seconds for voice notes)
        for attempt in range(60):
            time.sleep(1)
            result = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            status = result['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                # Get transcript
                transcript_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
                req = urllib.request.Request(transcript_uri)
                with urllib.request.urlopen(req) as response:
                    transcript_data = json.loads(response.read())
                
                transcript_text = transcript_data['results']['transcripts'][0]['transcript']
                confidence = get_average_confidence(transcript_data)
                
                print(f"Transcription complete: '{transcript_text}' (confidence: {confidence:.2f})")
                
                # 5. Cleanup
                s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
                transcribe.delete_transcription_job(TranscriptionJobName=job_name)
                
                if confidence >= 0.5:
                    return {
                        'success': True,
                        'text': transcript_text,
                        'confidence': confidence,
                        'source': 'voice'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'low_confidence',
                        'confidence': confidence,
                        'text': transcript_text
                    }
            
            elif status == 'FAILED':
                print(f"Transcription failed: {result}")
                # Cleanup
                s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
                return {'success': False, 'error': 'transcription_failed'}
        
        # Timeout
        print("Transcription timeout")
        s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
        transcribe.delete_transcription_job(TranscriptionJobName=job_name)
        return {'success': False, 'error': 'timeout'}
    
    except Exception as e:
        print(f"Error processing voice note: {e}")
        return {'success': False, 'error': str(e)}


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
                    'hi': 'माफ़ करें, आवाज़ बहुत लंबी है। कृपया छोटा संदेश भेजें या टाइप करें।',
                    'mr': 'माफ करा, आवाज खूप लांब आहे. कृपया लहान संदेश पाठवा किंवा टाइप करा.',
                    'te': 'క్షమించండి, వాయిస్ చాలా పొడవుగా ఉంది. దయచేసి చిన్న సందేశం పంపండి లేదా టైప్ చేయండి.',
                    'en': 'Sorry, the voice note is too long. Please send a shorter message or type.'
                }
            }
            
            error_type = result.get('error', 'transcription_failed')
            error_msg = error_messages.get(error_type, error_messages['transcription_failed'])
            send_whatsapp_message(from_number, error_msg.get(dialect, error_msg['hi']))
    
    return {'statusCode': 200}
