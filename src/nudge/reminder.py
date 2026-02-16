"""
Reminder Sender
Sends T+24h and T+48h reminders if task not completed
"""
import json
import os
import boto3
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb')
secrets = boto3.client('secretsmanager')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)

REMINDER_TEMPLATES = {
    'hi': {
        'T+24h': 'याद दिलाना: कल हमने स्प्रे करने के लिए कहा था। क्या आपने कर लिया? "हो गया" या "अभी नहीं" भेजें।',
        'T+48h': 'अंतिम याद दिलाना: स्प्रे करना बाकी है। कृपया जल्द करें और "हो गया" भेजें।'
    },
    'mr': {
        'T+24h': 'आठवण: काल आम्ही फवारणी करण्यास सांगितले होते। तुम्ही केले का? "झाला" किंवा "नाही झाला" पाठवा.',
        'T+48h': 'शेवटची आठवण: फवारणी बाकी आहे. कृपया लवकर करा आणि "झाला" पाठवा.'
    },
    'te': {
        'T+24h': 'గుర్తు: నిన్న మేము స్ప్రే చేయమని చెప్పాము. మీరు చేశారా? "అయ్యింది" లేదా "ఇంకా లేదు" పంపండి.',
        'T+48h': 'చివరి గుర్తు: స్ప్రే చేయడం మిగిలి ఉంది. దయచేసి త్వరగా చేయండి మరియు "అయ్యింది" పంపండి.'
    }
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send reminder if task not completed"""
    phone_number = event['phone_number']
    nudge_id = event['nudge_id']
    reminder_type = event['reminder_type']
    dialect = event.get('dialect', 'hi')
    
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
    
    # Only send reminder if not completed
    if status != 'DONE':
        template = REMINDER_TEMPLATES.get(dialect, REMINDER_TEMPLATES['hi'])
        message = template.get(reminder_type, template['T+24h'])
        
        # Send WhatsApp message
        # TODO: Implement WhatsApp API call
        print(f"Sending {reminder_type} reminder to {phone_number}: {message}")
        
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
