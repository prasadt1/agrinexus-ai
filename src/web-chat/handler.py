"""
Web Chat Handler
Provides a public API for text-based queries and image analysis without phone numbers.
Reuses existing Bedrock RAG logic from processor.
"""
import json
import os
import re
import logging
import boto3
import base64
from typing import Dict, Any, List, Tuple
from datetime import datetime
from decimal import Decimal
import hashlib
from botocore.exceptions import ClientError
from common.guardrail_reply import (
    KB_NO_ANSWER_MARKER,
    KB_NOT_FARMING_MARKER,
    LOCALIZED_NO_ANSWER,
    LOCALIZED_REFUSAL,
    apply_kb_no_answer,
    apply_localized_guardrail_reply,
)
from common.advice_filter import filter_advice, is_pesticide_question, pesticide_policy
from common.source_line import strip_source_lines
from common.source_labels import source_labels

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
bedrock_agent = boto3.client('bedrock-agent-runtime')
bedrock_runtime = boto3.client('bedrock-runtime')

TABLE_NAME = os.environ['TABLE_NAME']
KB_ID = os.environ['KNOWLEDGE_BASE_ID']
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID', '')
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', '1')
RATE_LIMIT = int(os.environ.get('WEB_RATE_LIMIT', '5'))  # 5 queries per hour
RATE_LIMIT_WINDOW = int(os.environ.get('WEB_RATE_LIMIT_WINDOW', '3600'))  # 1 hour
BEDROCK_MODEL_ID = os.environ.get(
    'BEDROCK_MODEL_ID',
    'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
)
WEB_IMAGE_MAX_BYTES = int(os.environ.get('WEB_IMAGE_MAX_BYTES', str(5 * 1024 * 1024)))
WEB_MAX_IMAGES = int(os.environ.get('WEB_MAX_IMAGES', '1'))

table = dynamodb.Table(TABLE_NAME)


def _bedrock_model_arn() -> str:
    """Build modelArn for RetrieveAndGenerate from BEDROCK_MODEL_ID."""
    mid = BEDROCK_MODEL_ID
    if mid.startswith('arn:'):
        return mid
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1'
    account = os.environ.get('ACCOUNT_ID', '')
    if mid.startswith(('us.', 'eu.', 'ap.', 'global.', 'jp.', 'au.', 'ca.')):
        return f'arn:aws:bedrock:{region}:{account}:inference-profile/{mid}'
    return f'arn:aws:bedrock:{region}::foundation-model/{mid}'

def is_rag_refusal_response(text: str) -> bool:
    """
    Detect KB no-hit / refusal replies. If the model refused or stated it lacks KB
    context, we should NOT present citations (even generic).
    """
    t = (text or "").strip()
    if not t:
        return True
    if t in (*LOCALIZED_NO_ANSWER.values(), *LOCALIZED_REFUSAL.values()):
        return True
    if KB_NO_ANSWER_MARKER in t or KB_NOT_FARMING_MARKER in t:
        return True
    low = t.lower()
    # English refusals from prompt rules
    if "i don't have information about this in my knowledge base" in low:
        return True
    if "i can only help with farming questions" in low:
        return True
    # Common Hindi patterns observed in prod logs
    if "मेरे पास" in t and ("जानकारी नहीं" in t or "जानकारी नही" in t):
        return True
    if "कृषि" in t and ("सिर्फ" in t and "सवाल" in t):
        return True
    # Marathi (both spellings of ज्ञानकोश appear in model output)
    if ("ज्ञानकोषात" in t or "ज्ञानकोशात" in t) and "नाही" in t:
        return True
    if "माझ्याकडे" in t and "माहिती नाही" in t:
        return True
    return False


