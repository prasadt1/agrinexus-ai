"""
Web Chat Handler
Provides a public API for text-based queries without phone numbers.
Reuses existing Bedrock RAG logic from processor.
"""
import json
import os
import boto3
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal
import hashlib

dynamodb = boto3.resource('dynamodb')
bedrock_agent = boto3.client('bedrock-agent-runtime')

TABLE_NAME = os.environ['TABLE_NAME']
KB_ID = os.environ['KNOWLEDGE_BASE_ID']
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID', '')
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', '1')
RATE_LIMIT = int(os.environ.get('WEB_RATE_LIMIT', '10'))  # 10 queries per hour
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
    Returns: {'allowed': bool, 'remaining': int, 'reset_at': int}
    """
    now = int(datetime.utcnow().timestamp())
    ttl = now + RATE_LIMIT_WINDOW
    
    # Hash IP for privacy (don't store raw IPs)
    ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    
    try:
        # Try to increment counter atomically
        response = table.update_item(
            Key={
                'PK': f'RATE_LIMIT#{ip_hash}',
                'SK': 'WEB_DEMO'
            },
            UpdateExpression='SET #count = if_not_exists(#count, :zero) + :inc, #ttl = :ttl',
            ExpressionAttributeNames={
                '#count': 'count',
                '#ttl': 'ttl'
            },
            ExpressionAttributeValues={
                ':zero': 0,
                ':inc': 1,
                ':ttl': ttl
            },
            ReturnValues='ALL_NEW'
        )
        
        count = int(response['Attributes']['count'])
        remaining = max(0, RATE_LIMIT - count)
        
        return {
            'allowed': count <= RATE_LIMIT,
            'remaining': remaining,
            'reset_at': ttl
        }
    
    except Exception as e:
        print(f"Rate limit check error: {e}")
        # Fail open (allow request) if rate limiting fails
        return {
            'allowed': True,
            'remaining': RATE_LIMIT,
            'reset_at': ttl
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
        
        # Validate input
        if not message:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Message is required'
                })
            }
        
        if len(message) > 500:
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
        
        # Query Bedrock
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
                'remaining': rate_limit_status['remaining'] - 1,
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
