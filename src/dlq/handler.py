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
    'te': 'క్షమించండి, సిస్టమ్‌లో సమస్య వచ్చింది। దయచేసి కొంత సమయం తర్వాత మళ్లీ ప్రయత్నించండి.'
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
    message = ERROR_MESSAGES.get(dialect, ERROR_MESSAGES['hi'])
    
    # TODO: Implement WhatsApp API call
    print(f"Sending error message to {phone_number} in {dialect}: {message}")


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
