"""
Message Processor
Processes messages from SQS: Onboarding state machine + Bedrock RAG queries
"""
import json
import os
import boto3
from typing import Dict, Any, Optional
from datetime import datetime

# Import voice output module
from output import text_to_speech, should_send_voice_response

# Import vision module
from analyzer import process_image_message

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
VALID_CROPS = ['Cotton', 'Wheat', 'Soybean', 'Maize']
VALID_LANGUAGES = ['Hindi', 'Marathi', 'Telugu', 'English']

# Onboarding messages by dialect
ONBOARDING_MESSAGES = {
    'welcome': {
        'hi': 'नमस्ते! AgriNexus AI में आपका स्वागत है। मैं आपकी खेती में मदद करूंगा। कृपया अपनी भाषा चुनें:',
        'mr': 'नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे. मी तुमच्या शेतीत मदत करेन. कृपया तुमची भाषा निवडा:',
        'te': 'నమస్కారం! AgriNexus AI కి స్వాగతం. నేను మీ వ్యవసాయంలో సహాయం చేస్తాను. దయచేసి మీ భాషను ఎంచుకోండి:',
        'en': 'Welcome to AgriNexus AI! I will help you with your farming. Please choose your language:'
    },
    'ask_location': {
        'hi': 'बढ़िया! अब मुझे बताएं आप किस जिले में हैं?',
        'mr': 'छान! आता मला सांगा तुम्ही कोणत्या जिल्ह्यात आहात?',
        'te': 'బాగుంది! ఇప్పుడు మీరు ఏ జిల్లాలో ఉన్నారో చెప్పండి?',
        'en': 'Great! Now tell me which district you are in?'
    },
    'ask_crop': {
        'hi': 'धन्यवाद! आप कौन सी फसल उगाते हैं?',
        'mr': 'धन्यवाद! तुम्ही कोणते पीक घेता?',
        'te': 'ధన్యవాదాలు! మీరు ఏ పంట పండిస్తారు?',
        'en': 'Thank you! Which crop do you grow?'
    },
    'ask_consent': {
        'hi': 'अंतिम प्रश्न: क्या आप मौसम के अनुसार खेती की सलाह प्राप्त करना चाहते हैं? (हाँ/नहीं)',
        'mr': 'शेवटचा प्रश्न: तुम्हाला हवामानानुसार शेतीचा सल्ला मिळवायचा आहे का? (होय/नाही)',
        'te': 'చివరి ప్రశ్న: మీరు వాతావరణం ఆధారంగా వ్యవసాయ సలహా పొందాలనుకుంటున్నారా? (అవును/కాదు)',
        'en': 'Final question: Would you like to receive weather-based farming advice? (Yes/No)'
    },
    'onboarding_complete': {
        'hi': 'बधाई हो! आपका प्रोफाइल तैयार है। अब आप मुझसे कोई भी सवाल पूछ सकते हैं।',
        'mr': 'अभिनंदन! तुमचे प्रोफाइल तयार आहे. आता तुम्ही मला कोणताही प्रश्न विचारू शकता.',
        'te': 'అభినందనలు! మీ ప్రొఫైల్ సిద్ధంగా ఉంది. ఇప్పుడు మీరు నన్ను ఏదైనా ప్రశ్న అడగవచ్చు.',
        'en': 'Congratulations! Your profile is ready. You can now ask me any question.'
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


def handle_onboarding(phone_number: str, message_text: str, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Onboarding state machine with interactive buttons
    States: welcome -> language -> location -> crop -> consent -> complete
    Returns: {'type': 'text'|'buttons', 'content': str, 'buttons': list (optional)}
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
        # Send welcome message with language selection buttons
        # Show multilingual welcome so all farmers can understand
        multilingual_welcome = """Welcome to AgriNexus AI! 🌾

नमस्ते! AgriNexus AI में आपका स्वागत है।
नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे.
నమస్కారం! AgriNexus AI కి స్వాగతం.

Please choose your language / कृपया अपनी भाषा चुनें:"""
        
        return {
            'type': 'buttons',
            'content': multilingual_welcome,
            'buttons': ['English', 'हिंदी', 'मराठी']
        }
    
    state = profile.get('onboarding_state', 'complete')
    
    # State 2: Language selection
    if state == 'language':
        # Check if message contains language selection (from button or text)
        text_lower = message_text.lower()
        dialect = None
        if 'hindi' in text_lower or 'हिंदी' in message_text:
            dialect = 'hi'
        elif 'marathi' in text_lower or 'मराठी' in message_text:
            dialect = 'mr'
        elif 'telugu' in text_lower or 'తెలుగు' in message_text:
            dialect = 'te'
        elif 'english' in text_lower:
            dialect = 'en'
        
        if dialect:
            update_user_profile(phone_number, {
                'dialect': dialect,
                'onboarding_state': 'location'
            })
            # Ask for location with buttons
            location_prompt = {
                'hi': 'बढ़िया! अब मुझे बताएं आप किस जिले में हैं?\n\n(या कोई भी जिला टाइप करें)',
                'mr': 'छान! आता मला सांगा तुम्ही कोणत्या जिल्ह्यात आहात?\n\n(किंवा कोणताही जिल्हा टाइप करा)',
                'te': 'బాగుంది! ఇప్పుడు మీరు ఏ జిల్లాలో ఉన్నారో చెప్పండి?\n\n(లేదా ఏదైనా జిల్లా టైప్ చేయండి)',
                'en': 'Great! Now tell me which district you are in?\n\n(Or type any district name)'
            }
            return {
                'type': 'buttons',
                'content': location_prompt.get(dialect, location_prompt['hi']),
                'buttons': ['Aurangabad', 'Jalna', 'Nagpur']
            }
        else:
            # Invalid selection, resend buttons
            multilingual_welcome = """Welcome to AgriNexus AI! 🌾

नमस्ते! AgriNexus AI में आपका स्वागत है।
नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे.
నమస్కారం! AgriNexus AI కి స్వాగతం.

Please choose your language / कृपया अपनी भाषा चुनें:"""
            
            return {
                'type': 'buttons',
                'content': multilingual_welcome,
                'buttons': ['English', 'हिंदी', 'मराठी']
            }
    
    # State 3: Location validation
    elif state == 'location':
        dialect = profile.get('dialect', 'hi')
        # Check if message contains valid district
        location = None
        
        # First check for our configured districts (for weather nudges)
        for district in VALID_DISTRICTS:
            if district.lower() in message_text.lower():
                location = district
                break
        
        # If not a configured district, accept any district name (for demo flexibility)
        if not location and len(message_text.strip()) > 2:
            # Accept the input as a district name
            location = message_text.strip().title()
        
        if location:
            update_user_profile(phone_number, {
                'location': location,
                'onboarding_state': 'crop'
            })
            # Ask for crop with buttons in user's dialect
            crop_buttons = {
                'hi': ['कपास', 'गेहूं', 'सोयाबीन'],
                'mr': ['कापूस', 'गहू', 'सोयाबीन'],
                'te': ['పత్తి', 'గోధుమ', 'సోయాబీన్'],
                'en': ['Cotton', 'Wheat', 'Soybean']
            }
            return {
                'type': 'buttons',
                'content': ONBOARDING_MESSAGES['ask_crop'][dialect],
                'buttons': crop_buttons.get(dialect, crop_buttons['hi'])
            }
        else:
            # Show buttons for configured districts with option to type any district
            location_prompt = {
                'hi': 'बढ़िया! अब मुझे बताएं आप किस जिले में हैं?\n\n(या कोई भी जिला टाइप करें)',
                'mr': 'छान! आता मला सांगा तुम्ही कोणत्या जिल्ह्यात आहात?\n\n(किंवा कोणताही जिल्हा टाइप करा)',
                'te': 'బాగుంది! ఇప్పుడు మీరు ఏ జిల్లాలో ఉన్నారో చెప్పండి?\n\n(లేదా ఏదైనా జిల్లా టైప్ చేయండి)',
                'en': 'Great! Now tell me which district you are in?\n\n(Or type any district name)'
            }
            return {
                'type': 'buttons',
                'content': location_prompt.get(dialect, location_prompt['hi']),
                'buttons': ['Aurangabad', 'Jalna', 'Nagpur']
            }
    
    # State 4: Crop selection
    elif state == 'crop':
        dialect = profile.get('dialect', 'hi')
        # Check if message contains valid crop (from button or text)
        crop = None
        text_lower = message_text.lower()
        # Cotton
        if 'cotton' in text_lower or 'कपास' in text_lower or 'कापूस' in text_lower or 'పత్తి' in message_text:
            crop = 'Cotton'
        # Wheat
        elif 'wheat' in text_lower or 'गेहूं' in text_lower or 'गहू' in text_lower or 'గోధుమ' in message_text:
            crop = 'Wheat'
        # Soybean
        elif 'soybean' in text_lower or 'सोयाबीन' in text_lower or 'సోయాబీన్' in message_text:
            crop = 'Soybean'
        # Maize
        elif 'maize' in text_lower or 'मक्का' in text_lower or 'మొక్కజొన్న' in message_text:
            crop = 'Maize'
        
        if crop:
            update_user_profile(phone_number, {
                'crop': crop,
                'onboarding_state': 'consent'
            })
            # Ask for consent with buttons in user's dialect
            consent_buttons = {
                'hi': ['हाँ ✅', 'नहीं ❌'],
                'mr': ['होय ✅', 'नाही ❌'],
                'te': ['అవును ✅', 'కాదు ❌'],
                'en': ['Yes ✅', 'No ❌']
            }
            return {
                'type': 'buttons',
                'content': ONBOARDING_MESSAGES['ask_consent'][dialect],
                'buttons': consent_buttons.get(dialect, consent_buttons['hi'])
            }
        else:
            # Invalid crop, prompt for text input
            crop_names = {
                'hi': 'कपास, गेहूं, सोयाबीन',
                'mr': 'कापूस, गहू, सोयाबीन',
                'te': 'పత్తి, గోధుమ, సోయాబీన్',
                'en': 'Cotton, Wheat, Soybean'
            }
            return {
                'type': 'text',
                'content': f"{ONBOARDING_MESSAGES['ask_crop'][dialect]}\n\nOptions: {crop_names.get(dialect, crop_names['hi'])}"
            }
    
    # State 5: Consent
    elif state == 'consent':
        dialect = profile.get('dialect', 'hi')
        location = profile.get('location')
        crop = profile.get('crop')
        
        # Check for consent keywords (from button or text)
        text_lower = message_text.lower()
        consent = False
        if any(word in text_lower for word in ['yes', 'हाँ', 'हां', 'होय', 'అవును', '✅']):
            consent = True
        
        # Complete onboarding
        create_user_profile(phone_number, dialect, location, crop, consent)
        return {
            'type': 'text',
            'content': ONBOARDING_MESSAGES['onboarding_complete'][dialect]
        }
    
    return {
        'type': 'text',
        'content': "Error in onboarding flow"
    }


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
    # Map dialect to language instruction
    language_instructions = {
        'hi': 'Respond in Hindi (Devanagari script). Use simple, practical language.',
        'mr': 'Respond in Marathi (Devanagari script). Use simple, practical language.',
        'te': 'Respond in Telugu script. Use simple, practical language.',
        'en': 'Respond in English. Use simple, practical language suitable for Indian farmers.'
    }
    
    language_instruction = language_instructions.get(dialect, language_instructions['hi'])
    
    # Build generation configuration
    generation_config = {
        'promptTemplate': {
            'textPromptTemplate': f'''You are an agricultural extension agent helping smallholder farmers in India with FARMING questions ONLY.
{language_instruction}
Include source citations.

IMPORTANT RESTRICTIONS:
- ONLY answer questions about agriculture, farming, crops, pests, diseases, fertilizers, weather, and farm management
- If the question is about human health, medical issues, personal problems, or non-farming topics, respond: "I can only help with farming questions. Please ask about crops, pests, fertilizers, or farm management."
- Do NOT provide medical advice, health recommendations, or personal counseling
- Stay strictly within agricultural domain

Question: $query$

Context: $search_results$

Provide actionable farming advice with source references.'''
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


def send_whatsapp_message(phone_number: str, message: str, audio_url: Optional[str] = None):
    """
    Send message via WhatsApp Business API
    Supports both text and audio messages
    
    Args:
        phone_number: Recipient phone number
        message: Text message to send
        audio_url: Optional audio URL for voice message
    """
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
    
    # If audio URL provided, send audio message
    if audio_url:
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "audio",
            "audio": {
                "link": audio_url
            }
        }
        print(f"Sending voice message to {phone_number}: {audio_url}")
    else:
        # Send text message
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {
                "body": message
            }
        }
        print(f"Sending text to {phone_number}: {message[:50]}...")
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"Message sent successfully: {response.json()}")
    else:
        print(f"Failed to send message: {response.status_code} - {response.text}")


def send_whatsapp_buttons(phone_number: str, body_text: str, buttons: list):
    """Send interactive reply buttons via WhatsApp Business API"""
    import requests
    
    # Get WhatsApp credentials
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    phone_id_secret = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')
    
    access_token_response = secrets.get_secret_value(SecretId=access_token_secret)
    access_token = access_token_response['SecretString']
    
    phone_id_response = secrets.get_secret_value(SecretId=phone_id_secret)
    phone_number_id = phone_id_response['SecretString']
    
    # Build interactive message with reply buttons
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Format buttons for WhatsApp API (max 3 buttons)
    formatted_buttons = []
    for i, button in enumerate(buttons[:3]):  # WhatsApp allows max 3 reply buttons
        formatted_buttons.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}",
                "title": button
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": formatted_buttons
            }
        }
    }
    
    print(f"Sending buttons to {phone_number}: {body_text[:50]}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"Buttons sent successfully: {response.json()}")
    else:
        print(f"Failed to send buttons: {response.status_code} - {response.text}")


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
            text = ''
            if message_type == 'text':
                text = message.get('text', {}).get('body', '')
            elif message_type == 'interactive':
                # Extract button reply text
                interactive = message.get('interactive', {})
                button_reply = interactive.get('button_reply', {})
                text = button_reply.get('title', '')
            
            if text:
                onboarding_response = handle_onboarding(from_number, text, profile)
                
                # Send appropriate message type (text or buttons)
                if onboarding_response['type'] == 'buttons':
                    send_whatsapp_buttons(from_number, onboarding_response['content'], onboarding_response['buttons'])
                else:
                    send_whatsapp_message(from_number, onboarding_response['content'])
            continue
        
        dialect = profile.get('dialect', 'hi')
        
        # Process based on message type
        if message_type == 'text':
            text = message.get('text', {}).get('body', '')
            
            # Check for HELP command
            if text.strip().upper() in ['HELP', 'मदद', 'मदत', 'సహాయం']:
                help_messages = {
                    'hi': '''🌾 AgriNexus AI - मदद

मैं आपकी खेती में मदद कर सकता हूं:

📝 सवाल पूछें:
• "कपास में कीट कैसे नियंत्रित करें?"
• "गेहूं में खाद कब डालें?"
• "मौसम के अनुसार क्या करें?"

📸 फोटो भेजें:
• पत्तियों की फोटो
• कीट/रोग की फोटो
• मैं पहचान करूंगा और सलाह दूंगा

🎤 आवाज़ में पूछें:
• वॉइस नोट भेजें
• मैं समझूंगा और जवाब दूंगा

बस अपना सवाल टाइप करें या फोटो भेजें!''',
                    'mr': '''🌾 AgriNexus AI - मदत

मी तुमच्या शेतीत मदत करू शकतो:

📝 प्रश्न विचारा:
• "कापसात किडे कसे नियंत्रित करावे?"
• "गहूमध्ये खत कधी घालावे?"
• "हवामानानुसार काय करावे?"

📸 फोटो पाठवा:
• पानांचा फोटो
• किडे/रोगाचा फोटो
• मी ओळखेन आणि सल्ला देईन

🎤 आवाजात विचारा:
• व्हॉइस नोट पाठवा
• मी समजेन आणि उत्तर देईन

फक्त तुमचा प्रश्न टाइप करा किंवा फोटो पाठवा!''',
                    'te': '''🌾 AgriNexus AI - సహాయం

నేను మీ వ్యవసాయంలో సహాయం చేయగలను:

📝 ప్రశ్నలు అడగండి:
• "పత్తిలో పురుగులను ఎలా నియంత్రించాలి?"
• "గోధుమలో ఎరువులు ఎప్పుడు వేయాలి?"
• "వాతావరణం ప్రకారం ఏమి చేయాలి?"

📸 ఫోటో పంపండి:
• ఆకుల ఫోటో
• పురుగు/వ్యాధి ఫోటో
• నేను గుర్తించి సలహా ఇస్తాను

🎤 వాయిస్‌లో అడగండి:
• వాయిస్ నోట్ పంపండి
• నేను అర్థం చేసుకుని సమాధానం ఇస్తాను

మీ ప్రశ్న టైప్ చేయండి లేదా ఫోటో పంపండి!''',
                    'en': '''🌾 AgriNexus AI - Help

I can help you with your farming:

📝 Ask Questions:
• "How to control cotton pests?"
• "When to apply fertilizer to wheat?"
• "What to do based on weather?"

📸 Send Photos:
• Leaf photos
• Pest/disease photos
• I'll identify and advise

🎤 Ask by Voice:
• Send voice note
• I'll understand and respond

Just type your question or send a photo!'''
                }
                send_whatsapp_message(from_number, help_messages.get(dialect, help_messages['hi']))
                continue
            
            # Check for DONE/NOT YET keywords (handled by response detector)
            # Just process as normal query
            
            # Send immediate acknowledgment (improves perceived response time)
            ack_messages = {
                'hi': '✓ आपका सवाल मिल गया। जवाब तैयार कर रहे हैं...',
                'mr': '✓ तुमचा प्रश्न मिळाला. उत्तर तयार करत आहे...',
                'te': '✓ మీ ప్రశ్న అందింది. సమాధానం తయారు చేస్తున్నాము...',
                'en': '✓ Question received. Preparing answer...'
            }
            send_whatsapp_message(from_number, ack_messages.get(dialect, ack_messages['hi']))
            
            # Query Bedrock (this takes ~13 seconds)
            result = query_bedrock(text, dialect)
            
            # Save to DynamoDB
            save_message(from_number, wamid, message, result['text'], str(result['citations']))
            
            # Check if user wants voice response (Hindi, Marathi, English supported)
            send_voice = (dialect in ['hi', 'mr', 'en'] and 
                         (message.get('_source') == 'voice' or profile.get('voicePreference', False)))
            
            if send_voice:
                # Generate voice output
                audio_url = text_to_speech(result['text'], dialect, from_number)
                if audio_url:
                    # Send voice message
                    send_whatsapp_message(from_number, result['text'], audio_url=audio_url)
                else:
                    # Fallback to text if voice generation fails
                    send_whatsapp_message(from_number, result['text'])
            else:
                # Send text response
                send_whatsapp_message(from_number, result['text'])
        
        elif message_type == 'image':
            # Process image with Claude Vision
            print(f"Processing image message from {from_number}")
            
            # Send acknowledgment
            ack_messages = {
                'hi': '✓ फोटो मिली। विश्लेषण कर रहे हैं...',
                'mr': '✓ फोटो मिळाला. विश्लेषण करत आहे...',
                'te': '✓ ఫోటో అందింది. విశ్లేషిస్తున్నాము...',
                'en': '✓ Photo received. Analyzing...'
            }
            send_whatsapp_message(from_number, ack_messages.get(dialect, ack_messages['hi']))
            
            # Analyze image
            analysis = process_image_message(message, profile)
            
            # Save to DynamoDB
            save_message(from_number, wamid, message, analysis, 'vision_analysis')
            
            # Send response (text only - no voice for image responses)
            send_whatsapp_message(from_number, analysis)
        
        elif message_type == 'audio':
            # Audio messages are handled by VoiceProcessor Lambda
            print(f"Audio message - should be handled by VoiceProcessor")
    
    return {'statusCode': 200}
