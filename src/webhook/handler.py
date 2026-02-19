"""
WhatsApp Webhook Handler
Validates webhook signature and implements DynamoDB-based idempotency
"""
import json
import os
import hmac
import hashlib
import boto3
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
secrets = boto3.client('secretsmanager')

QUEUE_URL = os.environ['QUEUE_URL']
TABLE_NAME = os.environ['TABLE_NAME']
VERIFY_TOKEN_SECRET = os.environ.get('VERIFY_TOKEN_SECRET', 'agrinexus/whatsapp/verify-token')
APP_SECRET_NAME = os.environ.get('APP_SECRET_NAME', 'agrinexus/whatsapp/app-secret')
VERIFY_SIGNATURE = os.environ.get('VERIFY_SIGNATURE', 'true').lower() == 'true'

table = dynamodb.Table(TABLE_NAME)

# DONE/NOT YET keywords - skip RAG processing for these
SKIP_RAG_KEYWORDS = [
    # Hindi
    'हो गया', 'कर दिया', 'हो गया है', 'कर लिया', 'done', 'completed',
    'अभी नहीं', 'बाद में', 'नहीं किया', 'not yet', 'later',
    # Marathi
    'झाला', 'केला', 'पूर्ण झाला',
    'नाही झाला', 'नंतर', 'अजून नाही',
    # Telugu
    'అయ్యింది', 'చేశాను', 'పూర్తయింది',
    'ఇంకా లేదు', 'తర్వాత', 'చేయలేదు'
]


def should_skip_rag(text: str) -> bool:
    """Check if message contains DONE/NOT YET keywords that should skip RAG"""
    if not text:
        return False
    text_lower = text.lower().strip()
    return any(keyword.lower() in text_lower for keyword in SKIP_RAG_KEYWORDS)


def get_verify_token() -> str:
    """Retrieve WhatsApp verify token from Secrets Manager"""
    response = secrets.get_secret_value(SecretId=VERIFY_TOKEN_SECRET)
    return response['SecretString']


def get_app_secret() -> str:
    """Retrieve WhatsApp app secret from Secrets Manager"""
    response = secrets.get_secret_value(SecretId=APP_SECRET_NAME)
    return response['SecretString']


def verify_signature(payload: str, signature: str) -> bool:
    """Verify X-Hub-Signature-256 from WhatsApp"""
    if not VERIFY_SIGNATURE:
        logger.info("Signature verification disabled via VERIFY_SIGNATURE=false")
        return True
    if not signature:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    try:
        app_secret = get_app_secret()
    except Exception as e:
        logger.error(f"Failed to load app secret: {e}")
        return False

    try:
        provided = signature.replace('sha256=', '')
        expected = hmac.new(
            app_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, provided)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WhatsApp webhook events
    - GET: Webhook verification
    - POST: Message processing
    """
    logger.info(f"Event received: {json.dumps(event)}")
    
    # Log the HTTP method (support both API Gateway v1 and v2 formats)
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method')
    logger.info(f"HTTP method: {http_method}")
    
    # GET: Webhook verification
    if http_method == 'GET':
        params = event.get('queryStringParameters', {})
        mode = params.get('hub.mode')
        token = params.get('hub.verify_token')
        challenge = params.get('hub.challenge')
        
        logger.info(f"Webhook verification request - mode: {mode}, challenge: {challenge}")
        
        verify_token = get_verify_token()
        
        if mode == 'subscribe' and token == verify_token:
            logger.info("Webhook verification successful")
            return {
                'statusCode': 200,
                'body': challenge
            }
        else:
            logger.warning(f"Webhook verification failed - token mismatch")
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Verification failed'})
            }
    
    # POST: Message processing
    elif http_method == 'POST':
        # Verify signature
        signature = event.get('headers', {}).get('X-Hub-Signature-256', '')
        body = event.get('body', '')
        
        logger.info(f"POST request received - body length: {len(body)}")
        
        if not verify_signature(body, signature):
            logger.warning("Signature verification failed")
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Invalid signature'})
            }
        
        # Parse webhook payload
        try:
            payload = json.loads(body)
            logger.info(f"Parsed payload: {json.dumps(payload)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid JSON'})
            }
        
        # Extract message data
        entry = payload.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        logger.info(f"Processing {len(messages)} message(s)")
        
        # Queue each message for async processing
        for message in messages:
            wamid = message.get('id')
            from_number = message.get('from')
            message_type = message.get('type')
            
            logger.info(f"Message - wamid: {wamid}, from: {from_number}, type: {message_type}")
            
            # Idempotency check: Conditional write to avoid race
            try:
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
                    },
                    ConditionExpression='attribute_not_exists(PK)'
                )
                logger.info(f"Stored deduplication record for wamid: {wamid}")
            
            except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                logger.info(f"Duplicate message detected: {wamid} - skipping")
                continue
            except Exception as e:
                logger.error(f"Error checking idempotency: {e}")
                # Continue processing even if dedup check fails
            
            # Store message in DynamoDB for response detector (via DynamoDB Streams)
            import time
            message_ttl = int(time.time()) + (7 * 24 * 60 * 60)  # 7 days
            try:
                table.put_item(
                    Item={
                        'PK': f'USER#{from_number}',
                        'SK': f'MSG#{datetime.utcnow().isoformat()}',
                        'wamid': wamid,
                        'message': message,
                        'ttl': message_ttl
                    }
                )
                logger.info(f"Message stored in DynamoDB for response detector")
            except Exception as e:
                logger.error(f"Error storing message in DynamoDB: {e}")
            
            # Route audio messages to voice processor queue
            if message_type == 'audio':
                logger.info(f"Audio message detected - routing to voice processor")
                try:
                    voice_queue_url = os.environ.get('VOICE_QUEUE_URL')
                    if voice_queue_url:
                        sqs.send_message(
                            QueueUrl=voice_queue_url,
                            MessageBody=json.dumps({
                                'wamid': wamid,
                                'from': from_number,
                                'message': message,
                                'metadata': value.get('metadata', {})
                            }),
                            MessageGroupId=from_number,
                            MessageDeduplicationId=wamid
                        )
                        logger.info(f"Audio message queued for voice processing - wamid: {wamid}")
                        continue
                    else:
                        logger.warning("VOICE_QUEUE_URL not configured - skipping audio message")
                        continue
                except Exception as e:
                    logger.error(f"Error queuing audio message: {e}")
                    continue
            
            # Check if message should skip RAG processing (DONE/NOT YET keywords)
            message_text = ''
            if message_type == 'text':
                message_text = message.get('text', {}).get('body', '')
            
            if should_skip_rag(message_text):
                logger.info(f"Message contains DONE/NOT YET keyword - skipping RAG, will be handled by response detector: {message_text}")
                # Don't send to SQS - response detector will handle it via DynamoDB Streams
                continue
            
            # Queue message for processing (FIFO queue requires MessageGroupId and MessageDeduplicationId)
            try:
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
                logger.info(f"Message queued successfully - wamid: {wamid}")
            except Exception as e:
                logger.error(f"Error queuing message: {e}")
                raise
        
        # Always return 200 OK within 2 seconds
        logger.info("Webhook processing complete - returning 200 OK")
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'queued'})
        }
    
    else:
        logger.warning(f"Method not allowed: {http_method}")
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})
        }
