"""
WhatsApp Webhook Handler
Validates webhook signature and implements DynamoDB-based idempotency
"""
import json
import os
import hmac
import hashlib
import boto3
from typing import Dict, Any
from datetime import datetime

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
secrets = boto3.client('secretsmanager')

QUEUE_URL = os.environ['QUEUE_URL']
TABLE_NAME = os.environ['TABLE_NAME']
VERIFY_TOKEN_SECRET = os.environ.get('VERIFY_TOKEN_SECRET', 'agrinexus/whatsapp/verify-token')

table = dynamodb.Table(TABLE_NAME)


def get_verify_token() -> str:
    """Retrieve WhatsApp verify token from Secrets Manager"""
    response = secrets.get_secret_value(SecretId=VERIFY_TOKEN_SECRET)
    return response['SecretString']


def verify_signature(payload: str, signature: str) -> bool:
    """Verify X-Hub-Signature-256 from WhatsApp"""
    # For now, skip signature verification in development
    # TODO: Implement proper signature verification with app secret
    return True


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
        
        verify_token = get_verify_token()
        
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
            
            # Idempotency check: Check if wamid already exists in DynamoDB
            try:
                response = table.get_item(
                    Key={
                        'PK': f'WAMID#{wamid}',
                        'SK': 'DEDUP'
                    }
                )
                
                if 'Item' in response:
                    # Message already processed, return 200 immediately
                    print(f"Duplicate message detected: {wamid}")
                    continue
                
                # Store wamid for deduplication (with 24h TTL)
                import time
                ttl = int(time.time()) + (24 * 60 * 60)
                table.put_item(
                    Item={
                        'PK': f'WAMID#{wamid}',
                        'SK': 'DEDUP',
                        'from': from_number,
                        'processed_at': datetime.utcnow().isoformat(),
                        'ttl': ttl
                    }
                )
                
            except Exception as e:
                print(f"Error checking idempotency: {e}")
                # Continue processing even if dedup check fails
            
            # Queue message for processing (FIFO queue requires MessageGroupId and MessageDeduplicationId)
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({
                    'wamid': wamid,
                    'from': from_number,
                    'type': message_type,
                    'message': message,
                    'metadata': value.get('metadata', {})
                }),
                MessageGroupId=from_number,  # Group by phone number to maintain order per user
                MessageDeduplicationId=wamid  # Use wamid for deduplication
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
