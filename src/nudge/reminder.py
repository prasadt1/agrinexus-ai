"""
Reminder Sender
Sends T+24h and T+48h reminders if task not completed
"""
import json
import os
import sys
import boto3
from typing import Dict, Any
from common.whatsapp import send_whatsapp_message, send_whatsapp_buttons

_nudge_dir = os.path.dirname(os.path.abspath(__file__))
if _nudge_dir not in sys.path:
    sys.path.insert(0, _nudge_dir)
from nudge_copy import build_reminder_message

dynamodb = boto3.resource('dynamodb')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)

REMINDER_BUTTONS = {
    'hi': [{"id": "done", "title": "हो गया"}, {"id": "not_yet", "title": "अभी नहीं"}],
    'mr': [{"id": "done", "title": "झाला"}, {"id": "not_yet", "title": "नाही झाला"}],
    'te': [{"id": "done", "title": "అయ్యింది"}, {"id": "not_yet", "title": "ఇంకా లేదు"}],
    'en': [{"id": "done", "title": "Done"}, {"id": "not_yet", "title": "Not Yet"}],
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
    
    # Get user profile to determine dialect + district
    try:
        profile_response = table.get_item(
            Key={
                'PK': f'USER#{phone_number}',
                'SK': 'PROFILE'
            }
        )
        profile = profile_response.get('Item') or {}
        dialect = profile.get('dialect', 'hi')
        district_key = profile.get('location') or ''
    except Exception:
        dialect = 'hi'
        district_key = ''
    
    crop = nudge.get('crop', 'Cotton')
    district_key = nudge.get('district') or district_key

    # Only send reminder if not completed/closed
    if status not in ['DONE', 'EXPIRED']:
        message = build_reminder_message(dialect, reminder_type, district_key, crop)
        
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
        if status == 'DONE':
            return {'statusCode': 200, 'message': 'Task already completed'}
        return {'statusCode': 200, 'message': 'Task already closed'}
