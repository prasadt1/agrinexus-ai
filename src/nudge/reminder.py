"""
Reminder Sender
Sends T+24h and T+48h reminders if task not completed
"""
import json
import os
import boto3
from typing import Dict, Any
from common.whatsapp import send_whatsapp_message, send_whatsapp_buttons

dynamodb = boto3.resource('dynamodb')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)

CROP_INFO = {
    'Cotton':  {'hi': ('कपास', 'कीटनाशक'),    'mr': ('कापूस', 'कीटकनाशक'),    'te': ('పత్తి', 'పురుగుమందు'),       'en': ('cotton', 'pesticide')},
    'Wheat':   {'hi': ('गेहूं', 'फफूंदनाशक'),  'mr': ('गहू', 'बुरशीनाशक'),      'te': ('గోధుమ', 'శిలీంధ్రనాశని'),    'en': ('wheat', 'fungicide')},
    'Soybean': {'hi': ('सोयाबीन', 'कीटनाशक'), 'mr': ('सोयाबीन', 'कीटकनाशक'),  'te': ('సోయాబీన్', 'పురుగుమందు'),   'en': ('soybean', 'pesticide')},
    'Maize':   {'hi': ('मक्का', 'कीटनाशक'),   'mr': ('मका', 'कीटकनाशक'),       'te': ('మొక్కజొన్న', 'పురుగుమందు'), 'en': ('maize', 'pesticide')},
}

REMINDER_BUTTONS = {
    'hi': [{"id": "done", "title": "हो गया"}, {"id": "not_yet", "title": "अभी नहीं"}],
    'mr': [{"id": "done", "title": "झाला"}, {"id": "not_yet", "title": "नाही झाला"}],
    'te': [{"id": "done", "title": "అయ్యింది"}, {"id": "not_yet", "title": "ఇంకా లేదు"}],
    'en': [{"id": "done", "title": "Done"}, {"id": "not_yet", "title": "Not Yet"}],
}

REMINDER_TEMPLATES = {
    'hi': {
        'T+24h': 'याद दिलाना: कल हमने {crop} में {spray_type} स्प्रे के लिए कहा था। क्या आपने कर लिया?',
        'T+48h': 'अंतिम याद दिलाना: {crop} में {spray_type} स्प्रे अभी बाकी है। कृपया जल्द करें।'
    },
    'mr': {
        'T+24h': 'आठवण: काल आम्ही {crop} साठी {spray_type} फवारणी करण्यास सांगितले होते। तुम्ही केले का?',
        'T+48h': 'शेवटची आठवण: {crop} साठी {spray_type} फवारणी अजून बाकी आहे. कृपया लवकर करा.'
    },
    'te': {
        'T+24h': 'గుర్తు: నిన్న {crop}లో {spray_type} స్ప్రే చేయమని చెప్పాము. మీరు చేశారా?',
        'T+48h': 'చివరి గుర్తు: {crop}లో {spray_type} స్ప్రే ఇంకా మిగిలి ఉంది. దయచేసి త్వరగా చేయండి.'
    },
    'en': {
        'T+24h': 'Reminder: Yesterday we suggested {spray_type} spray for your {crop}. Have you done it?',
        'T+48h': 'Final reminder: {spray_type} spray for your {crop} is still pending. Please do it soon.'
    }
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send reminder if task not completed"""
    phone_number = event['phone_number']
    nudge_id = event['nudge_id']
    reminder_type = event['reminder_type']
    
    # Check nudge status
    response = table.get_item(
        Key={
            'PK': f'USER#{phone_number}',
            'SK': f'NUDGE#{nudge_id}'
        }
    )
    
    nudge = response.get('Item')
    if not nudge:
        return {'statusCode': 404, 'message': 'Nudge not found'}
    
    status = nudge.get('status')
    
    # Handle auto-expiry (T+72h - no response from farmer)
    if reminder_type == 'EXPIRY':
        if status not in ['DONE', 'EXPIRED']:
            # Mark as EXPIRED (farmer never responded)
            table.update_item(
                Key={
                    'PK': f'USER#{phone_number}',
                    'SK': f'NUDGE#{nudge_id}'
                },
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'EXPIRED'
                }
            )
            print(f"Auto-expired nudge {nudge_id} (no response after T+48h)")
        return {'statusCode': 200, 'message': 'Nudge expired'}
    
    # Get user profile to determine dialect
    try:
        profile_response = table.get_item(
            Key={
                'PK': f'USER#{phone_number}',
                'SK': 'PROFILE'
            }
        )
        dialect = profile_response.get('Item', {}).get('dialect', 'hi')
    except:
        dialect = 'hi'  # Default to Hindi if profile not found
    
    crop = nudge.get('crop', 'Cotton')
    crop_data = CROP_INFO.get(crop, CROP_INFO['Cotton'])
    crop_name, spray_type = crop_data.get(dialect, crop_data['hi'])

    # Only send reminder if not completed
    if status != 'DONE':
        template = REMINDER_TEMPLATES.get(dialect, REMINDER_TEMPLATES['hi'])
        message = template.get(reminder_type, template['T+24h']).format(crop=crop_name, spray_type=spray_type)
        
        # Send WhatsApp message with DONE/NOT YET buttons
        buttons = REMINDER_BUTTONS.get(dialect, REMINDER_BUTTONS['hi'])
        sent = send_whatsapp_buttons(phone_number, message, buttons)
        if not sent:
            send_whatsapp_message(phone_number, message)
        
        # Update nudge record
        table.update_item(
            Key={
                'PK': f'USER#{phone_number}',
                'SK': f'NUDGE#{nudge_id}'
            },
            UpdateExpression='SET #status = :status, lastReminder = :reminder',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'REMINDED',
                ':reminder': reminder_type
            }
        )
        
        return {'statusCode': 200, 'message': 'Reminder sent'}
    else:
        return {'statusCode': 200, 'message': 'Task already completed'}
