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
from bedrock_liner import invoke_nudge_focus_line

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

from common.allowlist import is_approved_user


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
    
    try:
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
        print(f"Created reminder schedule: {schedule_name}")
    except Exception as e:
        # Idempotency: if Lambda retries after partial success, schedule may already exist.
        code = None
        try:
            code = (getattr(e, "response", {}) or {}).get("Error", {}).get("Code")
        except Exception:
            code = None
        if code == "ConflictException" or "ConflictException" in str(e):
            print(f"Reminder schedule already exists (OK): {schedule_name}")
            return
        print(f"Failed to create reminder schedule {schedule_name}: {e}")


def create_expiry_schedule(phone_number: str, nudge_id: str, hours_offset: int):
    """Create EventBridge Scheduler to auto-expire nudge if no response"""
    schedule_time = datetime.utcnow() + timedelta(hours=hours_offset)
    
    # Create valid schedule name
    safe_nudge_id = nudge_id.replace(':', '-').replace('#', '-')
    schedule_name = f'expiry-{safe_nudge_id}'
    
    # Use the same reminder Lambda but with a special 'EXPIRY' type
    try:
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
        print(f"Created expiry schedule: {schedule_name}")
    except Exception as e:
        code = None
        try:
            code = (getattr(e, "response", {}) or {}).get("Error", {}).get("Code")
        except Exception:
            code = None
        if code == "ConflictException" or "ConflictException" in str(e):
            print(f"Expiry schedule already exists (OK): {schedule_name}")
            return
        print(f"Failed to create expiry schedule {schedule_name}: {e}")


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
    # "Today" for nudges is evaluated in IST to avoid a UTC-midnight edge case where
    # a farmer can receive two nudges within minutes (same India morning).
    ist_offset = timedelta(hours=5, minutes=30)
    today_ist = (datetime.utcnow() + ist_offset).date().isoformat()
    
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
        # Convert the nudge timestamp (stored as UTC in SK) into IST-local date.
        # SK format: "{utc_iso_timestamp}#{activity}"
        nudge_date = ''
        try:
            ts = nudge_id.split('#', 1)[0]
            if 'T' in ts:
                nudge_date = (datetime.fromisoformat(ts) + ist_offset).date().isoformat()
        except Exception:
            nudge_date = nudge_id.split('T')[0] if 'T' in nudge_id else ''
        nudge_activity = nudge_id.split('#')[-1] if '#' in nudge_id else ''
        status = item.get('status', 'SENT')  # Default to SENT if not set
        
        # Check if it's today's nudge for this activity and still pending (SENT or REMINDED, not DONE)
        if nudge_date == today_ist and nudge_activity == activity and status in ['SENT', 'REMINDED']:
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

        # Gate nudges to approved users only (public WhatsApp is text-only)
        if not is_approved_user(table, phone_number):
            print(f"Skipping {phone_number} - not allowlisted for nudges")
            nudges_skipped += 1
            continue
        
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
        hint_override = None
        if os.environ.get("NUDGE_BEDROCK_LINER", "").lower() in ("1", "true", "yes"):
            try:
                hint_override = invoke_nudge_focus_line(
                    dialect, crop, str(district_key), wind_speed
                )
            except Exception as e:
                print(f"Nudge Bedrock liner skipped: {e}")
        message = build_nudge_message(
            dialect, district_key, crop, wind_speed, context_hint_override=hint_override
        )

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
        
        # Check if user is demo tier (skip follow-up reminders for demo users)
        is_demo_user = profile.get('demo_tier') == 'public'
        
        if is_demo_user:
            print(f"Demo user {phone_number} - sending one nudge only, no T+24h/T+48h follow-ups")
            # Demo users get one nudge to see the flow, but no follow-up reminders
        else:
            # Production users get full closed-loop follow-ups
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
