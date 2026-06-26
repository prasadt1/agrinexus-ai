"""
Message Processor
Processes messages from SQS: Onboarding state machine + Bedrock RAG queries
"""
import json
import os
import re
import boto3
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

# Import voice output module
from output import text_to_speech, truncate_for_voice, voice_truncation_prefix

# Import vision module
import analyzer

# Import WhatsApp utilities from common layer (with Secrets Manager caching)
from common.whatsapp import send_whatsapp_message, send_whatsapp_list
from common.whatsapp import send_whatsapp_buttons as _send_whatsapp_buttons
from common.district_helplines import maybe_append_helpline_footer
from common.allowlist import is_approved_user, allowlist_expiry_hint


def send_whatsapp_buttons(phone_number: str, body_text: str, buttons: list):
    """
    Wrapper for common layer's send_whatsapp_buttons that accepts simple string list.
    Converts ['Option 1', 'Option 2'] to [{'id': 'btn_0', 'title': 'Option 1'}, ...]
    """
    formatted_buttons = [
        {"id": f"btn_{i}", "title": btn}
        for i, btn in enumerate(buttons[:3])
    ]
    return _send_whatsapp_buttons(phone_number, body_text, formatted_buttons)

dynamodb = boto3.resource('dynamodb')
bedrock_agent = boto3.client('bedrock-agent-runtime')
s3 = boto3.client("s3")

TABLE_NAME = os.environ['TABLE_NAME']
KB_ID = os.environ['KNOWLEDGE_BASE_ID']
GUARDRAIL_ID = os.environ['GUARDRAIL_ID']
GUARDRAIL_VERSION = os.environ['GUARDRAIL_VERSION']

table = dynamodb.Table(TABLE_NAME)

_PENDING_CROP_CONFIRM_SK = "PENDING#CROP_CONFIRM"
_PENDING_TTL_SECONDS = int(os.environ.get("PENDING_CROP_CONFIRM_TTL_SECONDS", "600"))
_LAST_IMAGE_SK = "PENDING#LAST_IMAGE"
_LAST_IMAGE_TTL_SECONDS = int(os.environ.get("LAST_IMAGE_TTL_SECONDS", "600"))


