"""
Nudge Sender
Sends behavioral nudges and schedules reminders
"""
import json
import os
import sys
import boto3
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any
from common.whatsapp import send_whatsapp_message, send_whatsapp_template, send_whatsapp_buttons

# Lambda uses Handler sender.lambda_handler (flat zip); tests use src.nudge.sender
_nudge_dir = os.path.dirname(os.path.abspath(__file__))
if _nudge_dir not in sys.path:
    sys.path.insert(0, _nudge_dir)
from nudge_copy import build_nudge_message

dynamodb = boto3.resource('dynamodb')
scheduler = boto3.client('scheduler')
cloudwatch = boto3.client('cloudwatch')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)
NUDGE_TEMPLATE_NAME = os.environ.get('NUDGE_TEMPLATE_NAME', '').strip()
USE_NUDGE_TEMPLATE = os.environ.get('USE_NUDGE_TEMPLATE', 'true').lower() == 'true'

# Nudge templates by dialect
NUDGE_BUTTONS = {
    'hi': [{"id": "done", "title": "हो गया"}, {"id": "not_yet", "title": "अभी नहीं"}],
    'mr': [{"id": "done", "title": "झाला"}, {"id": "not_yet", "title": "नाही झाला"}],
    'te': [{"id": "done", "title": "అయ్యింది"}, {"id": "not_yet", "title": "ఇంకా లేదు"}],
    'en': [{"id": "done", "title": "Done"}, {"id": "not_yet", "title": "Not Yet"}],
}


def convert_floats_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj


def create_reminder_schedule(phone_number: str, nudge_id: str, hours_offset: int, dialect: str):
    """Create EventBridge Scheduler for reminder"""
    schedule_time = datetime.utcnow() + timedelta(hours=hours_offset)
    
    # Create valid schedule name (alphanumeric, hyphens, underscores only)
    safe_nudge_id = nudge_id.replace(':', '-').replace('#', '-')
    schedule_name = f'reminder-{safe_nudge_id}-{hours_offset}h'
    
    scheduler.create_schedule(
        Name=schedule_name,
        ScheduleExpression=f'at({schedule_time.strftime("%Y-%m-%dT%H:%M:%S")})',
        Target={
            'Arn': os.environ['REMINDER_LAMBDA_ARN'],
            'RoleArn': os.environ['SCHEDULER_ROLE_ARN'],
            'Input': json.dumps({
                'phone_number': phone_number,
                'nudge_id': nudge_id,
                'reminder_type': f'T+{hours_offset}h',
                'dialect': dialect
            })
        },
        FlexibleTimeWindow={'Mode': 'OFF'}
    )


def create_expiry_schedule(phone_number: str, nudge_id: str, hours_offset: int):
    """Create EventBridge Scheduler to auto-expire nudge if no response"""
    schedule_time = datetime.utcnow() + timedelta(hours=hours_offset)
    
    # Create valid schedule name
    safe_nudge_id = nudge_id.replace(':', '-').replace('#', '-')
    schedule_name = f'expiry-{safe_nudge_id}'
    
    # Use the same reminder Lambda but with a special 'EXPIRY' type
    scheduler.create_schedule(
        Name=schedule_name,
        ScheduleExpression=f'at({schedule_time.strftime("%Y-%m-%dT%H:%M:%S")})',
        Target={
            'Arn': os.environ['REMINDER_LAMBDA_ARN'],
            'RoleArn': os.environ['SCHEDULER_ROLE_ARN'],
            'Input': json.dumps({
                'phone_number': phone_number,
                'nudge_id': nudge_id,
                'reminder_type': 'EXPIRY',
                'activity': 'auto-expire'
            })
        },
        FlexibleTimeWindow={'Mode': 'OFF'}
    )


def emit_metric(name: str, value: float = 1.0):
    """Emit custom CloudWatch metric for nudges"""
    try:
        cloudwatch.put_metric_data(
            Namespace='AgriNexus',
            MetricData=[
                {
                    'MetricName': name,
                    'Value': value,
                    'Unit': 'Count'
                }
            ]
        )
    except Exception as e:
        print(f"Failed to emit metric {name}: {e}")


