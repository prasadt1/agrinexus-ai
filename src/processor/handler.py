"""
Message Processor
Processes messages from SQS: Onboarding state machine + Bedrock RAG queries
"""
import json
import os
import boto3
from typing import Dict, Any, Optional
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
bedrock_agent = boto3.client('bedrock-agent-runtime')
secrets = boto3.client('secretsmanager')

TABLE_NAME = os.environ['TABLE_NAME']
KB_ID = os.environ['KNOWLEDGE_BASE_ID']
GUARDRAIL_ID = os.environ['GUARDRAIL_ID']
GUARDRAIL_VERSION = os.environ['GUARDRAIL_VERSION']

table = dynamodb.Table(TABLE_NAME)

# Onboarding configuration
VALID_DISTRICTS = ['Aurangabad', 'Jalna', 'Nagpur']
VALID_CROPS = ['Cotton', 'Soybean', 'Maize']
VALID_LANGUAGES = ['Hindi', 'Marathi', 'Telugu']

# Onboarding messages by dialect
ONBOARDING_MESSAGES = {
    'welcome': {
        'hi': 'नमस्ते! AgriNexus AI में आपका स्वागत है। मैं आपकी खेती में मदद करूंगा। कृपया अपनी भाषा चुनें:',
        'mr': 'नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे. मी तुमच्या शेतीत मदत करेन. कृपया तुमची भाषा निवडा:',
        'te': 'నమస్కారం! AgriNexus AI కి స్వాగతం. నేను మీ వ్యవసాయంలో సహాయం చేస్తాను. దయచేసి మీ భాషను ఎంచుకోండి:'
    },
    'ask_location': {
        'hi': 'बढ़िया! अब मुझे बताएं आप किस जिले में हैं?',
        'mr': 'छान! आता मला सांगा तुम्ही कोणत्या जिल्ह्यात आहात?',
        'te': 'బాగుంది! ఇప్పుడు మీరు ఏ జిల్లాలో ఉన్నారో చెప్పండి?'
    },
    'ask_crop': {
        'hi': 'धन्यवाद! आप कौन सी फसल उगाते हैं?',
        'mr': 'धन्यवाद! तुम्ही कोणते पीक घेता?',
        'te': 'ధన్యవాదాలు! మీరు ఏ పంట పండిస్తారు?'
    },
    'ask_consent': {
        'hi': 'अंतिम प्रश्न: क्या आप मौसम के अनुसार खेती की सलाह प्राप्त करना चाहते हैं? (हाँ/नहीं)',
        'mr': 'शेवटचा प्रश्न: तुम्हाला हवामानानुसार शेतीचा सल्ला मिळवायचा आहे का? (होय/नाही)',
        'te': 'చివరి ప్రశ్న: మీరు వాతావరణం ఆధారంగా వ్యవసాయ సలహా పొందాలనుకుంటున్నారా? (అవును/కాదు)'
    },
    'onboarding_complete': {
        'hi': 'बधाई हो! आपका प्रोफाइल तैयार है। अब आप मुझसे कोई भी सवाल पूछ सकते हैं।',
        'mr': 'अभिनंदन! तुमचे प्रोफाइल तयार आहे. आता तुम्ही मला कोणताही प्रश्न विचारू शकता.',
        'te': 'అభినందనలు! మీ ప్రొఫైల్ సిద్ధంగా ఉంది. ఇప్పుడు మీరు నన్ను ఏదైనా ప్రశ్న అడగవచ్చు.'
    }
}


def get_user_profile(phone_number: str) -> Optional[Dict[str, Any]]:
    """Retrieve user profile from DynamoDB"""
    response = table.get_item(
        Key={
            'PK': f'USER#{phone_number}',
            'SK': 'PROFILE'
        }
    )
    return response.get('Item')


def update_user_profile(phone_number: str, updates: Dict[str, Any]):
    """Update user profile in DynamoDB"""
    update_expr = 'SET ' + ', '.join([f'#{k} = :{k}' for k in updates.keys()])
    expr_names = {f'#{k}': k for k in updates.keys()}
    expr_values = {f':{k}': v for k, v in updates.items()}
    
    table.update_item(
        Key={
            'PK': f'USER#{phone_number}',
            'SK': 'PROFILE'
        },
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values
    )