def strip_llm_xml_citation_tags(text: str) -> str:
    """Remove inline XML-style citation leaks (e.g. <source>2</source>) from model output."""
    if not text:
        return text
    text = re.sub(r"(?is)<\s*source\b[^>]*>.*?</\s*source\s*>", "", text)
    text = re.sub(r"(?is)<\s*sources\b[^>]*>.*?</\s*sources\s*>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def strip_all_numeric_source_footers(text: str) -> str:
    """
    Strip model-added placeholder footers like:
    - "Source: 3"
    - "स्रोत: 3, 4"
    - "మూలం: 1"
    """
    if not text:
        return text
    # Match any of the labels with digits/commas/spaces after optional colon.
    labels = [
        "Source", "source",
        "स्रोत", "स्त्रोत",
        "మూలం",
    ]
    out = text.rstrip()
    for lb in labels:
        pattern = rf"(?:\n\s*)*{re.escape(lb)}\s*:?\s*[\d,\s]+$"
        out = re.sub(pattern, "", out, flags=re.MULTILINE).rstrip()
    return out


def effective_dialect(message: str, ui_language: str) -> str:
    """
    Use UI language when set to a non-English locale. If UI is English but the
    message is clearly in another script, infer dialect so prompts match the
    question (retrieval still uses the same query text).
    """
    lang = (ui_language or 'en').strip().lower()
    if lang not in ('en', 'hi', 'mr', 'te'):
        lang = 'en'
    if lang != 'en':
        return lang
    text = (message or '').strip()
    if not text:
        return 'en'
    if re.search(r'[\u0900-\u097F]', text):
        return 'hi'
    if re.search(r'[\u0C00-\u0C7F]', text):
        return 'te'
    return 'en'


def get_client_ip(event: Dict[str, Any]) -> str:
    """Client IP from API Gateway identity — never trust X-Forwarded-For (client-controlled)."""
    request_context = event.get('requestContext', {}) or {}
    identity = request_context.get('identity', {}) or {}
    return identity.get('sourceIp') or 'unknown'


def _decode_image_payload(raw: str) -> Tuple[str, str, bytes]:
    """
    Return (media_type, base64_payload, raw_bytes) for a data-URI or bare base64 image.
    Raises ValueError on invalid / oversized input.
    """
    media_type = "image/jpeg"
    payload = raw
    if raw.startswith('data:image/'):
        header, _, rest = raw.partition(',')
        payload = rest
        if 'image/png' in header:
            media_type = "image/png"
        elif 'image/webp' in header:
            media_type = "image/webp"
        elif 'image/gif' in header:
            media_type = "image/gif"
        elif 'image/jpeg' in header or 'image/jpg' in header:
            media_type = "image/jpeg"
    elif ',' in raw:
        payload = raw.split(',', 1)[1]

    try:
        raw_bytes = base64.b64decode(payload, validate=False)
    except Exception as e:
        raise ValueError(f"Invalid base64 image: {e}") from e

    if len(raw_bytes) > WEB_IMAGE_MAX_BYTES:
        raise ValueError(
            f"Image too large ({len(raw_bytes)} bytes; max {WEB_IMAGE_MAX_BYTES})"
        )
    if not raw_bytes:
        raise ValueError("Empty image payload")
    return media_type, payload, raw_bytes


def collect_images(body: Dict[str, Any]) -> List[str]:
    """Gather image fields from the request; enforce per-request count cap."""
    images: List[str] = []
    if body.get('image'):
        images.append(str(body['image']))
    extra = body.get('images')
    if isinstance(extra, list):
        images.extend(str(x) for x in extra if x)
    elif extra:
        images.append(str(extra))

    if len(images) > WEB_MAX_IMAGES:
        raise ValueError(
            f"Too many images ({len(images)}); max {WEB_MAX_IMAGES} per request"
        )
    return images

def _peek_rate_limit(identifier: str) -> Dict[str, Any]:
    """
    Read-only rate limit check (no increments).
    Returns same shape as check_rate_limit(): allowed/remaining/reset_at/current_count.
    """
    now = int(datetime.utcnow().timestamp())
    ident_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]

    key = {
        'PK': f'RATE_LIMIT#{ident_hash}',
        'SK': 'WEB_DEMO'
    }

    try:
        item = table.get_item(Key=key).get('Item') or {}
        ttl = int(item.get('ttl', 0) or 0)
        count = int(item.get('count', 0) or 0)

        # Missing/expired -> fresh window, but don't create it here.
        if ttl < now:
            return {
                'allowed': True,
                'remaining': RATE_LIMIT,
                'reset_at': now + RATE_LIMIT_WINDOW,
                'current_count': 0
            }

        if count >= RATE_LIMIT:
            return {
                'allowed': False,
                'remaining': 0,
                'reset_at': ttl,
                'current_count': count
            }

        return {
            'allowed': True,
            'remaining': max(0, RATE_LIMIT - count),
            'reset_at': ttl,
            'current_count': count
        }
    except Exception as e:
        print(f"Rate limit peek error: {e}")
        return {
            'allowed': False,
            'remaining': 0,
            'reset_at': now + RATE_LIMIT_WINDOW,
            'current_count': RATE_LIMIT
        }


