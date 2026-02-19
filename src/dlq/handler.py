"""
DLQ Handler
Handles failed messages with dialect-aware error responses
"""
import json
import os
import boto3
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb')
secrets = boto3.client('secretsmanager')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)

ERROR_MESSAGES = {
    'hi': 'माफ कीजिए, सिस्टम में तकलीफ है। कृपया थोड़ी देर बाद फिर से कोशिश करें।',
    'mr': 'माफ करा, सिस्टम मध्ये अपघात आला आहे। कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.',
    'te': 'క్షమించండి, సిస్టమ్‌లో సమస్య వచ్చింది. దయచేసి కొంత సమయం తర్వాత మళ్లీ ప్రయత్నించండి.',
    'en': 'Sorry, there was a system error. Please try again in a few moments.'
}


def get_user_dialect(phone_number: str) -> str:
    """Get user's preferred dialect"""
    try:
        response = table.get_item(
            Key={
                'PK': f'USER#{phone_number}',
                'SK': 'PROFILE'
            }
        )
        profile = response.get('Item', {})
        return profile.get('dialect', 'hi')
    except:
        return 'hi'


def send_error_message(phone_number: str, dialect: str):
    """Send error message in user's dialect"""
    import requests
    import time
    
    message = ERROR_MESSAGES.get(dialect, ERROR_MESSAGES['hi'])
    
    # Get WhatsApp credentials
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    phone_id_secret = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')
    
    try:
        access_token_response = secrets.get_secret_value(SecretId=access_token_secret)
        access_token = access_token_response['SecretString']
        
        phone_id_response = secrets.get_secret_value(SecretId=phone_id_secret)
        phone_number_id = phone_id_response['SecretString']
        
        # Send via WhatsApp Business API
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": message}
        }
        
        response = None
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=5)
                if response.status_code < 500 and response.status_code != 429:
                    break
            except requests.RequestException as e:
                print(f"WhatsApp DLQ request error (attempt {attempt + 1}): {e}")
            time.sleep(0.5 * (2 ** attempt))
        
        if response and response.status_code == 200:
            print(f"Error message sent successfully to {phone_number} in {dialect}")
        else:
            status = response.status_code if response else 'no_response'
            text = response.text if response else 'no_response_body'
            print(f"Failed to send error message: {status} - {text}")
    except Exception as e:
        print(f"Exception sending error message to {phone_number}: {str(e)}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle messages from DLQ"""
    for record in event['Records']:
        body = json.loads(record['body'])
        
        from_number = body.get('from')
        if not from_number:
            continue
        
        # Get user's dialect
        dialect = get_user_dialect(from_number)
        
        # Send error message
        send_error_message(from_number, dialect)
    
    return {'statusCode': 200}
