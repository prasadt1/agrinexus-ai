"""
Response Detector
Detects DONE/NOT YET keywords in messages via DynamoDB Streams
"""
import json
import os
import boto3
from typing import Dict, Any, List
import re

dynamodb = boto3.resource('dynamodb')
scheduler = boto3.client('scheduler')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)

# DONE keywords by dialect
DONE_KEYWORDS = {
    'hi': ['हो गया', 'कर दिया', 'हो गया है', 'कर लिया', 'done', 'completed'],
    'mr': ['झाला', 'केला', 'पूर्ण झाला', 'done'],
    'te': ['అయ్యింది', 'చేశాను', 'పూర్తయింది', 'done']
}

NOT_YET_KEYWORDS = {
    'hi': ['अभी नहीं', 'बाद में', 'नहीं किया', 'not yet', 'later'],
    'mr': ['नाही झाला', 'नंतर', 'अजून नाही', 'not yet'],
    'te': ['ఇంకా లేదు', 'తర్వాత', 'చేయలేదు', 'not yet']
}


def detect_keyword(text: str, keywords: List[str]) -> bool:
    """Check if text contains any of the keywords"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def get_active_nudges(phone_number: str) -> List[Dict[str, Any]]:
    """Get active nudges for user"""
    response = table.query(
        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
        ExpressionAttributeValues={
            ':pk': f'USER#{phone_number}',
            ':sk': 'NUDGE#'
        }
    )
    
    # Filter for SENT or REMINDED status
    return [
        item for item in response.get('Items', [])
        if item.get('status') in ['SENT', 'REMINDED']
    ]


def delete_scheduled_reminders(nudge_id: str):
    """Delete EventBridge Scheduler reminders"""
    try:
        scheduler.delete_schedule(Name=f'reminder-{nudge_id}-24h')
    except:
        pass
    
    try:
        scheduler.delete_schedule(Name=f'reminder-{nudge_id}-48h')
    except:
        pass


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process DynamoDB Stream events"""
    for record in event['Records']:
        if record['eventName'] != 'INSERT':
            continue
        
        new_image = record['dynamodb']['NewImage']
        
        # Only process message records
        sk = new_image.get('SK', {}).get('S', '')
        if not sk.startswith('MSG#'):
            continue
        
        pk = new_image.get('PK', {}).get('S', '')
        phone_number = pk.replace('USER#', '')
        
        # Extract message text
        message_data = json.loads(new_image.get('message', {}).get('S', '{}'))
        text = message_data.get('text', {}).get('body', '')
        
        if not text:
            continue
        
        # Check for DONE keywords
        all_done_keywords = []
        for keywords in DONE_KEYWORDS.values():
            all_done_keywords.extend(keywords)
        
        if detect_keyword(text, all_done_keywords):
            # Get active nudges
            active_nudges = get_active_nudges(phone_number)
            
            # Mark most recent nudge as DONE
            if active_nudges:
                latest_nudge = active_nudges[0]
                nudge_sk = latest_nudge['SK']
                nudge_id = nudge_sk.replace('NUDGE#', '')
                
                # Update status to DONE
                table.update_item(
                    Key={
                        'PK': pk,
                        'SK': nudge_sk
                    },
                    UpdateExpression='SET #status = :status, completedAt = :completed',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': 'DONE',
                        ':completed': new_image.get('SK', {}).get('S', '').replace('MSG#', '')
                    }
                )
                
                # Delete scheduled reminders
                delete_scheduled_reminders(nudge_id)
                
                print(f"Marked nudge {nudge_id} as DONE for {phone_number}")
        
        # Check for NOT YET keywords
        all_not_yet_keywords = []
        for keywords in NOT_YET_KEYWORDS.values():
            all_not_yet_keywords.extend(keywords)
        
        if detect_keyword(text, all_not_yet_keywords):
            # Just log, reminders will continue
            print(f"User {phone_number} responded NOT YET")
    
    return {'statusCode': 200}