def create_user_profile(phone_number: str, dialect: str, location: str, crop: str, consent: bool):
    """Create complete user profile"""
    table.put_item(
        Item={
            'PK': f'USER#{phone_number}',
            'SK': 'PROFILE',
            'phone_number': phone_number,
            'dialect': dialect,
            'location': location,
            'crop': crop,
            'consent': consent,
            'onboarding_complete': True,
            'created_at': datetime.utcnow().isoformat(),
            'GSI1PK': f'LOCATION#{location}',
            'GSI1SK': f'CROP#{crop}'
        }
    )


def handle_onboarding(phone_number: str, message_text: str, profile: Optional[Dict[str, Any]]) -> str:
    """
    Onboarding state machine
    States: welcome -> language -> location -> crop -> consent -> complete
    """
    # State 1: Welcome (no profile exists)
    if not profile:
        table.put_item(
            Item={
                'PK': f'USER#{phone_number}',
                'SK': 'PROFILE',
                'phone_number': phone_number,
                'onboarding_state': 'language',
                'onboarding_complete': False
            }
        )
        return ONBOARDING_MESSAGES['welcome']['hi']  # Default to Hindi for welcome
    
    state = profile.get('onboarding_state', 'complete')
    
    # State 2: Language selection
    if state == 'language':
        # Check if message contains language selection
        text_lower = message_text.lower()
        dialect = None
        if 'hindi' in text_lower or 'हिंदी' in text_lower:
            dialect = 'hi'
        elif 'marathi' in text_lower or 'मराठी' in text_lower:
            dialect = 'mr'
        elif 'telugu' in text_lower or 'తెలుగు' in text_lower:
            dialect = 'te'
        
        if dialect:
            update_user_profile(phone_number, {
                'dialect': dialect,
                'onboarding_state': 'location'
            })
            return ONBOARDING_MESSAGES['ask_location'][dialect]
        else:
            return ONBOARDING_MESSAGES['welcome']['hi']
    
    # State 3: Location validation
    elif state == 'location':
        dialect = profile.get('dialect', 'hi')
        # Check if message contains valid district
        location = None
        for district in VALID_DISTRICTS:
            if district.lower() in message_text.lower():
                location = district
                break
        
        if location:
            update_user_profile(phone_number, {
                'location': location,
                'onboarding_state': 'crop'
            })
            return ONBOARDING_MESSAGES['ask_crop'][dialect]
        else:
            return f"{ONBOARDING_MESSAGES['ask_location'][dialect]}\n\nValid: {', '.join(VALID_DISTRICTS)}"
    
    # State 4: Crop selection
    elif state == 'crop':
        dialect = profile.get('dialect', 'hi')
        # Check if message contains valid crop
        crop = None
        text_lower = message_text.lower()
        if 'cotton' in text_lower or 'कपास' in text_lower or 'कापूस' in text_lower:
            crop = 'Cotton'
        elif 'soybean' in text_lower or 'सोयाबीन' in text_lower:
            crop = 'Soybean'
        elif 'maize' in text_lower or 'मक्का' in text_lower:
            crop = 'Maize'
        
        if crop:
            update_user_profile(phone_number, {
                'crop': crop,
                'onboarding_state': 'consent'
            })
            return ONBOARDING_MESSAGES['ask_consent'][dialect]
        else:
            return f"{ONBOARDING_MESSAGES['ask_crop'][dialect]}\n\nOptions: Cotton, Soybean, Maize"
    
    # State 5: Consent
    elif state == 'consent':
        dialect = profile.get('dialect', 'hi')
        location = profile.get('location')
        crop = profile.get('crop')
        
        # Check for consent keywords
        text_lower = message_text.lower()
        consent = False
        if any(word in text_lower for word in ['yes', 'हाँ', 'हां', 'होय', 'అవును']):
            consent = True
        
        # Complete onboarding
        create_user_profile(phone_number, dialect, location, crop, consent)
        return ONBOARDING_MESSAGES['onboarding_complete'][dialect]
    
    return "Error in onboarding flow"


