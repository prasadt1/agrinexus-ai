"""
Web Chat Handler
Provides a public API for text-based queries and image analysis without phone numbers.
Reuses existing Bedrock RAG logic from processor.
"""
import json
import os
import boto3
import base64
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal
import hashlib
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
bedrock_agent = boto3.client('bedrock-agent-runtime')
bedrock_runtime = boto3.client('bedrock-runtime')

TABLE_NAME = os.environ['TABLE_NAME']
KB_ID = os.environ['KNOWLEDGE_BASE_ID']
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID', '')
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', '1')
RATE_LIMIT = int(os.environ.get('WEB_RATE_LIMIT', '5'))  # 5 queries per hour
RATE_LIMIT_WINDOW = int(os.environ.get('WEB_RATE_LIMIT_WINDOW', '3600'))  # 1 hour

table = dynamodb.Table(TABLE_NAME)


def get_client_ip(event: Dict[str, Any]) -> str:
    """Extract client IP from API Gateway event"""
    # Try X-Forwarded-For first (if behind CloudFront/ALB)
    headers = event.get('headers', {})
    forwarded = headers.get('X-Forwarded-For', headers.get('x-forwarded-for', ''))
    if forwarded:
        return forwarded.split(',')[0].strip()
    
    # Fall back to requestContext
    request_context = event.get('requestContext', {})
    identity = request_context.get('identity', {})
    return identity.get('sourceIp', 'unknown')


def check_rate_limit(ip_address: str) -> Dict[str, Any]:
    """
    Check if IP has exceeded rate limit.
    Returns: {'allowed': bool, 'remaining': int, 'reset_at': int, 'current_count': int}
    """
    now = int(datetime.utcnow().timestamp())
    
    # Hash IP for privacy (don't store raw IPs)
    ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    
    try:
        key = {
            'PK': f'RATE_LIMIT#{ip_hash}',
            'SK': 'WEB_DEMO'
        }

        current_response = table.get_item(Key=key)
        item = current_response.get('Item')

        # New window if missing/expired
        if not item or int(item.get('ttl', 0)) < now:
            reset_at = now + RATE_LIMIT_WINDOW
            table.put_item(
                Item={
                    **key,
                    'count': 1,
                    'ttl': reset_at
                }
            )
            return {
                'allowed': True,
                'remaining': max(0, RATE_LIMIT - 1),
                'reset_at': reset_at,
                'current_count': 1
            }

        current_count = int(item.get('count', 0))
        reset_at = int(item.get('ttl', now + RATE_LIMIT_WINDOW))

        if current_count >= RATE_LIMIT:
            return {
                'allowed': False,
                'remaining': 0,
                'reset_at': reset_at,
                'current_count': current_count
            }

        # Atomic increment; keep existing ttl (fixed window)
        try:
            response = table.update_item(
                Key=key,
                UpdateExpression='SET #count = #count + :inc',
                ConditionExpression='#ttl >= :now AND #count < :limit',
                ExpressionAttributeNames={
                    '#count': 'count',
                    '#ttl': 'ttl'
                },
                ExpressionAttributeValues={
                    ':inc': 1,
                    ':now': now,
                    ':limit': RATE_LIMIT
                },
                ReturnValues='ALL_NEW'
            )
        except ClientError as e:
            # Most common here: ConditionalCheckFailedException (hit limit or window expired)
            code = e.response.get('Error', {}).get('Code', '')
            if code == 'ConditionalCheckFailedException':
                latest = table.get_item(Key=key).get('Item') or {}
                latest_ttl = int(latest.get('ttl', 0) or 0)
                latest_count = int(latest.get('count', 0) or 0)

                # If window expired between read and update, start a new window.
                if latest_ttl < now:
                    reset_at = now + RATE_LIMIT_WINDOW
                    table.put_item(
                        Item={
                            **key,
                            'count': 1,
                            'ttl': reset_at
                        }
                    )
                    return {
                        'allowed': True,
                        'remaining': max(0, RATE_LIMIT - 1),
                        'reset_at': reset_at,
                        'current_count': 1
                    }

                return {
                    'allowed': False,
                    'remaining': 0,
                    'reset_at': latest_ttl or reset_at,
                    'current_count': latest_count
                }
            raise

        new_count = int(response['Attributes']['count'])
        return {
            'allowed': True,
            'remaining': max(0, RATE_LIMIT - new_count),
            'reset_at': reset_at,
            'current_count': new_count
        }
    
    except Exception as e:
        print(f"Rate limit check error: {e}")
        # Fail closed (deny request) if rate limiting fails
        return {
            'allowed': False,
            'remaining': 0,
            'reset_at': now + RATE_LIMIT_WINDOW,
            'current_count': RATE_LIMIT
        }