def check_rate_limit(identifier: str) -> Dict[str, Any]:
    """
    Check if IP has exceeded rate limit.
    Returns: {'allowed': bool, 'remaining': int, 'reset_at': int, 'current_count': int}
    """
    now = int(datetime.utcnow().timestamp())
    
    # Hash identifier for privacy (don't store raw IPs / client IDs)
    ip_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
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

    # For non-English queries, append English keywords to improve KB vector
    # retrieval (documents are primarily in English).  The generation prompt
    # still instructs the model to respond in the user's language.
    retrieval_query = query
    if dialect != 'en':
        # Common farming keyword mappings for better retrieval
        _keyword_hints = {
            'कपास': 'cotton', 'कापूस': 'cotton', 'कापस': 'cotton', 'పత్తి': 'cotton',
            'गेहूं': 'wheat', 'गहू': 'wheat', 'గోధుమ': 'wheat',
            'सोयाबीन': 'soybean', 'సోయాబీన్': 'soybean',
            'मक्का': 'maize', 'मका': 'maize', 'మొక్కజొన్న': 'maize',
            'धान': 'rice', 'भात': 'rice', 'వరి': 'rice',
            'कीट': 'pest', 'कीड': 'pest', 'పురుగు': 'pest',
            'रोग': 'disease', 'रोग': 'disease', 'వ్యాధి': 'disease',
            'सफेद मक्खी': 'whitefly', 'पांढरी माशी': 'whitefly', 'पांढऱ्या माशी': 'whitefly', 'తెల్ల దోమ': 'whitefly',
            'स्प्रे': 'spray', 'फवार': 'spray', 'స్ప్రే': 'spray',
            'खाद': 'fertilizer', 'खत': 'fertilizer', 'ఎరువు': 'fertilizer',
            'पाने': 'leaves', 'पान': 'leaves', 'ఆకులు': 'leaves',
            'पीले': 'yellow', 'पिवळी': 'yellow', 'పసుపు': 'yellow',
            'सिंचाई': 'irrigation', 'पाणी': 'water irrigation', 'నీరు': 'water irrigation',
            'बीज': 'seed', 'बियाणे': 'seed', 'విత్తనం': 'seed',
            'मिट्टी': 'soil', 'माती': 'soil', 'నేల': 'soil',
            'उपज': 'yield', 'उत्पादन': 'yield production', 'దిగుబడి': 'yield',
        }
        hints = []
        for local_word, eng_word in _keyword_hints.items():
            if local_word in query:
                hints.append(eng_word)
        if hints:
            retrieval_query = f"{query} ({' '.join(dict.fromkeys(hints))})"
    
    # Build generation configuration
    generation_config = {
        'promptTemplate': {
            'textPromptTemplate': f'''You are an agricultural extension agent helping smallholder farmers in India with FARMING questions ONLY.
{language_instruction}

CRITICAL RULES - READ CAREFULLY:
1. ONLY use information from the Context provided below. DO NOT use any external knowledge.
2. If the Context does not contain relevant information to answer the question, you MUST respond with exactly NO_KB_ANSWER and nothing else. Do not translate it or add any other words.
3. NEVER make up or invent information. NEVER hallucinate.
4. If the question is about people, places, or things not related to farming, respond with exactly NOT_FARMING and nothing else.

RESPONSE STYLE (when you DO have relevant context):
- Sound like a calm, practical TV or radio farm advisory (DD Kisan / extension bulletin style): direct and trustworthy, not a research paper.
- Lead with the ACTION the farmer should take first — not long background.
- Main answer: at most 2-3 short sentences. For simple when / how much / what questions, give the direct answer in one or two sentences first.
- Add at most one short sentence for "why" or "what to watch" only if it changes what they should do.
- Use everyday words; if a technical term is needed, explain it in a few words.
- Avoid long paragraphs, dense lists, and copying long passages from the context.
- Keep the whole answer under 100 words. If the Context lists many steps, give the three or four that matter most.
- Plain text only. No Markdown: no asterisks for bold and no # headings.
- Do not write a line that begins with "Source:" (or स्रोत:, स्त्रोत:, మూలం:) in your answer. The system adds the source line from the documents you cite. Cite the search results only in the way the output format instructions at the end of this prompt ask for.

CRITICAL: If you respond NO_KB_ANSWER OR NOT_FARMING, DO NOT ADD ANY SOURCE CITATION. NO "स्रोत:", NO "Source:", NOTHING.

IMPORTANT RESTRICTIONS:
- ONLY answer questions about agriculture, farming, crops, pests, diseases, fertilizers, weather, and farm management
- If the question is about human health, medical issues, personal problems, or non-farming topics, respond with exactly NOT_FARMING.
- Do NOT provide medical advice, health recommendations, or personal counseling
- Stay strictly within agricultural domain
- Never name a pesticide, insecticide, fungicide or herbicide product, brand, active ingredient, chemical class (for example pyrethroids or organophosphates), formulation or dose, even if the Context contains one, and not as something to avoid either. Give the pest or disease and the non-chemical steps the farmer can take today. Do not write a line telling the farmer to contact the KVK for chemical control: the system adds a closing line to every answer that refers the farmer to their local KVK (Krishi Vigyan Kendra) for the right product and quantity.
- Only if the question asks which pesticide or spray to use, or how much, begin your answer with one short sentence saying you cannot give pesticide names or quantities, then give the non-chemical steps. For any other question, do not say what you cannot recommend; start with the first step.
- NEVER invent or make up information not in the Context

Question: $query$

Context: $search_results$

$output_format_instructions$

REMEMBER: If the Context above does not contain information to answer the Question, you MUST respond with exactly NO_KB_ANSWER. DO NOT make up answers.'''
        }
    }
    
    # Only add guardrail if configured
    if GUARDRAIL_ID and GUARDRAIL_ID.strip():
        generation_config['guardrailConfiguration'] = {
            'guardrailId': GUARDRAIL_ID,
            'guardrailVersion': GUARDRAIL_VERSION
        }
    
    model_arn = _bedrock_model_arn()
    
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
        input={'text': retrieval_query},
        retrieveAndGenerateConfiguration=rag_config
    )
    
    result = {
        'text': response['output']['text'],
        'citations': response.get('citations', []),
        'guardrailAction': response.get('guardrailAction'),
    }
    return apply_kb_no_answer(apply_localized_guardrail_reply(result, dialect), dialect)


