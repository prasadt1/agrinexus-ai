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


def send_whatsapp_message(phone_number: str, message: str):
    """Send message via WhatsApp Business API"""
    import requests
    
    # Get WhatsApp credentials
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    phone_id_secret = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')
    
    try:
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
            "text": {"body": message}
        }
        
        print(f"Sending reminder to {phone_number}: {message[:50]}...")
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            print(f"Reminder sent successfully: {response.json()}")
        else:
            print(f"Failed to send reminder: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception sending reminder to {phone_number}: {str(e)}")
