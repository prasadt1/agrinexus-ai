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
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from common.whatsapp import send_whatsapp_message, VOICE_RECEIVED_ACK
from common.allowlist import is_approved_user, allowlist_expiry_hint

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
secrets = boto3.client('secretsmanager')

QUEUE_URL = os.environ['QUEUE_URL']
QUEUE_URL_BETA = os.environ.get('QUEUE_URL_BETA') or ""
TABLE_NAME = os.environ['TABLE_NAME']
VERIFY_TOKEN_SECRET = os.environ.get('VERIFY_TOKEN_SECRET', 'agrinexus/whatsapp/verify-token')
APP_SECRET_NAME = os.environ.get('APP_SECRET_NAME', 'agrinexus/whatsapp/app-secret')
VERIFY_SIGNATURE = os.environ.get('VERIFY_SIGNATURE', 'true').lower() == 'true'

table = dynamodb.Table(TABLE_NAME)

# Cache for Secrets Manager (5-minute TTL) - reduces API calls significantly
_secrets_cache: Dict[str, Any] = {
    'verify_token': None,
    'app_secret': None,
    'expires_at': None
}
CACHE_TTL_SECONDS = 300

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

# Rate limiting: max messages per user per hour
RATE_LIMIT_MESSAGES = int(os.environ.get('RATE_LIMIT_MESSAGES', '10'))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('RATE_LIMIT_WINDOW_SECONDS', '3600'))