def query_bedrock(query: str, dialect: str = 'en') -> Dict[str, Any]:
    """
    Query Bedrock Knowledge Base with RAG (reused from processor)
    
    Args:
        query: User's question
        dialect: Language (en, hi, mr, te)
    
    Returns:
        Dict with 'text' and 'citations'
    """
    # Map dialect to language instruction
    language_instructions = {
        'hi': 'Respond in Hindi (Devanagari script). Use simple, practical language.',
        'mr': 'Respond in Marathi (Devanagari script). Use simple, practical language.',
        'te': 'Respond in Telugu script. Use simple, practical language.',
        'en': 'Respond in English. Use simple, practical language suitable for Indian farmers.'
    }
    
    language_instruction = language_instructions.get(dialect, language_instructions['en'])
    
    # Build generation configuration
    generation_config = {
        'promptTemplate': {
            'textPromptTemplate': f'''You are an agricultural extension agent helping smallholder farmers in India with FARMING questions ONLY.
{language_instruction}

RESPONSE STYLE (very important):
- Sound like a calm, practical TV or radio farm advisory (DD Kisan / extension bulletin style): direct and trustworthy, not a research paper.
- Lead with the ACTION the farmer should take first — not long background.
- Main answer: at most 2-3 short sentences. For simple when / how much / what questions, give the direct answer in one or two sentences first.
- Add at most one short sentence for "why" or "what to watch" only if it changes what they should do.
- Use everyday words; if a technical term is needed, explain it in a few words.
- Avoid long paragraphs, dense lists, and copying long passages from the context.
- End with exactly ONE final line for traceability: Look at the search_results metadata and extract the actual document name or source title. Write a single compact line starting with "Source:" (or "स्रोत:" in Hindi, "स्त्रोत:" in Marathi, "మూలం:" in Telugu) followed by the actual document name from the metadata (e.g., "Source: FAO Cotton IPM Guide" or "स्रोत: ICAR कीट प्रबंधन सलाह"). Do NOT just write "Source: 1" or "स्रोत: 1".

IMPORTANT RESTRICTIONS:
- ONLY answer questions about agriculture, farming, crops, pests, diseases, fertilizers, weather, and farm management
- If the question is about human health, medical issues, personal problems, or non-farming topics, respond: "I can only help with farming questions. Please ask about crops, pests, fertilizers, or farm management."
- Do NOT provide medical advice, health recommendations, or personal counseling
- Stay strictly within agricultural domain

Question: $query$

Context: $search_results$

Answer using the style rules above. Ground every claim in the context; if the context is insufficient, say so briefly and suggest contacting the local KVK or a qualified adviser.'''
        }
    }
    
    # Only add guardrail if configured
    if GUARDRAIL_ID and GUARDRAIL_ID.strip():
        generation_config['guardrailConfiguration'] = {
            'guardrailId': GUARDRAIL_ID,
            'guardrailVersion': GUARDRAIL_VERSION
        }
    
    # Get model ARN from environment
    model_arn = os.environ.get(
        'MODEL_ARN',
        'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
    )
    
    # Build retrieve_and_generate configuration
    rag_config = {
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': KB_ID,
            'modelArn': model_arn,
            'generationConfiguration': generation_config
        }
    }
    
    # Call Bedrock (no session ID for web demo - stateless)
    response = bedrock_agent.retrieve_and_generate(
        input={'text': query},
        retrieveAndGenerateConfiguration=rag_config
    )
    
    return {
        'text': response['output']['text'],
        'citations': response.get('citations', [])
    }