def analyze_image(image_base64: str, dialect: str = 'en') -> str:
    """
    Analyze crop image using Bedrock vision (BEDROCK_MODEL_ID).

    Raises on Bedrock/model failures so Lambda Errors increments.
    """
    media_type, image_payload, _ = _decode_image_payload(image_base64)

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

    prompt = prompts.get(dialect, prompts['en']) + (
        "\n\nNever name a pesticide, insecticide, fungicide or herbicide product, brand, active ingredient, "
        "formulation or dose. Give non-chemical steps the farmer can take today; for chemical control, "
        "refer the farmer to the local KVK (Krishi Vigyan Kendra) for the right product and quantity."
    )

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
                            "data": image_payload
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

    response = bedrock_runtime.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(request_body)
    )

    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']


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
        body = json.loads(event.get('body', '{}'))
        message = body.get('message', '').strip()
        language = body.get('language', 'en')

        try:
            images = collect_images(body)
        except ValueError as ve:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': str(ve)})
            }

        # Validate input
        if not message and not images:
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

        # Check rate limit (enforce strictest of IP + anonymous client_id, if provided)
        client_ip = get_client_ip(event)
        client_id = str(body.get('client_id', '')).strip()

        # Pre-check (no increments) so we don't partially increment one bucket if the other is already over limit.
        identifiers = [f"IP#{client_ip}"]
        if client_id:
            # Keep it bounded; we only support a short anonymous identifier
            if 16 <= len(client_id) <= 80:
                identifiers.append(f"CID#{client_id}")
            else:
                print("Ignoring invalid client_id length for rate limiting.")

        peeked = [_peek_rate_limit(i) for i in identifiers]
        if any(not p.get('allowed') for p in peeked):
            reset_at = max(int(p.get('reset_at', 0)) for p in peeked)
            return {
                'statusCode': 429,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Rate limit exceeded. Please try again later.',
                    'remaining': 0,
                    'reset_at': reset_at
                })
            }

        # Increment all identifiers now that we know all are allowed.
        statuses = [check_rate_limit(i) for i in identifiers]
        rate_limit_status = {
            'allowed': all(bool(s.get('allowed')) for s in statuses),
            'remaining': min(int(s.get('remaining', 0)) for s in statuses),
            'reset_at': max(int(s.get('reset_at', 0)) for s in statuses),
            'current_count': max(int(s.get('current_count', 0)) for s in statuses),
        }

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

        dialect = effective_dialect(message or '', language)

        # Process image if provided
        if images:
            print("Processing image analysis request")
            # Validate size before Bedrock (raises ValueError → 400)
            try:
                for img in images:
                    _decode_image_payload(img)
            except ValueError as ve:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': str(ve)})
                }
            analysis = filter_advice(analyze_image(images[0], dialect), dialect, "web_photo", kind="photo")

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
        result = query_bedrock(message, dialect)

        reply_text = result.get('text') or ''
        policy_reply = (
            is_pesticide_question(message)
            and is_rag_refusal_response(reply_text)
            and not result.get('kb_not_farming')
            and not result.get('guardrail_localized')
        )
        if policy_reply:
            # Replaces a refused answer, so that answer's retrievals are not its source.
            reply_text = pesticide_policy(dialect)
        reply_text = strip_llm_xml_citation_tags(reply_text)
        reply_text = strip_source_lines(reply_text)
        reply_text = filter_advice(
            reply_text, dialect, "web_text", kind="answer",
            add_referral=not is_rag_refusal_response(reply_text),
            question=message,
        )

        # Format citations
        # Document titles from metadata, else file names (common.source_labels).
        citations = [] if policy_reply else source_labels(result.get('citations', []))

        # Return response
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'reply': reply_text,
                'citations': list(dict.fromkeys(citations)),  # Deduplicate, preserve order
                'remaining': rate_limit_status['remaining'],
                'reset_at': rate_limit_status['reset_at']
            })
        }

    except Exception:
        # Log full stack and re-raise so Lambda Errors increments (and API GW 5XX fires).
        logger.exception("Web chat handler failed")
        raise