def save_message(phone_number: str, wamid: str, message_data: Dict[str, Any], response_text: str, source_citation: str):
    """Save message to DynamoDB with TTL"""
    timestamp = datetime.utcnow().isoformat()
    ttl = int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days
    
    table.put_item(
        Item={
            'PK': f'USER#{phone_number}',
            'SK': f'MSG#{timestamp}',
            'wamid': wamid,
            'message': message_data,
            'response': response_text,
            'source_citation': source_citation,
            'ttl': ttl
        }
    )


def query_bedrock(query: str, dialect: str = 'hi') -> Dict[str, Any]:
    """Query Bedrock Knowledge Base with RAG"""
    # Build generation configuration
    generation_config = {
        'promptTemplate': {
            'textPromptTemplate': f'''You are an agricultural extension agent helping smallholder farmers in India. 
Respond in {dialect} dialect (hi=Hindi, mr=Marathi, te=Telugu).
Use simple, practical language. Include source citations.

Question: $query$

Context: $search_results$

Provide actionable advice with source references.'''
        }
    }
    
    # Only add guardrail if it's configured
    if GUARDRAIL_ID and GUARDRAIL_ID.strip():
        generation_config['guardrailConfiguration'] = {
            'guardrailId': GUARDRAIL_ID,
            'guardrailVersion': GUARDRAIL_VERSION
        }
    
    response = bedrock_agent.retrieve_and_generate(
        input={'text': query},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KB_ID,
                'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
                'generationConfiguration': generation_config
            }
        }
    )
    
    return {
        'text': response['output']['text'],
        'citations': response.get('citations', [])
    }


def send_whatsapp_message(phone_number: str, message: str):
    """Send message via WhatsApp Business API"""
    import requests
    
    # Get WhatsApp credentials from environment variables (secret names)
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    phone_id_secret = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')
    
    # Get secret values
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
        "text": {
            "body": message
        }
    }
    
    print(f"Sending to {phone_number}: {message[:50]}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"Message sent successfully: {response.json()}")
    else:
        print(f"Failed to send message: {response.status_code} - {response.text}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process messages from SQS"""
    for record in event['Records']:
        body = json.loads(record['body'])
        
        wamid = body['wamid']
        from_number = body['from']
        message_type = body['type']
        message = body['message']
        
        # Get user profile
        profile = get_user_profile(from_number)
        
        # Check if onboarding is complete
        if not profile or not profile.get('onboarding_complete', False):
            # Handle onboarding
            if message_type == 'text':
                text = message.get('text', {}).get('body', '')
                response_text = handle_onboarding(from_number, text, profile)
                send_whatsapp_message(from_number, response_text)
            continue
        
        dialect = profile.get('dialect', 'hi')
        
        # Process based on message type
        if message_type == 'text':
            text = message.get('text', {}).get('body', '')
            
            # Check for DONE/NOT YET keywords (handled by response detector)
            # Just process as normal query
            
            # Send immediate acknowledgment (improves perceived response time)
            ack_messages = {
                'hi': '✓ आपका सवाल मिल गया। जवाब तैयार कर रहे हैं...',
                'mr': '✓ तुमचा प्रश्न मिळाला. उत्तर तयार करत आहे...',
                'te': '✓ మీ ప్రశ్న అందింది. సమాధానం తయారు చేస్తున్నాము...'
            }
            send_whatsapp_message(from_number, ack_messages.get(dialect, ack_messages['hi']))
            
            # Query Bedrock (this takes ~13 seconds)
            result = query_bedrock(text, dialect)
            
            # Save to DynamoDB
            save_message(from_number, wamid, message, result['text'], str(result['citations']))
            
            # Send response
            send_whatsapp_message(from_number, result['text'])
        
        elif message_type == 'image':
            # TODO: Implement Claude Vision processing
            send_whatsapp_message(from_number, "Image processing coming soon!")
        
        elif message_type == 'audio':
            # TODO: Implement Transcribe processing
            send_whatsapp_message(from_number, "Voice processing coming soon!")
    
    return {'statusCode': 200}