def has_pending_nudge(phone_number: str, activity: str) -> bool:
    """Check if user has a pending nudge for this activity today"""
    today = datetime.utcnow().date().isoformat()
    
    # Query nudges for this user
    response = table.query(
        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
        ExpressionAttributeValues={
            ':pk': f'USER#{phone_number}',
            ':sk': 'NUDGE#'
        }
    )
    
    # Check if any nudge is pending and from today
    for item in response.get('Items', []):
        nudge_id = item.get('SK', '').replace('NUDGE#', '')
        nudge_date = nudge_id.split('T')[0] if 'T' in nudge_id else ''
        nudge_activity = nudge_id.split('#')[-1] if '#' in nudge_id else ''
        status = item.get('status', 'SENT')  # Default to SENT if not set
        
        # Check if it's today's nudge for this activity and still pending (SENT or REMINDED, not DONE)
        if nudge_date == today and nudge_activity == activity and status in ['SENT', 'REMINDED']:
            print(f"Found existing pending {activity} nudge for {phone_number}: {nudge_id} (status: {status})")
            return True
    
    return False


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send nudge and schedule reminders"""
    location = event.get('location')
    weather = convert_floats_to_decimal(event.get('weather', {}))
    activity = event.get('activity', 'spray')
    
    # Query farmers in this location
    response = table.query(
        IndexName='GSI1',
        KeyConditionExpression='GSI1PK = :location',
        ExpressionAttributeValues={
            ':location': f'LOCATION#{location}'
        }
    )
    
    farmers = response.get('Items', [])
    print(f"Found {len(farmers)} farmers in {location}")
    
    nudges_sent = 0
    nudges_skipped = 0
    
    for farmer in farmers:
        phone_number = farmer.get('phone_number')
        dialect = farmer.get('dialect', 'hi')
        wind_speed = float(weather.get('wind_speed', 0))
        
        # Check if user already has a pending nudge for this activity today
        if has_pending_nudge(phone_number, activity):
            print(f"Skipping {phone_number} - already has pending {activity} nudge today")
            nudges_skipped += 1
            continue
        
        # Fetch crop + district from farmer profile
        profile = table.get_item(Key={'PK': f'USER#{phone_number}', 'SK': 'PROFILE'}).get('Item') or {}
        crop = profile.get('crop', 'Cotton')
        district_key = profile.get('location') or location

        # Context-aware message (district, crop, spray type, wind, extension-style hint)
        message = build_nudge_message(dialect, district_key, crop, wind_speed)

        # Create nudge record in DynamoDB
        timestamp = datetime.utcnow().isoformat()
        nudge_id = f"{timestamp}#{activity}"
        ttl = int(datetime.utcnow().timestamp()) + (180 * 24 * 60 * 60)  # 180 days

        table.put_item(
            Item={
                'PK': f'USER#{phone_number}',
                'SK': f'NUDGE#{nudge_id}',
                'GSI2PK': 'NUDGE',
                'GSI2SK': timestamp,
                'status': 'SENT',
                'activity': activity,
                'crop': crop,
                'district': district_key,
                'weather': weather,
                'message': message,
                'ttl': ttl
            }
        )
        
        # Personalized interactive message first (shows crop/district/hints).
        # WhatsApp template is generic — use only as fallback if buttons fail.
        sent = False
        buttons = NUDGE_BUTTONS.get(dialect, NUDGE_BUTTONS['hi'])
        sent = send_whatsapp_buttons(phone_number, message, buttons)
        if not sent and USE_NUDGE_TEMPLATE and NUDGE_TEMPLATE_NAME:
            language_code = {
                'hi': 'hi',
                'mr': 'mr',
                'te': 'te',
                'en': 'en'
            }.get(dialect, 'hi')
            sent = send_whatsapp_template(phone_number, NUDGE_TEMPLATE_NAME, language_code)
        if not sent:
            send_whatsapp_message(phone_number, message)

        emit_metric('NudgesSent', 1)
        
        # Schedule reminders at T+24h and T+48h
        create_reminder_schedule(phone_number, nudge_id, 24, dialect)
        create_reminder_schedule(phone_number, nudge_id, 48, dialect)
        
        # Schedule auto-expiry at T+72h (24h after final reminder)
        # This closes the nudge if farmer never responds
        create_expiry_schedule(phone_number, nudge_id, 72)
        
        nudges_sent += 1
    
    return {
        'statusCode': 200,
        'nudges_sent': nudges_sent,
        'nudges_skipped': nudges_skipped,
        'location': location
    }
