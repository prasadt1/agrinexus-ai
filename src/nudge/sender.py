"""
Nudge Sender
Sends behavioral nudges and schedules reminders
"""
import json
import os
import boto3
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb')
scheduler = boto3.client('scheduler')
secrets = boto3.client('secretsmanager')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)

# Nudge templates by dialect
NUDGE_TEMPLATES = {
    'hi': {
        'spray': 'आज स्प्रे करने के लिए अच्छा मौसम है। हवा {wind_speed} km/h है और बारिश नहीं होगी। क्या आपने स्प्रे कर दिया?',
        'done_prompt': 'कृपया "हो गया" भेजें जब आप स्प्रे कर लें।'
    },
    'mr': {
        'spray': 'आज फवारणीसाठी चांगले हवामान आहे। वारा {wind_speed} km/h आहे आणि पाऊस नाही। तुम्ही फवारणी केली का?',
        'done_prompt': 'कृपया "झाला" पाठवा जेव्हा तुम्ही फवारणी पूर्ण करता.'
    },
    'te': {
        'spray': 'ఈరోజు స్ప్రే చేయడానికి మంచి వాతావరణం. గాలి {wind_speed} km/h మరియు వర్షం ఉండదు। మీరు స్ప్రే చేశారా?',
        'done_prompt': 'దయచేసి "అయ్యింది" పంపండి మీరు స్ప్రే పూర్తి చేసినప్పుడు.'
    }
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


def send_whatsapp_message(phone_number: str, message: str):
    """Send message via WhatsApp Business API"""
    import requests
    import time
    
    # Get WhatsApp credentials
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    phone_id_secret = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')
    
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
    
    print(f"Sending nudge to {phone_number}: {message[:50]}...")
    response = None
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            if response.status_code < 500 and response.status_code != 429:
                break
        except requests.RequestException as e:
            print(f"WhatsApp nudge request error (attempt {attempt + 1}): {e}")
        time.sleep(0.5 * (2 ** attempt))
    
    if response and response.status_code == 200:
        print(f"Nudge sent successfully: {response.json()}")
    else:
        status = response.status_code if response else 'no_response'
        text = response.text if response else 'no_response_body'
        print(f"Failed to send nudge: {status} - {text}")


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
        
        # Generate nudge message
        template = NUDGE_TEMPLATES.get(dialect, NUDGE_TEMPLATES['hi'])
        message = template['spray'].format(wind_speed=wind_speed)
        message += '\n\n' + template['done_prompt']
        
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
                'weather': weather,
                'message': message,
                'ttl': ttl
            }
        )
        
        # Send WhatsApp message
        send_whatsapp_message(phone_number, message)
        
        # Schedule reminders at T+24h and T+48h
        create_reminder_schedule(phone_number, nudge_id, 24, dialect)
        create_reminder_schedule(phone_number, nudge_id, 48, dialect)
        
        nudges_sent += 1
    
    return {
        'statusCode': 200,
        'nudges_sent': nudges_sent,
        'nudges_skipped': nudges_skipped,
        'location': location
    }
