"""
WhatsApp Webhook Handler
Validates webhook signature and queues messages for async processing
"""
import json
import os
import hmac
import hashlib
import boto3
from typing import Dict, Any

sqs = boto3.client('sqs')
secrets = boto3.client('secretsmanager')

QUEUE_URL = os.environ['QUEUE_URL']
SECRET_NAME = os.environ.get('WHATSAPP_SECRET_NAME', 'agrinexus-whatsapp-dev')


def get_webhook_secret() -> str:
    """Retrieve WhatsApp webhook secret from Secrets Manager"""
    response = secrets.get_secret_value(SecretId=SECRET_NAME)
    secret_data = json.loads(response['SecretString'])
    return secret_data['WEBHOOK_SECRET']


def verify_signature(payload: str, signature: str) -> bool:
    """Verify X-Hub-Signature-256 from WhatsApp"""
    secret = get_webhook_secret()
    expected_signature = 'sha256=' + hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WhatsApp webhook events
    - GET: Webhook verification
    - POST: Message processing
    """
    http_method = event.get('httpMethod', '')
    
    # GET: Webhook verification
    if http_method == 'GET':
        params = event.get('queryStringParameters', {})
        mode = params.get('hub.mode')
        token = params.get('hub.verify_token')
        challenge = params.get('hub.challenge')
        
        verify_token = os.environ['WHATSAPP_VERIFY_TOKEN']
        
        if mode == 'subscribe' and token == verify_token:
            return {
                'statusCode': 200,
                'body': challenge
            }
        else:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Verification failed'})
            }
    
    # POST: Message processing
    elif http_method == 'POST':
        # Verify signature
        signature = event.get('headers', {}).get('X-Hub-Signature-256', '')
        body = event.get('body', '')
        
        if not verify_signature(body, signature):
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Invalid signature'})
            }
        
        # Parse webhook payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid JSON'})
            }
        
        # Extract message data
        entry = payload.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        # Queue each message for async processing
        for message in messages:
            wamid = message.get('id')
            from_number = message.get('from')
            message_type = message.get('type')
            
            # Use wamid as deduplication ID
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({
                    'wamid': wamid,
                    'from': from_number,
                    'type': message_type,
                    'message': message,
                    'metadata': value.get('metadata', {})
                }),
                MessageDeduplicationId=wamid,
                MessageGroupId=from_number
            )
        
        # Always return 200 OK within 2 seconds
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'queued'})
        }
    
    else:
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})
        }
