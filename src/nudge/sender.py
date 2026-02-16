"""
Nudge Sender
Sends behavioral nudges and schedules reminders
"""
import json
import os
import boto3
from datetime import datetime, timedelta
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


def create_reminder_schedule(phone_number: str, nudge_id: str, hours_offset: int, dialect: str):
    """Create EventBridge Scheduler for reminder"""
    schedule_time = datetime.utcnow() + timedelta(hours=hours_offset)
    
    scheduler.create_schedule(
        Name=f'reminder-{nudge_id}-{hours_offset}h',
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


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send nudge and schedule reminders"""
    location = event.get('location')
    weather = event.get('weather', {})
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
    
    for farmer in farmers:
        phone_number = farmer.get('phone_number')
        dialect = farmer.get('dialect', 'hi')
        wind_speed = weather.get('wind_speed', 0)
        
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
        # TODO: Implement WhatsApp API call
        print(f"Sending nudge to {phone_number}: {message}")
        
        # Schedule reminders at T+24h and T+48h
        create_reminder_schedule(phone_number, nudge_id, 24, dialect)
        create_reminder_schedule(phone_number, nudge_id, 48, dialect)
        
        nudges_sent += 1
    
    return {
        'statusCode': 200,
        'nudges_sent': nudges_sent,
        'location': location
    }