def analyze_image(image_base64: str, dialect: str = 'en') -> str:
    """
    Analyze crop image using Claude 3 Sonnet vision
    
    Args:
        image_base64: Base64 encoded image (with or without data URI prefix)
        dialect: Language for response
    
    Returns:
        Analysis text
    """
    # Detect media type from data URI (if present)
    raw = image_base64
    media_type = "image/jpeg"
    if raw.startswith('data:image/'):
        if raw.startswith('data:image/png'):
            media_type = "image/png"
        elif raw.startswith('data:image/webp'):
            media_type = "image/webp"
        elif raw.startswith('data:image/gif'):
            media_type = "image/gif"
        elif raw.startswith('data:image/jpeg') or raw.startswith('data:image/jpg'):
            media_type = "image/jpeg"

    # Remove data URI prefix if present
    if ',' in raw:
        image_base64 = raw.split(',')[1]
    
    # Language-specific prompts
    prompts = {
        'hi': '''आप एक कृषि विशेषज्ञ हैं जो भारतीय किसानों की मदद करते हैं। इस तस्वीर को देखें और बताएं:

1. यह कौन सी फसल है?
2. पौधे की स्वास्थ्य स्थिति कैसी है?
3. क्या कोई कीट, रोग या पोषण की कमी दिखाई दे रही है?
4. क्या सुधार की सलाह देंगे?

संक्षिप्त और व्यावहारिक जवाब दें। अगर तस्वीर में फसल नहीं है, तो बताएं कि आप क्या देख रहे हैं।''',
        'mr': '''तुम्ही भारतीय शेतकऱ्यांना मदत करणारे शेती तज्ञ आहात. हा फोटो पहा आणि सांगा:

1. हे कोणते पीक आहे?
2. रोपाची आरोग्य स्थिती कशी आहे?
3. काही किडे, रोग किंवा पोषणाची कमतरता दिसते का?
4. काय सुधारणा सुचवाल?

संक्षिप्त आणि व्यावहारिक उत्तर द्या. फोटोमध्ये पीक नसेल तर काय दिसतंय ते सांगा.''',
        'te': '''మీరు భారతీయ రైతులకు సహాయం చేసే వ్యవసాయ నిపుణులు. ఈ ఫోటోను చూసి చెప్పండి:

1. ఇది ఏ పంట?
2. మొక్క ఆరోగ్య స్థితి ఎలా ఉంది?
3. ఏదైనా పురుగులు, వ్యాధులు లేదా పోషకాహార లోపం కనిపిస్తుందా?
4. ఏ మెరుగుదల సూచిస్తారు?

సంక్షిప్త మరియు ఆచరణాత్మక సమాధానం ఇవ్వండి. ఫోటోలో పంట లేకపోతే, మీకు ఏమి కనిపిస్తుందో చెప్పండి.''',
        'en': '''You are an agricultural expert helping Indian farmers. Look at this image and tell me:

1. What crop is this?
2. What is the plant's health status?
3. Are there any pests, diseases, or nutrient deficiencies visible?
4. What improvements would you recommend?

Provide a brief and practical answer. If the image doesn't show a crop, describe what you see.'''
    }
    
    prompt = prompts.get(dialect, prompts['en'])
    
    # Call Claude 3 Sonnet with vision
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    try:
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    except Exception as e:
        print(f"Error analyzing image: {e}")
        # Return a helpful error message
        error_messages = {
            'hi': 'क्षमा करें, तस्वीर का विश्लेषण करने में समस्या हुई। कृपया फिर से प्रयास करें या एक अलग तस्वीर अपलोड करें।',
            'mr': 'माफ करा, फोटोचे विश्लेषण करताना समस्या आली. कृपया पुन्हा प्रयत्न करा किंवा वेगळा फोटो अपलोड करा.',
            'te': 'క్షమించండి, ఫోటో విశ్లేషణలో సమస్య వచ్చింది. దయచేసి మళ్లీ ప్రయత్నించండి లేదా వేరే ఫోటో అప్‌లోడ్ చేయండి.',
            'en': 'Sorry, there was a problem analyzing the image. Please try again or upload a different image.'
        }
        return error_messages.get(dialect, error_messages['en'])


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle web chat API requests
    
    Expected input:
    {
        "message": "How to control cotton pests?",
        "language": "en"
    }
    
    Returns:
    {
        "reply": "To control cotton pests...",
        "citations": [...],
        "remaining": 9
    }
    """
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',  # Restrict to your domain in production
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
    }
    
    # Handle OPTIONS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        message = body.get('message', '').strip()
        language = body.get('language', 'en')
        image = body.get('image')  # Base64 encoded image
        
        # Validate input
        if not message and not image:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Message or image is required'
                })
            }
        
        if message and len(message) > 500:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Message too long (max 500 characters)'
                })
            }
        
        if language not in ['en', 'hi', 'mr', 'te']:
            language = 'en'
        
        # Check rate limit
        client_ip = get_client_ip(event)
        rate_limit_status = check_rate_limit(client_ip)
        
        if not rate_limit_status['allowed']:
            return {
                'statusCode': 429,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Rate limit exceeded. Please try again later.',
                    'remaining': 0,
                    'reset_at': rate_limit_status['reset_at']
                })
            }
        
        # Process image if provided
        if image:
            print(f"Processing image analysis request")
            analysis = analyze_image(image, language)
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'reply': analysis,
                    'citations': ['Vision Analysis'],
                    'remaining': rate_limit_status['remaining'],
                    'reset_at': rate_limit_status['reset_at']
                })
            }
        
        # Query Bedrock for text
        result = query_bedrock(message, language)
        
        # Format citations
        citations = []
        for citation in result.get('citations', []):
            retrieved_refs = citation.get('retrievedReferences', [])
            for ref in retrieved_refs:
                location = ref.get('location', {})
                s3_location = location.get('s3Location', {})
                uri = s3_location.get('uri', '')
                if uri:
                    # Extract filename from S3 URI
                    filename = uri.split('/')[-1]
                    citations.append(filename)
        
        # Return response
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'reply': result['text'],
                'citations': list(set(citations)),  # Deduplicate
                'remaining': rate_limit_status['remaining'],
                'reset_at': rate_limit_status['reset_at']
            })
        }
    
    except Exception as e:
        print(f"Error processing request: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error. Please try again.'
            })
        }