def _last_image_override_enabled() -> bool:
    return (os.environ.get("LAST_IMAGE_OVERRIDE_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")


def _put_last_image_pointer(phone_number: str, bucket: str, key: str):
    if not _last_image_override_enabled():
        return
    import time
    ttl = int(time.time()) + _LAST_IMAGE_TTL_SECONDS
    table.put_item(
        Item={
            "PK": f"USER#{phone_number}",
            "SK": _LAST_IMAGE_SK,
            "bucket": bucket,
            "key": key,
            "ttl": ttl,
        }
    )


def _get_last_image_pointer(phone_number: str) -> Optional[Dict[str, Any]]:
    if not _last_image_override_enabled():
        return None
    resp = table.get_item(Key={"PK": f"USER#{phone_number}", "SK": _LAST_IMAGE_SK})
    return resp.get("Item")


def _delete_last_image_pointer(phone_number: str):
    if not _last_image_override_enabled():
        return
    table.delete_item(Key={"PK": f"USER#{phone_number}", "SK": _LAST_IMAGE_SK})


def _get_pending_crop_confirm(phone_number: str) -> Optional[Dict[str, Any]]:
    resp = table.get_item(Key={"PK": f"USER#{phone_number}", "SK": _PENDING_CROP_CONFIRM_SK})
    return resp.get("Item")


def _put_pending_crop_confirm(phone_number: str, pending: Dict[str, Any]):
    import time

    ttl = int(time.time()) + _PENDING_TTL_SECONDS
    item = {
        "PK": f"USER#{phone_number}",
        "SK": _PENDING_CROP_CONFIRM_SK,
        "ttl": ttl,
        **pending,
    }
    table.put_item(Item=item)


def _delete_pending_crop_confirm(phone_number: str):
    table.delete_item(Key={"PK": f"USER#{phone_number}", "SK": _PENDING_CROP_CONFIRM_SK})


def _parse_crop_confirm_reply(text: str, inferred_crop: str, profile_crop: str) -> Optional[str]:
    """
    Returns chosen crop string, or None if the reply isn't a crop-confirm response.
    """
    t = (text or "").strip().lower()
    if not t:
        return None

    # Normalize common punctuation so replies like "yes." or "हाँ!" are accepted.
    t_norm = (
        t.replace("।", " ")
        .replace(".", " ")
        .replace("!", " ")
        .replace("?", " ")
        .replace(",", " ")
        .replace(":", " ")
        .replace(";", " ")
    ).strip()
    tokens = [x for x in t_norm.split() if x]

    yes = {
        "y",
        "yes",
        "yeah",
        "yep",
        "ok",
        "okay",
        # Hindi (typed variants)
        "haan",
        "han",
        "haa",
        "ha",
        "ji",
        "haanji",
        "जी",
        "हाँ",
        "हां",
        "हो",
        "ठीक",
        "theek",
        "thik",
    }
    no = {
        "n",
        "no",
        "nah",
        "nope",
        # Hindi/Marathi/Telugu common negatives
        "नहीं",
        "नहि",
        "ना",
        "na",
        "नाही",
        "कాదు",
    }

    # Accept exact match OR presence in a short phrase (e.g., "हाँ वही है", "yes it's wheat").
    if t in yes or any(tok in yes for tok in tokens):
        return inferred_crop
    if t in no or any(tok in no for tok in tokens):
        return profile_crop

    chosen = _parse_crop_word(text)
    if chosen:
        return chosen

    # Also accept sending the exact inferred crop or profile crop.
    if t == (inferred_crop or "").strip().lower():
        return inferred_crop
    if t == (profile_crop or "").strip().lower():
        return profile_crop

    return None


def _parse_crop_word(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    crop_words = {
        # English
        "wheat": "Wheat",
        "cotton": "Cotton",
        "soybean": "Soybean",
        "maize": "Maize",
        # Hindi
        "गेहूं": "Wheat",
        "कपास": "Cotton",
        "सोयाबीन": "Soybean",
        "मक्का": "Maize",
        # Marathi
        "गहू": "Wheat",
        "कापूस": "Cotton",
        "मका": "Maize",
        # Telugu (common forms)
        "గోధుమ": "Wheat",
        "పత్తి": "Cotton",
        "సోయాబీన్": "Soybean",
        "మొక్కజొన్న": "Maize",
    }
    return crop_words.get(t)

# Onboarding configuration
VALID_DISTRICTS = ['Latur', 'Jalna', 'Nagpur']
VALID_CROPS = ['Cotton', 'Wheat', 'Soybean', 'Maize']
VALID_LANGUAGES = ['Hindi', 'Marathi', 'Telugu', 'English']

# District -> coordinates (approximate; for geo-based nudges + weather)
# Note: Former "Aurangabad" district area is now Chhatrapati Sambhajinagar; Latur used as primary Marathwada demo.
DISTRICT_COORDS = {
    'Latur': {'lat': 18.4088, 'lon': 76.5604},
    'Jalna': {'lat': 19.8347, 'lon': 75.8816},
    'Nagpur': {'lat': 21.1458, 'lon': 79.0882},
}

# Onboarding messages by dialect
ONBOARDING_MESSAGES = {
    'welcome': {
        'hi': 'नमस्ते! AgriNexus AI में आपका स्वागत है।\n\nयह AWS 10,000 AIdeas प्रतियोगिता का डेमो है। Voice/Photo और Nudges allowlist पर हैं — और public demo में nudge follow-up reminders (T+24h/T+48h) सीमित हो सकते हैं। Full access के लिए GitHub issue खोलें।\n\nटिप: सुविधाओं की सूची के लिए “HELP” भेजें।\n\nकृपया अपनी भाषा चुनें:',
        'mr': 'नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे.\n\nहा AWS 10,000 AIdeas स्पर्धेसाठीचा डेमो आहे. Voice/Photo आणि Nudges allowlist वर आहेत — आणि public demo मध्ये nudge follow-up reminders (T+24h/T+48h) मर्यादित असू शकतात. Full access साठी GitHub issue उघडा.\n\nटिप: सुविधांची यादी पाहण्यासाठी “HELP” पाठवा.\n\nकृपया तुमची भाषा निवडा:',
        'te': 'నమస్కారం! AgriNexus AI కి స్వాగతం.\n\nఇది AWS 10,000 AIdeas పోటీ కోసం డెమో. Voice/Photo మరియు Nudges allowlist లో ఉన్నాయి — అలాగే public demo లో nudge follow-up reminders (T+24h/T+48h) పరిమితం అయ్యే అవకాశం ఉంది. Full access కోసం GitHub issue పెట్టండి.\n\nటిప్: ఫీచర్ల జాబితా కోసం “HELP” పంపండి.\n\nదయచేసి మీ భాషను ఎంచుకోండి:',
        'en': 'Welcome to AgriNexus AI!\n\nThis is a demo built for AWS 10,000 AIdeas. Voice/photo and nudges are allowlisted — and on the public demo, nudge follow-up reminders (T+24h/T+48h) may be limited. Request full access via a GitHub issue.\n\nTip: send “HELP” for the capability list.\n\nPlease choose your language:'
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


def create_user_profile(phone_number: str, dialect: str, location: str, crop: str, consent, consent_source: str = 'self'):
    """Create complete user profile. `consent` may be a legacy bool or a state string
    ('granted'/'declined'); it is stored as a state string."""
    coords = DISTRICT_COORDS.get(location)
    consent_state = 'granted' if consent in (True, 'granted') else 'declined'
    now = datetime.utcnow().isoformat()
    table.put_item(
        Item={
            'PK': f'USER#{phone_number}',
            'SK': 'PROFILE',
            'phone_number': phone_number,
            'dialect': dialect,
            'location': location,
            'location_coords': list(coords) if coords else None,
            'crop': crop,
            'consent': consent_state,
            'consentSource': consent_source,
            'consentAt': now if consent_state == 'granted' else None,
            'onboarding_complete': True,
            'created_at': now,
            'GSI1PK': f'LOCATION#{location}',
            'GSI1SK': f'CROP#{crop}',
            # Public demo: one weather nudge only (no T+24h/T+48h). Set demo_tier to 'full' in Dynamo for pilot partners.
            'demo_tier': 'public',
        }
    )


def auto_assign_cohort(phone_number: str, district: str, crop: str):
    """On self-onboard, link the farmer to a single matching ACTIVE cohort by writing a
    PHONE#/MEMBERSHIP row (mirrors the platform enrollment shape) so their outcomes roll
    up to a partner program. Skips if zero or more than one active cohort matches the
    district -- deterministic, no cross-tenant mis-assignment."""
    if not district:
        return
    try:
        resp = table.query(
            IndexName='GSI2',
            KeyConditionExpression='GSI2PK = :pk',
            FilterExpression='district = :d',
            ExpressionAttributeValues={':pk': 'STATUS#active', ':d': district},
        )
    except Exception as e:
        print(f"auto_assign_cohort: query failed for {district}: {e}")
        return
    cohorts = resp.get('Items', [])
    if len(cohorts) != 1:
        print(f"auto_assign_cohort: {len(cohorts)} active cohorts for {district}; skipping")
        return
    cohort = cohorts[0]
    cohort_id = cohort.get('cohortId')
    tenant_id = cohort.get('tenantId')
    norm = phone_number.replace(' ', '').lstrip('+')
    try:
        table.put_item(
            Item={
                'PK': f'PHONE#{norm}',
                'SK': 'MEMBERSHIP',
                'GSI1PK': f'COHORT#{cohort_id}',
                'GSI1SK': f'MEMBER#{norm}',
                'phone': norm,
                'tenantId': tenant_id,
                'cohortId': cohort_id,
                'enrolledAt': datetime.utcnow().isoformat(),
            },
            ConditionExpression='attribute_not_exists(PK)',
        )
        print(f"auto_assign_cohort: linked {norm} -> cohort {cohort_id}")
    except Exception as e:
        print(f"auto_assign_cohort: membership exists or write failed for {norm}: {e}")


def _parse_language_selection(message_text: str) -> Optional[str]:
    """Return dialect code if message is a language selection, else None."""
    text_lower = message_text.lower().strip()
    
    # Handle list response IDs directly (only when from interactive reply, not free text)
    if text_lower in ['en', 'hi', 'mr', 'te']:
        return text_lower
    
    # Handle language names
    if 'hindi' in text_lower or 'हिंदी' in message_text:
        return 'hi'
    if 'marathi' in text_lower or 'मराठी' in message_text:
        return 'mr'
    if 'telugu' in text_lower or 'తెలుగు' in message_text:
        return 'te'
    if 'english' in text_lower:
        return 'en'
    return None


def handle_onboarding(phone_number: str, message_text: str, profile: Optional[Dict[str, Any]], is_interactive: bool = False) -> Dict[str, Any]:
    """
    Onboarding state machine with interactive buttons
    States: welcome -> language -> location -> crop -> consent -> complete
    Returns: {'type': 'text'|'buttons', 'content': str, 'buttons': list (optional)}
    """
    # State 1: No profile exists - treat first message as possible language choice so we don't send welcome 6x
    if not profile:
        # Only parse language from interactive replies — free text "Hi" must not match language code "hi"
        dialect = _parse_language_selection(message_text) if is_interactive else None
        if dialect:
            # First message was a language choice: create profile and go straight to location
            table.put_item(
                Item={
                    'PK': f'USER#{phone_number}',
                    'SK': 'PROFILE',
                    'phone_number': phone_number,
                    'dialect': dialect,
                    'onboarding_state': 'location',
                    'onboarding_complete': False,
                    'demo_tier': 'public',
                }
            )
            location_prompt = {
                'hi': 'बढ़िया! अब मुझे बताएं आप किस जिले में हैं?\n\n(या कोई भी जिला टाइप करें)',
                'mr': 'छान! आता मला सांगा तुम्ही कोणत्या जिल्ह्यात आहात?\n\n(किंवा कोणताही जिल्हा टाइप करा)',
                'te': 'బాగుంది! ఇప్పుడు మీరు ఏ జిల్లాలో ఉన్నారో చెప్పండి?\n\n(లేదా ఏదైనా జిల్లా టైప్ చేయండి)',
                'en': 'Great! Now tell me which district you are in?\n\n(Or type any district name)'
            }
            district_buttons = {
                'hi': ['लातूर', 'जालना', 'नागपुर'],
                'mr': ['लातूर', 'जालना', 'नागपूर'],
                'te': ['లాతూర్', 'జల్నా', 'నాగ్‌పూర్'],
                'en': ['Latur', 'Jalna', 'Nagpur']
            }
            return {
                'type': 'buttons',
                'content': location_prompt.get(dialect, location_prompt['en']),
                'buttons': district_buttons.get(dialect, district_buttons['en'])
            }
        # Not a language choice: create profile at language state and send welcome once
        table.put_item(
            Item={
                'PK': f'USER#{phone_number}',
                'SK': 'PROFILE',
                'phone_number': phone_number,
                'onboarding_state': 'language',
                'onboarding_complete': False,
                'demo_tier': 'public',
            }
        )
        multilingual_welcome = """Welcome to AgriNexus AI! 🌾

नमस्ते! AgriNexus AI में आपका स्वागत है।
नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे.
నమస్కారం! AgriNexus AI కి స్వాగతం.

Demo note: Built for AWS 10,000 AIdeas. Voice/photo and nudges are allowlisted (public demo may limit nudge follow-ups). Request full access via GitHub issues.

Tip: Send HELP / मदद / मदत / సహాయం for the capability list.

Please choose your language / कृपया अपनी भाषा चुनें:"""
        return {
            'type': 'list',
            'content': multilingual_welcome,
            'button_text': 'Select Language',
            'sections': [{
                'title': 'Available Languages',
                'rows': [
                    {'id': 'en', 'title': 'English'},
                    {'id': 'hi', 'title': 'हिंदी (Hindi)'},
                    {'id': 'mr', 'title': 'मराठी (Marathi)'},
                    {'id': 'te', 'title': 'తెలుగు (Telugu)'}
                ]
            }]
        }

    state = profile.get('onboarding_state', 'complete')
    
    # State 2: Language selection
    if state == 'language':
        dialect = _parse_language_selection(message_text)
        if dialect:
            update_user_profile(phone_number, {
                'dialect': dialect,
                'onboarding_state': 'location'
            })
            # Ask for location with buttons in user's language
            location_prompt = {
                'hi': 'बढ़िया! अब मुझे बताएं आप किस जिले में हैं?\n\n(या कोई भी जिला टाइप करें)',
                'mr': 'छान! आता मला सांगा तुम्ही कोणत्या जिल्ह्यात आहात?\n\n(किंवा कोणताही जिल्हा टाइप करा)',
                'te': 'బాగుంది! ఇప్పుడు మీరు ఏ జిల్లాలో ఉన్నారో చెప్పండి?\n\n(లేదా ఏదైనా జిల్లా టైప్ చేయండి)',
                'en': 'Great! Now tell me which district you are in?\n\n(Or type any district name)'
            }
            # District names in local script
            district_buttons = {
                'hi': ['लातूर', 'जालना', 'नागपुर'],
                'mr': ['लातूर', 'जालना', 'नागपूर'],
                'te': ['లాతూర్', 'జల్నా', 'నాగ్‌పూర్'],
                'en': ['Latur', 'Jalna', 'Nagpur']
            }
            return {
                'type': 'buttons',
                'content': location_prompt.get(dialect, location_prompt['hi']),
                'buttons': district_buttons.get(dialect, district_buttons['en'])
            }
        else:
            # Invalid selection, resend buttons
            multilingual_welcome = """Welcome to AgriNexus AI! 🌾

नमस्ते! AgriNexus AI में आपका स्वागत है।
नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे.
నమస్కారం! AgriNexus AI కి స్వాగతం.

Demo note: Built for AWS 10,000 AIdeas. Voice/photo and nudges are allowlisted (public demo may limit nudge follow-ups). Request full access via GitHub issues.

Tip: Send HELP / मदद / मदत / సహాయం for the capability list.

Please choose your language / कृपया अपनी भाषा चुनें:"""
            return {
                'type': 'list',
                'content': multilingual_welcome,
                'button_text': 'Select Language',
                'sections': [{
                    'title': 'Available Languages',
                    'rows': [
                        {'id': 'en', 'title': 'English'},
                        {'id': 'hi', 'title': 'हिंदी (Hindi)'},
                        {'id': 'mr', 'title': 'मराठी (Marathi)'},
                        {'id': 'te', 'title': 'తెలుగు (Telugu)'}
                    ]
                }]
            }
    
    # State 3: Location validation
    elif state == 'location':
        dialect = profile.get('dialect', 'hi')
        # Check if message contains valid district
        location = None
        
        # District name mappings (local script -> English)
        district_mappings = {
            # Latur
            'latur': 'Latur',
            'लातूर': 'Latur',
            'లాతూర్': 'Latur',
            # Jalna
            'jalna': 'Jalna',
            'जालना': 'Jalna',
            'జల్నా': 'Jalna',
            # Nagpur
            'nagpur': 'Nagpur',
            'नागपुर': 'Nagpur',
            'नागपूर': 'Nagpur',
            'నాగ్‌పూర్': 'Nagpur',
        }
        
        # Check for district in any language
        text_lower = message_text.lower().strip()
        for key, value in district_mappings.items():
            if key.lower() in text_lower or key in message_text:
                location = value
                break
        
        # If not found in mappings, check English names
        if not location:
            for district in VALID_DISTRICTS:
                if district.lower() in text_lower:
                    location = district
                    break
        
        # If still not found, accept any district name (for demo flexibility)
        if not location and len(message_text.strip()) > 2:
            # Accept the input as a district name
            location = message_text.strip().title()
        
        if location:
            coords = DISTRICT_COORDS.get(location)
            update_user_profile(phone_number, {
                'location': location,
                'location_coords': list(coords) if coords else None,
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
            # District names in local script
            district_buttons = {
                'hi': ['लातूर', 'जालना', 'नागपुर'],
                'mr': ['लातूर', 'जालना', 'नागपूर'],
                'te': ['లాతూర్', 'జల్నా', 'నాగ్‌పూర్'],
                'en': ['Latur', 'Jalna', 'Nagpur']
            }
            return {
                'type': 'buttons',
                'content': location_prompt.get(dialect, location_prompt['hi']),
                'buttons': district_buttons.get(dialect, district_buttons['en'])
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
    
    # State 4.5: Pending consent (partner-enrolled farmer's first contact)
    elif state == 'pending_consent':
        # Prompt for consent, then move to the consent state so the farmer's NEXT
        # reply (Yes/No) is read as the answer -- their first "Hi" must not be.
        dialect = profile.get('dialect', 'hi')
        district = profile.get('location', '') or ''
        crop = profile.get('crop', '') or ''
        update_user_profile(phone_number, {'onboarding_state': 'consent'})
        consent_buttons = {
            'hi': ['हाँ ✅', 'नहीं ❌'],
            'mr': ['होय ✅', 'नाही ❌'],
            'te': ['అవును ✅', 'కాదు ❌'],
            'en': ['Yes ✅', 'No ❌']
        }
        invite = {
            'hi': f'आपको {district} में {crop} सलाह के लिए नामांकित किया गया है। मौसम आधारित खेती सलाह पाने के लिए "हाँ" भेजें।',
            'mr': f'तुम्हाला {district} मध्ये {crop} सल्ल्यासाठी नोंदवले आहे. हवामान-आधारित सल्ला मिळवण्यासाठी "होय" पाठवा.',
            'te': f'{district}లో {crop} సలహా కోసం మీరు నమోదు అయ్యారు. వాతావరణ సలహా కోసం "అవును" పంపండి.',
            'en': f"You've been enrolled for {crop} advisories in {district}. Reply YES to start receiving weather-based farming advice."
        }
        return {
            'type': 'buttons',
            'content': invite.get(dialect, invite['en']),
            'buttons': consent_buttons.get(dialect, consent_buttons['hi'])
        }

    # State 5: Consent
    elif state == 'consent':
        dialect = profile.get('dialect', 'hi')
        location = profile.get('location')
        crop = profile.get('crop')
        
        # Check for consent keywords (from button or text)
        text_lower = message_text.lower()
        consent_source = profile.get('consentSource', 'self')
        granted = any(word in text_lower for word in ['yes', 'हाँ', 'हां', 'होय', 'అవును', '✅'])
        consent_state = 'granted' if granted else 'declined'
        
        # Complete onboarding: record the consent state, link the cohort
        if consent_source == 'partner':
            # Partner pre-seeded this profile; the MEMBERSHIP already exists.
            updates = {'consent': consent_state, 'onboarding_complete': True, 'onboarding_state': 'complete'}
            if granted:
                updates['consentAt'] = datetime.utcnow().isoformat()
            update_user_profile(phone_number, updates)
        else:
            create_user_profile(phone_number, dialect, location, crop, consent_state, consent_source='self')
            if granted:
                auto_assign_cohort(phone_number, location, crop)
        return {
            'type': 'text',
            'content': ONBOARDING_MESSAGES['onboarding_complete'][dialect]
        }
    
    return {
        'type': 'text',
        'content': "Error in onboarding flow"
    }


def convert_floats_to_decimal(obj):
    """
    Recursively convert float values to Decimal for DynamoDB compatibility.
    DynamoDB doesn't support float types - must use Decimal instead.
    """
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def is_rag_refusal_response(text: str) -> bool:
    """
    Detect KB no-hit / refusal replies. Generic FAO/ICAR footer must not be appended to these
    (it implies a grounded answer when there was none).
    """
    if not text or not text.strip():
        return True
    low = text.lower()
    if "don't have information" in low or "do not have information" in low:
        return True
    if "i don't have" in low and "information" in low:
        return True
    if "no information" in low and "knowledge base" in low:
        return True
    if "i can only help with farming" in low:
        return True
    # Hindi (model paraphrases the English refusal)
    if "जानकारी संग्रह" in text:
        return True
    if "मेरे पास" in text and "जानकारी नहीं" in text:
        return True
    if "दिए गए संदर्भ" in text and (
        "विशिष्ट जानकारी नहीं" in text or "जानकारी नहीं दी गई" in text
    ):
        return True
    if "ज्ञानकोषात" in text and ("माहिती नाही" in text or "नाही" in text):
        return True
    if "माझ्याकडे" in text and "माहिती नाही" in text:
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


def strip_llm_numeric_source_footer(text: str, source_keyword: str) -> str:
    """
    Remove trailing LLM-added placeholders like 'स्रोत: 1' or 'स्रोत: 3, 4, 5' (ADR 0005).
    Only strips when the line contains digits/commas/spaces after the keyword — not real titles.
    """
    if not text or source_keyword not in text:
        return text
    kw = re.escape(source_keyword)
    # Digits / commas / spaces only after keyword (not real document titles)
    pattern = rf"(?:\n\s*)*{kw}\s*[\d,\s]+$"
    return re.sub(pattern, "", text.rstrip(), flags=re.MULTILINE).rstrip()


def strip_llm_numeric_source_footer_flexible(text: str, label: str) -> str:
    """Like strip_llm_numeric_source_footer but allows optional spaces around the colon."""
    if not text:
        return text
    lb = re.escape(label).rstrip(":").rstrip()
    pattern = rf"(?:\n\s*)*{lb}\s*:\s*[\d,\s]+$"
    return re.sub(pattern, "", text.rstrip(), flags=re.MULTILINE).rstrip()


def strip_all_numeric_source_footers(text: str) -> str:
    """Strip numeric citation junk for any locale keyword the model might emit."""
    telugu_source = "\u0c2e\u0c42\u0c32\u0c02:"
    hindi_sors = "\u0938\u094b\u0930\u094d\u0938"  # loanword "source" in Devanagari
    for kw in ("स्रोत:", "स्त्रोत:", f"{hindi_sors}:", telugu_source, "Source:", "source:"):
        text = strip_llm_numeric_source_footer(text, kw)
    # Second pass: flexible spacing around colon (e.g. space before colon)
    for label in ("स्रोत", "स्त्रोत", hindi_sors, "Source", "source", telugu_source.rstrip(":")):
        text = strip_llm_numeric_source_footer_flexible(text, label)
    return text


def source_labels_from_citations(citations: Any) -> List[str]:
    """Basenames from S3 URIs in retrieve_and_generate citations (same idea as web-chat handler)."""
    if not citations:
        return []
    labels: List[str] = []
    for citation in citations:
        for ref in citation.get("retrievedReferences") or []:
            loc = ref.get("location") or {}
            s3_loc = loc.get("s3Location") or {}
            uri = s3_loc.get("uri") or ""
            if not uri:
                continue
            name = uri.rstrip("/").split("/")[-1]
            if name and name not in labels:
                labels.append(name)
    return labels


def save_message(phone_number: str, wamid: str, message_data: Dict[str, Any], response_text: str, source_citation: str):
    """Save message to DynamoDB with TTL"""
    timestamp = datetime.utcnow().isoformat()
    ttl = int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days
    
    # Convert any float values to Decimal for DynamoDB
    message_data_clean = convert_floats_to_decimal(message_data)
    
    table.put_item(
        Item={
            'PK': f'USER#{phone_number}',
            'SK': f'MSG#{timestamp}',
            'wamid': wamid,
            'message': message_data_clean,
            'response': response_text,
            'source_citation': source_citation,
            'ttl': ttl
        }
    )


def query_bedrock(query: str, dialect: str = 'hi', session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Query Bedrock Knowledge Base with RAG
    
    Args:
        query: User's question
        dialect: User's language dialect
        session_id: Optional session ID for conversation context (uses phone number)
    
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
    
    language_instruction = language_instructions.get(dialect, language_instructions['hi'])

    # For non-English queries, append English keywords to improve KB vector
    # retrieval (documents are primarily in English).  The generation prompt
    # still instructs the model to respond in the user's language.
    retrieval_query = query
    if dialect != 'en':
        _keyword_hints = {
            'कपास': 'cotton', 'कापूस': 'cotton', 'పత్తి': 'cotton',
            'गेहूं': 'wheat', 'गहू': 'wheat', 'గోధుమ': 'wheat',
            'सोयाबीन': 'soybean', 'సోయాబీన్': 'soybean',
            'मक्का': 'maize', 'मका': 'maize', 'మొక్కజొన్న': 'maize',
            'धान': 'rice', 'भात': 'rice', 'వరి': 'rice',
            'कीट': 'pest', 'कीड': 'pest', 'పురుగు': 'pest',
            'रोग': 'disease', 'వ్యాధి': 'disease',
            'स्प्रे': 'spray', 'फवारणी': 'spray', 'స్ప్రే': 'spray',
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
2. If the Context does not contain relevant information to answer the question, you MUST respond: "I don't have information about this in my knowledge base. Please contact your local KVK (Krishi Vigyan Kendra) or agricultural extension officer."
3. NEVER make up or invent information. NEVER hallucinate.
4. If the question is about people, places, or things not related to farming, respond: "I can only help with farming questions. Please ask about crops, pests, fertilizers, or farm management."

RESPONSE STYLE (when you DO have relevant context):
- Sound like a calm, practical TV or radio farm advisory (DD Kisan / extension bulletin style): direct and trustworthy, not a research paper.
- Lead with the ACTION the farmer should take first — not long background.
- Main answer: at most 2-3 short sentences. For simple when / how much / what questions, give the direct answer in one or two sentences first.
- Add at most one short sentence for "why" or "what to watch" only if it changes what they should do.
- Use everyday words; if a technical term is needed, explain it in a few words.
- Avoid long paragraphs, dense lists, and copying long passages from the context.
- DO NOT add any source citation or reference line at the end. The system will add it automatically.
- NEVER end with a "source" line that lists only numbers or citation indices (e.g. comma-separated digits like 3, 4, 5). No Devanagari or English label before such numbers.

CRITICAL: If you said "I don't have information" OR "I can only help with farming questions", DO NOT ADD ANY SOURCE CITATION. NO "स्रोत:", NO "Source:", NOTHING. Just end your response immediately after the refusal message.

IMPORTANT RESTRICTIONS:
- ONLY answer questions about agriculture, farming, crops, pests, diseases, fertilizers, weather, and farm management
- If the question is about human health, medical issues, personal problems, or non-farming topics, respond: "I can only help with farming questions. Please ask about crops, pests, fertilizers, or farm management."
- Do NOT provide medical advice, health recommendations, or personal counseling
- Stay strictly within agricultural domain

Question: $query$

Context: $search_results$

REMEMBER: If the Context above does not contain information to answer the Question, you MUST say "I don't have information about this in my knowledge base." DO NOT make up answers.'''
        }
    }
    
    # Only add guardrail if it's configured
    if GUARDRAIL_ID and GUARDRAIL_ID.strip():
        generation_config['guardrailConfiguration'] = {
            'guardrailId': GUARDRAIL_ID,
            'guardrailVersion': GUARDRAIL_VERSION
        }
    
    # Get model ARN from environment variable (with fallback to Claude 3 Sonnet)
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
    
    # Build request parameters
    request_params = {
        'input': {'text': retrieval_query},
        'retrieveAndGenerateConfiguration': rag_config
    }
    
    # Try with sessionId first (for conversation context)
    if session_id:
        request_params['sessionId'] = session_id
        print(f"Attempting to use session ID for conversation context: {session_id[:10]}***")
        try:
            response = bedrock_agent.retrieve_and_generate(**request_params)
            print(f"Successfully used existing session: {session_id[:10]}***")
            return {
                'text': response['output']['text'],
                'citations': response.get('citations', []),
                'sessionId': response.get('sessionId')
            }
        except bedrock_agent.exceptions.ValidationException as e:
            # Session doesn't exist yet, create new one by calling without sessionId
            if 'Session with Id' in str(e) and 'is not valid' in str(e):
                print(f"Session {session_id[:10]}*** not found, creating new session")
                del request_params['sessionId']
            else:
                raise
    
    # Call without sessionId (creates new session)
    response = bedrock_agent.retrieve_and_generate(**request_params)
    
    if session_id:
        print(f"Created new session: {response.get('sessionId', 'unknown')}")
    
    return {
        'text': response['output']['text'],
        'citations': response.get('citations', []),
        'sessionId': response.get('sessionId')
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process messages from SQS"""
    def _send_help(from_number: str, dialect: str):
        request_url = "https://github.com/prasadt1/agrinexus-ai/issues/new?template=demo-request.md"
        help_messages = {
            'hi': '''🌾 AgriNexus AI - मदद

मैं आपकी खेती में मदद कर सकता हूं:

📝 सवाल पूछें:
• "कपास में कीट कैसे नियंत्रित करें?"
• "गेहूं में खाद कब डालें?"
• "मौसम के अनुसार क्या करें?"

🎤 वॉइस (allowlisted):
• वॉइस नोट भेजें — मैं ट्रांसक्राइब करके जवाब दूंगा

📸 फोटो भेजें:
• पत्तियों की फोटो
• कीट/रोग की फोटो
• मैं पहचान करूंगा और सलाह दूंगा

🔔 नज (opt‑in):
• सही मौसम में स्प्रे/कृषि कार्य की याद दिलाना
• Public demo में follow‑up reminders (T+24h/T+48h) सीमित हो सकते हैं

बस अपना सवाल टाइप करें या फोटो भेजें!

Full access (voice/photo/nudges): GitHub request → {request_url}''',
            'mr': '''🌾 AgriNexus AI - मदत

मी तुमच्या शेतीत मदत करू शकतो:

📝 प्रश्न विचारा:
• "कापसात किडे कसे नियंत्रित करावे?"
• "गहूमध्ये खत कधी घालावे?"
• "हवामानानुसार काय करावे?"

🎤 व्हॉइस (allowlisted):
• व्हॉइस नोट पाठवा — मी ट्रान्सक्राइब करून उत्तर देईन

📸 फोटो पाठवा:
• पानांचा फोटो
• किडे/रोगाचा फोटो
• मी ओळखेन आणि सल्ला देईन

🔔 नज (opt‑in):
• योग्य हवामानात फवारणी/कृषी कामाची आठवण
• Public demo मध्ये follow‑up reminders (T+24h/T+48h) मर्यादित असू शकतात

फक्त तुमचा प्रश्न टाइप करा किंवा फोटो पाठवा!

Full access (voice/photo/nudges): GitHub request → {request_url}''',
            'te': '''🌾 AgriNexus AI - సహాయం

నేను మీ వ్యవసాయంలో సహాయం చేయగలను:

📝 ప్రశ్నలు అడగండి:
• "పత్తిలో పురుగులను ఎలా నియంత్రించాలి?"
• "గోధుమలో ఎరువులు ఎప్పుడు వేయాలి?"
• "వాతావరణం ప్రకారం ఏమి చేయాలి?"

🎤 వాయిస్ (allowlisted):
• వాయిస్ నోట్ పంపండి — నేను ట్రాన్స్‌క్రైబ్ చేసి సమాధానం ఇస్తాను

📸 ఫోటో పంపండి:
• ఆకుల ఫోటో
• పురుగు/వ్యాధి ఫోటో
• నేను గుర్తించి సలహా ఇస్తాను

🔔 నజ్ (opt‑in):
• సరైన వాతావరణంలో స్ప్రే/పనికి రిమైండర్
• Public demo లో follow‑up reminders (T+24h/T+48h) పరిమితం అయ్యే అవకాశం ఉంది

మీ ప్రశ్న టైప్ చేయండి లేదా ఫోటో పంపండి!

Full access (voice/photo/nudges): GitHub request → {request_url}''',
            'en': '''🌾 AgriNexus AI - Help

I can help you with your farming:

📝 Ask Questions:
• "How to control cotton pests?"
• "When to apply fertilizer to wheat?"
• "What to do based on weather?"

🎤 Voice (allowlisted):
• Send a voice note — I’ll transcribe and reply

📸 Photos (allowlisted):
• Leaf photos
• Pest/disease photos
• I'll identify and advise

🔔 Nudges (opt‑in):
• Weather-timed reminders to do farm actions (e.g., spraying)
• Public demo may limit follow-up reminders (T+24h/T+48h)

Just type your question or send a photo!

Full access (voice/photo/nudges): GitHub request → {request_url}'''
        }
        send_whatsapp_message(
            from_number,
            help_messages.get(dialect, help_messages['hi']).format(request_url=request_url)
        )

    for record in event['Records']:
        body = json.loads(record['body'])
        
        wamid = body['wamid']
        from_number = body['from']
        message_type = body['type']
        message = body['message']
        
        # Get user profile
        profile = get_user_profile(from_number)
        print(f"DEBUG: profile={profile}, onboarding_complete={profile.get('onboarding_complete') if profile else None}")
        
        # Check if onboarding is complete
        if not profile or not profile.get('onboarding_complete', False):
            # Handle onboarding
            text = ''
            if message_type == 'text':
                text = message.get('text', {}).get('body', '')
            elif message_type == 'interactive':
                # Extract interactive reply (button or list)
                interactive = message.get('interactive', {})
                interactive_type = interactive.get('type', '')
                
                if interactive_type == 'button_reply':
                    # Button reply: use title
                    button_reply = interactive.get('button_reply', {})
                    text = button_reply.get('title', '')
                elif interactive_type == 'list_reply':
                    # List reply: use id (e.g., 'en', 'hi', 'mr', 'te')
                    list_reply = interactive.get('list_reply', {})
                    text = list_reply.get('id', '')
                else:
                    text = ''
            
            if text:
                # HELP must work even during onboarding (judges try it immediately).
                stripped = text.strip()
                upper = stripped.upper()
                if upper in ['HELP', 'मदद', 'मदत', 'సహాయం']:
                    # If they ask in a specific script, respond in that language even before selection.
                    if stripped == 'मदद':
                        dialect = 'hi'
                    elif stripped == 'मदत':
                        dialect = 'mr'
                    elif stripped == 'సహాయం':
                        dialect = 'te'
                    else:
                        # During onboarding (before dialect is chosen) default HELP to English for demos.
                        dialect = (profile or {}).get('dialect') or 'en'
                    _send_help(from_number, dialect)
                    continue

                onboarding_response = handle_onboarding(from_number, text, profile, is_interactive=(message_type == 'interactive'))
                
                # Send appropriate message type (text, buttons, or list)
                if onboarding_response['type'] == 'buttons':
                    send_whatsapp_buttons(from_number, onboarding_response['content'], onboarding_response['buttons'])
                elif onboarding_response['type'] == 'list':
                    from common.whatsapp import send_whatsapp_list
                    send_whatsapp_list(
                        from_number,
                        onboarding_response['content'],
                        onboarding_response['button_text'],
                        onboarding_response['sections']
                    )
                else:
                    send_whatsapp_message(from_number, onboarding_response['content'])
                
                # Re-fetch profile to get updated state for next message in batch
                profile = get_user_profile(from_number)
            continue
        
        dialect = profile.get('dialect', 'hi')
        approved = is_approved_user(table, from_number)
        
        # Process based on message type
        if message_type in ('text', 'interactive'):
            text = ''
            if message_type == 'text':
                text = message.get('text', {}).get('body', '')
            else:
                interactive = message.get('interactive', {}) if isinstance(message, dict) else {}
                interactive_type = interactive.get('type', '')
                if interactive_type == 'button_reply':
                    button_reply = interactive.get('button_reply', {})
                    text = button_reply.get('title', '')
                elif interactive_type == 'list_reply':
                    list_reply = interactive.get('list_reply', {})
                    text = list_reply.get('title') or list_reply.get('id', '')

            # If we are waiting for crop confirmation from a previous photo, intercept first.
            pending = _get_pending_crop_confirm(from_number)
            if pending:
                chosen = _parse_crop_confirm_reply(
                    text,
                    inferred_crop=str(pending.get("inferred_crop") or ""),
                    profile_crop=str(pending.get("profile_crop") or profile.get("crop") or ""),
                )
                if chosen:
                    bucket = pending.get("bucket") or os.environ.get("TEMP_AUDIO_BUCKET")
                    key = pending.get("key")
                    if bucket and key:
                        try:
                            obj = s3.get_object(Bucket=bucket, Key=key)
                            image_bytes = obj["Body"].read()
                            district = profile.get("district") or profile.get("location")
                            result = analyzer.analyze_crop_image(image_bytes, dialect, chosen, district=district)
                            reply_text = str(result.get("recommendations") or "")
                            save_message(from_number, wamid, message, reply_text, "vision_reprocess")
                            send_whatsapp_message(from_number, reply_text)
                        finally:
                            _delete_pending_crop_confirm(from_number)
                        continue

                # Not a crop-confirm response; fall through to normal handling.

            # "Last image" override (beta-only via env flag).
            # If the user sends just a crop name (e.g., "Cotton") after an image,
            # re-run analysis on the most recent saved image.
            last_img = _get_last_image_pointer(from_number)
            chosen = _parse_crop_word(text)
            if last_img and chosen:
                bucket = last_img.get("bucket") or os.environ.get("TEMP_AUDIO_BUCKET")
                key = last_img.get("key")
                if bucket and key:
                    try:
                        obj = s3.get_object(Bucket=bucket, Key=key)
                        image_bytes = obj["Body"].read()
                        district = profile.get("district") or profile.get("location")
                        result = analyzer.analyze_crop_image(image_bytes, dialect, chosen, district=district)
                        reply_text = str(result.get("recommendations") or "")
                        save_message(from_number, wamid, message, reply_text, "vision_last_image_override")
                        send_whatsapp_message(from_number, reply_text)
                    finally:
                        _delete_last_image_pointer(from_number)
                    continue
            
            # Check for DONE/NOT YET keywords - these are handled by response detector
            done_keywords = ['हो गया', 'कर दिया', 'हो गया है', 'कर लिया', 'done', 'completed',
                           'झाला', 'केला', 'पूर्ण झाला', 'అయ్యింది', 'చేశాను', 'పూర్తయింది']
            not_yet_keywords = ['अभी नहीं', 'बाद में', 'नहीं किया', 'not yet', 'later',
                              'नाही झाला', 'नंतर', 'अजून नाही', 'ఇంకా లేదు', 'తర్వాత', 'చేయలేదు']
            
            text_lower = text.lower()
            is_done_or_not_yet = any(keyword.lower() in text_lower for keyword in done_keywords + not_yet_keywords)
            
            if is_done_or_not_yet:
                print(f"Skipping DONE/NOT YET message - handled by response detector")
                continue
            
            # Check for HELP command
            if text.strip().upper() in ['HELP', 'मदद', 'मदत', 'సహాయం']:
                _send_help(from_number, dialect)
                continue
            
            # Check for DONE/NOT YET keywords (handled by response detector)
            # Just process as normal query
            
            # Immediate text-query ack only (voice already got VOICE_RECEIVED_ACK in VoiceProcessor)
            voice_source = message.get('_source')
            if voice_source not in ('voice', 'voice_test'):
                ack_messages = {
                    'hi': '✓ आपका सवाल मिल गया। जवाब तैयार कर रहे हैं...',
                    'mr': '✓ तुमचा प्रश्न मिळाला. उत्तर तयार करत आहे...',
                    'te': '✓ మీ ప్రశ్న అందింది. సమాధానం తయారు చేస్తున్నాము...',
                    'en': '✓ Question received. Preparing answer...'
                }
                send_whatsapp_message(from_number, ack_messages.get(dialect, ack_messages['hi']))
            
            # Voice: skip Bedrock session so retrieve+generate is not skewed by prior turns;
            # STT text also differs from typed queries.
            rag_session = (
                None
                if voice_source in ("voice", "voice_test")
                else from_number
            )
            result = query_bedrock(text, dialect, session_id=rag_session)
            
            # Extract source citation from response or add generic attribution
            response_text = result["text"]
            source_keywords = {
                'hi': 'स्रोत:',
                'mr': 'स्त्रोत:',
                'te': 'మూలం:',
                'en': 'Source:'
            }
            source_keyword = source_keywords.get(dialect, 'Source:')
            
            # Strip LLM citation artifacts; append doc names or generic line
            response_text = strip_llm_xml_citation_tags(response_text)
            response_text = strip_all_numeric_source_footers(response_text)
            has_source = source_keyword in response_text

            if not has_source and not is_rag_refusal_response(response_text):
                labels = source_labels_from_citations(result.get("citations"))
                if labels:
                    max_show = 5
                    tail = ", ".join(labels[:max_show])
                    if len(labels) > max_show:
                        tail += " …"
                    response_text += f"\n\n{source_keyword} {tail}"
                else:
                    source_attributions = {
                        'hi': 'FAO/ICAR कृषि मार्गदर्शिका',
                        'mr': 'FAO/ICAR शेती मार्गदर्शक',
                        'te': 'FAO/ICAR వ్యవసాయ మార్గదర్శకం',
                        'en': 'FAO/ICAR Agricultural Guidelines'
                    }
                    source_text = source_attributions.get(dialect, source_attributions['en'])
                    response_text += f"\n\n{source_keyword} {source_text}"

            reply_text = maybe_append_helpline_footer(
                response_text,
                text,
                dialect,
                profile.get("location") if profile else None,
            )
            
            # Save to DynamoDB
            save_message(from_number, wamid, message, reply_text, str(result['citations']))
            
            # Check if user wants voice response (Hindi, Marathi, English supported)
            send_voice = (approved and dialect in ['hi', 'mr', 'en'] and 
                         (message.get('_source') in ('voice', 'voice_test') or profile.get('voicePreference', False)))
            
            if send_voice:
                # Full answer as text first (WhatsApp audio path ignores body text)
                send_whatsapp_message(from_number, reply_text)
                tts_text = truncate_for_voice(reply_text)
                if len(tts_text) < len(reply_text.strip()):
                    tts_text = voice_truncation_prefix(dialect) + tts_text
                audio_url = text_to_speech(tts_text, dialect, from_number)
                if audio_url:
                    send_whatsapp_message(from_number, '', audio_url=audio_url)
                else:
                    # Already sent full text above
                    pass
            else:
                # Send text response
                send_whatsapp_message(from_number, reply_text)
        
        elif message_type == 'image':
            if not approved:
                gate_msg = {
                    'hi': f'फोटो विश्लेषण सुविधा अभी बंद है। कृपया टेक्स्ट में प्रश्न भेजें। {allowlist_expiry_hint(dialect)}',
                    'mr': f'फोटो विश्लेषण सुविधा सध्या बंद आहे. कृपया प्रश्न टेक्स्टमध्ये पाठवा. {allowlist_expiry_hint(dialect)}',
                    'te': f'ఫోటో విశ్లేషణ ఫీచర్ ప్రస్తుతం అందుబాటులో లేదు. దయచేసి టెక్స్ట్‌లో ప్రశ్న అడగండి. {allowlist_expiry_hint(dialect)}',
                    'en': f'Photo analysis is not enabled in the public demo. Please ask in text. {allowlist_expiry_hint(dialect)}',
                }
                send_whatsapp_message(from_number, gate_msg.get(dialect, gate_msg['en']))
                continue

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
            analysis = analyzer.process_image_message(message, profile)

            # Record last image pointer for user-driven override (beta-only via env flag).
            if isinstance(analysis, dict):
                s3info = analysis.get("s3") or {}
                if isinstance(s3info, dict) and s3info.get("bucket") and s3info.get("key"):
                    _put_last_image_pointer(from_number, str(s3info["bucket"]), str(s3info["key"]))

            # If vision asks for a crop override confirmation, store pending state and ask user.
            if isinstance(analysis, dict) and analysis.get("pending_crop_confirm"):
                pending = dict(analysis["pending_crop_confirm"])
                pending.setdefault("dialect", dialect)
                pending.setdefault("profile_crop", profile.get("crop"))
                _put_pending_crop_confirm(from_number, pending)
                text_out = str(analysis.get("text") or "")
                save_message(from_number, wamid, message, text_out, "vision_crop_confirm")
                buttons = analysis.get("buttons") if isinstance(analysis, dict) else None
                if isinstance(buttons, list) and buttons:
                    send_whatsapp_buttons(from_number, text_out, buttons)
                else:
                    send_whatsapp_message(from_number, text_out)
                continue

            # Backward compatible (string return)
            if isinstance(analysis, dict):
                analysis = str(analysis.get("text") or analysis.get("recommendations") or "")
            
            # Save to DynamoDB
            save_message(from_number, wamid, message, analysis, 'vision_analysis')
            
            # Send response (text only - no voice for image responses)
            send_whatsapp_message(from_number, analysis)
        
        elif message_type == 'audio':
            # Audio messages are normally handled by VoiceProcessor Lambda (gated in webhook).
            if not approved:
                gate_msg = {
                    'hi': f'अभी वॉइस सुविधा बंद है। कृपया टेक्स्ट में प्रश्न भेजें। {allowlist_expiry_hint(dialect)}',
                    'mr': f'सध्या व्हॉइस सुविधा बंद आहे. कृपया प्रश्न टेक्स्टमध्ये पाठवा. {allowlist_expiry_hint(dialect)}',
                    'te': f'ప్రస్తుతం వాయిస్ ఫీచర్ అందుబాటులో లేదు. దయచేసి టెక్స్ట్‌లో ప్రశ్న అడగండి. {allowlist_expiry_hint(dialect)}',
                    'en': f'Voice is not enabled in the public demo. Please ask in text. {allowlist_expiry_hint(dialect)}',
                }
                send_whatsapp_message(from_number, gate_msg.get(dialect, gate_msg['en']))
                continue
            print(f"Audio message - should be handled by VoiceProcessor")

        elif message_type == 'document':
            # WhatsApp document uploads (e.g. .xlsx). We don't support parsing files in the demo.
            doc = (message or {}).get('document', {}) if isinstance(message, dict) else {}
            filename = (doc.get('filename') or '').strip()
            suffix = f" ({filename})" if filename else ""
            msg = {
                'hi': f'यह फ़ाइल{suffix} अभी पढ़ी नहीं जा सकती। कृपया टेक्स्ट में प्रश्न लिखें या फसल/पत्ते की फोटो भेजें।',
                'mr': f'ही फाईल{suffix} सध्या वाचता येत नाही. कृपया प्रश्न टेक्स्टमध्ये लिहा किंवा पिक/पानाचा फोटो पाठवा.',
                'te': f'ఈ ఫైల్{suffix} ప్రస్తుతం చదవలేము. దయచేసి ప్రశ్నను టెక్స్ట్‌లో పంపండి లేదా పంట/ఆకు ఫోటో పంపండి.',
                'en': f'I can’t read files{suffix} yet. Please paste the key text or ask your question in chat, or send a crop/leaf photo.'
            }
            send_whatsapp_message(from_number, msg.get(dialect, msg['en']))
            continue

        else:
            # Unknown/unsupported message types: fail closed with a helpful reply.
            msg = {
                'hi': 'यह अटैचमेंट/फॉर्मेट अभी समर्थित नहीं है। कृपया टेक्स्ट भेजें या फसल/पत्ते की फोटो भेजें।',
                'mr': 'हा अटॅचमेंट/फॉरमॅट सध्या समर्थित नाही. कृपया टेक्स्ट पाठवा किंवा पिक/पानाचा फोटो पाठवा.',
                'te': 'ఈ అటాచ్‌మెంట్/ఫార్మాట్ ప్రస్తుతం సపోర్ట్ కాదు. దయచేసి టెక్స్ట్ పంపండి లేదా పంట/ఆకు ఫోటో పంపండి.',
                'en': 'That attachment type isn’t supported yet. Please send text or a crop/leaf photo.'
            }
            send_whatsapp_message(from_number, msg.get(dialect, msg['en']))
            continue
    
    return {'statusCode': 200}