def _rate_limit_globally_disabled() -> bool:
    v = (os.environ.get("RATE_LIMIT_DISABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _rate_limit_bypass_phones() -> set:
    raw = os.environ.get("RATE_LIMIT_BYPASS_PHONES") or ""
    return {p.strip().lstrip("+") for p in raw.split(",") if p.strip()}

def _beta_phones() -> set:
    raw = os.environ.get("BETA_PHONES") or ""
    return {p.strip().lstrip("+") for p in raw.split(",") if p.strip()}

def _select_queue_url(from_number: str) -> str:
    norm = (from_number or "").strip().lstrip("+")
    if QUEUE_URL_BETA and norm and norm in _beta_phones():
        return QUEUE_URL_BETA
    return QUEUE_URL


def check_rate_limit(phone_number: str) -> bool:
    """Count inbound user messages only in the time window.

    Processor `save_message` also writes `SK` under `MSG#...` but includes a `response`
    field; those must not count toward the limit or users hit the cap in ~half as many
    turns as intended.
    """
    if _rate_limit_globally_disabled():
        return True
    norm = (phone_number or "").strip().lstrip("+")
    if norm and norm in _rate_limit_bypass_phones():
        return True
    try:
        now_ts = int(datetime.utcnow().timestamp())
        window_start = now_ts - RATE_LIMIT_WINDOW_SECONDS
        start_iso = datetime.utcfromtimestamp(window_start).isoformat()
        end_iso = datetime.utcnow().isoformat()

        message_count = 0
        query_kwargs: Dict[str, Any] = {
            'KeyConditionExpression': 'PK = :pk AND SK BETWEEN :lo AND :hi',
            # Webhook stream rows have no `response`; assistant saves do.
            'FilterExpression': 'attribute_not_exists(#resp)',
            'ExpressionAttributeNames': {'#resp': 'response'},
            'ExpressionAttributeValues': {
                ':pk': f'USER#{phone_number}',
                ':lo': f'MSG#{start_iso}',
                ':hi': f'MSG#{end_iso}',
            },
            'Select': 'COUNT',
        }
        while True:
            response = table.query(**query_kwargs)
            message_count += response.get('Count', 0)
            if message_count >= RATE_LIMIT_MESSAGES:
                logger.warning(
                    f"Rate limit exceeded for {phone_number}: {message_count} messages in window"
                )
                return False
            lek = response.get('LastEvaluatedKey')
            if not lek:
                break
            query_kwargs['ExclusiveStartKey'] = lek

        return True
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        return True  # Allow on error (fail open)


def should_skip_rag(text: str) -> bool:
    """Check if message contains DONE/NOT YET keywords that should skip RAG"""
    if not text:
        return False
    text_lower = text.lower().strip()
    return any(keyword.lower() in text_lower for keyword in SKIP_RAG_KEYWORDS)


def _refresh_secrets_cache() -> None:
    """Refresh secrets cache if expired"""
    now = datetime.utcnow()
    if _secrets_cache['expires_at'] and now < _secrets_cache['expires_at']:
        return  # Cache still valid

    # Fetch both secrets
    verify_response = secrets.get_secret_value(SecretId=VERIFY_TOKEN_SECRET)
    app_response = secrets.get_secret_value(SecretId=APP_SECRET_NAME)

    _secrets_cache['verify_token'] = verify_response['SecretString']
    _secrets_cache['app_secret'] = app_response['SecretString']
    _secrets_cache['expires_at'] = now + timedelta(seconds=CACHE_TTL_SECONDS)
    logger.info(f"Refreshed secrets cache (TTL: {CACHE_TTL_SECONDS}s)")


def get_verify_token() -> str:
    """Retrieve WhatsApp verify token from Secrets Manager (cached)"""
    _refresh_secrets_cache()
    return _secrets_cache['verify_token']


def get_app_secret() -> str:
    """Retrieve WhatsApp app secret from Secrets Manager (cached)"""
    _refresh_secrets_cache()
    return _secrets_cache['app_secret']


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


def redact_phone(phone: str) -> str:
    """Redact phone number for logging (show only first 3 digits)"""
    if not phone or len(phone) < 3:
        return "***"
    return f"{phone[:3]}***"


def get_user_dialect(phone: str) -> str:
    """Fast PROFILE lookup for localized voice ACK (defaults to hi)."""
    try:
        r = table.get_item(Key={'PK': f'USER#{phone}', 'SK': 'PROFILE'})
        return (r.get('Item') or {}).get('dialect', 'hi') or 'hi'
    except Exception as e:
        logger.warning(f"dialect lookup failed for voice ack: {e}")
        return 'hi'


def send_voice_received_ack(from_number: str) -> None:
    """Immediate feedback before SQS + Voice Lambda (avoids queue/cold-start delay)."""
    try:
        dialect = get_user_dialect(from_number)
        text = VOICE_RECEIVED_ACK.get(dialect, VOICE_RECEIVED_ACK['hi'])
        send_whatsapp_message(from_number, text)
    except Exception as e:
        logger.warning(f"Voice received ack failed (continuing to queue): {e}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WhatsApp webhook events
    - GET: Webhook verification
    - POST: Message processing
    """
    # Reduced logging - only log event structure, not full payload (saves CloudWatch costs)
    logger.info(f"Event received: method={event.get('httpMethod')}, path={event.get('path')}")
    
    # Log the HTTP method (support both API Gateway v1 and v2 formats)
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method')
    logger.info(f"HTTP method: {http_method}")
    
    # GET: Webhook verification
    if http_method == 'GET':
        params = event.get('queryStringParameters') or {}
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
        # Verify signature (case-insensitive header lookup)
        headers = event.get('headers', {})
        signature = headers.get('X-Hub-Signature-256') or headers.get('x-hub-signature-256', '')
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
            # Only log message count, not full payload (saves CloudWatch costs)
            msg_count = len(payload.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', []))
            logger.info(f"Parsed payload: {msg_count} message(s)")
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
            
            logger.info(f"Message - wamid: {wamid}, from: {redact_phone(from_number)}, type: {message_type}")
            
            # Rate limit check
            if not check_rate_limit(from_number):
                logger.warning(f"Rate limit exceeded for {redact_phone(from_number)}, dropping message {wamid}")
                rate_limit_msg = {
                    'hi': 'आपने बहुत सारे संदेश भेजे हैं। कृपया 1 घंटे बाद पुनः प्रयास करें।',
                    'mr': 'तुम्ही खूप संदेश पाठवले आहेत. कृपया 1 तासानंतर पुन्हा प्रयत्न करा.',
                    'te': 'మీరు చాలా సందేశాలు పంపారు. దయచేసి 1 గంట తర్వాత మళ్లీ ప్రయత్నించండి.',
                    'en': 'You have sent too many messages. Please try again in 1 hour.'
                }
                dialect = get_user_dialect(from_number)
                send_whatsapp_message(
                    from_number,
                    rate_limit_msg.get(dialect, rate_limit_msg['hi']),
                )
                continue
            
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
            
            voice_queue_url = os.environ.get('VOICE_QUEUE_URL')
            if message_type == 'audio' and voice_queue_url:
                # Gate expensive voice path for unapproved users (text-only still works)
                if not is_approved_user(table, from_number):
                    dialect = get_user_dialect(from_number)
                    gate_msg = {
                        'hi': f'अभी वॉइस सुविधा बंद है। कृपया टेक्स्ट में प्रश्न भेजें। {allowlist_expiry_hint(dialect)}',
                        'mr': f'सध्या व्हॉइस सुविधा बंद आहे. कृपया प्रश्न टेक्स्टमध्ये पाठवा. {allowlist_expiry_hint(dialect)}',
                        'te': f'ప్రస్తుతం వాయిస్ ఫీచర్ అందుబాటులో లేదు. దయచేసి టెక్స్ట్‌లో ప్రశ్న అడగండి. {allowlist_expiry_hint(dialect)}',
                        'en': f'Voice is not enabled in the public demo. Please ask in text. {allowlist_expiry_hint(dialect)}',
                    }
                    send_whatsapp_message(from_number, gate_msg.get(dialect, gate_msg['en']))
                    continue

                # Before detector write + SQS + Voice Lambda — minimizes perceived ACK delay
                send_voice_received_ack(from_number)

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
                logger.info(f"Message contains DONE/NOT YET keyword - skipping RAG, will be handled by response detector")
                # Don't send to SQS - response detector will handle it via DynamoDB Streams
                continue
            
            # Queue message for processing (FIFO queue requires MessageGroupId and MessageDeduplicationId)
            try:
                target_queue_url = _select_queue_url(from_number)
                sqs.send_message(
                    QueueUrl=target_queue_url,
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
                logger.info(f"Message queued successfully - wamid: {wamid}, beta={target_queue_url == QUEUE_URL_BETA}")
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
