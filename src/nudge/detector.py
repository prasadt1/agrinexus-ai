"""
Response Detector
Detects DONE/NOT YET keywords in messages via DynamoDB Streams
"""
import json
import os
import boto3
from typing import Dict, Any, List
import re
from common.whatsapp import send_whatsapp_message

dynamodb = boto3.resource('dynamodb')
scheduler = boto3.client('scheduler')
cloudwatch = boto3.client('cloudwatch')

TABLE_NAME = os.environ['TABLE_NAME']
table = dynamodb.Table(TABLE_NAME)

# DONE keywords by dialect
DONE_KEYWORDS = {
    'hi': ['हो गया', 'कर दिया', 'हो गया है', 'कर लिया', 'done', 'completed'],
    'mr': ['झाला', 'केला', 'पूर्ण झाला', 'done'],
    'te': ['అయ్యింది', 'చేశాను', 'పూర్తయింది', 'done'],
    'en': ['done', 'completed', 'finished']
}

NOT_YET_KEYWORDS = {
    'hi': ['अभी नहीं', 'बाद में', 'नहीं किया', 'not yet', 'later'],
    'mr': ['नाही झाला', 'नंतर', 'अजून नाही', 'not yet'],
    'te': ['ఇంకా లేదు', 'తర్వాత', 'చేయలేదు', 'not yet'],
    'en': ['not yet', 'later', 'not done', 'not now']
}

# Confirmation messages by dialect
CONFIRMATION_MESSAGES = {
    'hi': 'बहुत अच्छा! आपका काम पूरा हो गया। धन्यवाद! 🎉',
    'mr': 'खूप छान! तुमचे काम पूर्ण झाले. धन्यवाद! 🎉',
    'te': 'చాలా బాగుంది! మీ పని పూర్తయింది. ధన్యవాదాలు! 🎉',
    'en': 'Great! Your task is complete. Thank you! 🎉'
}

# NOT YET acknowledgment messages by dialect
NOT_YET_MESSAGES = {
    'hi': 'कोई बात नहीं। मैं आपको बाद में याद दिलाऊंगा। 👍',
    'mr': 'काही हरकत नाही. मी तुम्हाला नंतर आठवण करून देईन. 👍',
    'te': 'పర్వాలేదు. నేను మీకు తర్వాత గుర్తు చేస్తాను. 👍',
    'en': 'No problem. I will remind you later. 👍'
}

# NOT YET final acknowledgment (after T+48h reminder)
NOT_YET_FINAL_MESSAGES = {
    'hi': 'कोई बात नहीं। जब आप तैयार हों तो कर लें। अगली बार मौसम अच्छा होगा तो मैं फिर से याद दिलाऊंगा। 👍',
    'mr': 'काही हरकत नाही. तुम्ही तयार असाल तेव्हा करा. पुढच्या वेळी हवामान चांगले असेल तर मी पुन्हा आठवण करून देईन. 👍',
    'te': 'పర్వాలేదు. మీరు సిద్ధంగా ఉన్నప్పుడు చేయండి. తదుపరిసారి వాతావరణం మంచిగా ఉంటే నేను మళ్లీ గుర్తు చేస్తాను. 👍',
    'en': 'No problem. Do it when you are ready. I will remind you again when the weather is good next time. 👍'
}


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


def detect_keyword(text: str, keywords: List[str]) -> bool:
    """Check if text contains any of the keywords"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def get_active_nudges(phone_number: str) -> List[Dict[str, Any]]:
    """Get active nudges for user, newest first (by NUDGE# sort key).

    Default DynamoDB sort order is ascending, so the first item was the *oldest*
    nudge — wrong for lastReminder (T+48h) checks when multiple rows exist.
    """
    response = table.query(
        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
        ExpressionAttributeValues={
            ':pk': f'USER#{phone_number}',
            ':sk': 'NUDGE#'
        },
        ScanIndexForward=False,
    )

    # Filter for SENT or REMINDED status (but not EXPIRED); order = newest first
    return [
        item for item in response.get('Items', [])
        if item.get('status') in ['SENT', 'REMINDED']
    ]


def get_user_dialect(phone_number: str) -> str:
    """Get user's dialect from profile"""
    try:
        response = table.get_item(
            Key={
                'PK': f'USER#{phone_number}',
                'SK': 'PROFILE'
            }
        )
        return response.get('Item', {}).get('dialect', 'hi')
    except:
        return 'hi'  # Default to Hindi


def delete_scheduled_reminders(nudge_id: str):
    """Delete EventBridge Scheduler reminders and expiry"""
    # Apply same transformation as sender: replace : and # with -
    safe_nudge_id = nudge_id.replace(':', '-').replace('#', '-')
    
    try:
        schedule_name = f'reminder-{safe_nudge_id}-24h'
        scheduler.delete_schedule(Name=schedule_name)
        print(f"Deleted schedule: {schedule_name}")
    except Exception as e:
        print(f"Failed to delete 24h schedule: {e}")
    
    try:
        schedule_name = f'reminder-{safe_nudge_id}-48h'
        scheduler.delete_schedule(Name=schedule_name)
        print(f"Deleted schedule: {schedule_name}")
    except Exception as e:
        print(f"Failed to delete 48h schedule: {e}")
    
    try:
        schedule_name = f'expiry-{safe_nudge_id}'
        scheduler.delete_schedule(Name=schedule_name)
        print(f"Deleted expiry schedule: {schedule_name}")
    except Exception as e:
        print(f"Failed to delete expiry schedule: {e}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process DynamoDB Stream events"""
    print(f"Received {len(event['Records'])} records")
    
    for record in event['Records']:
        print(f"Processing record: eventName={record['eventName']}")
        
        if record['eventName'] != 'INSERT':
            print(f"Skipping non-INSERT event: {record['eventName']}")
            continue
        
        new_image = record['dynamodb']['NewImage']
        
        # Only process message records
        sk = new_image.get('SK', {}).get('S', '')
        print(f"Record SK: {sk}")
        
        if not sk.startswith('MSG#'):
            print(f"Skipping non-message record: {sk}")
            continue
        
        pk = new_image.get('PK', {}).get('S', '')
        phone_number = pk.replace('USER#', '')
        print(f"Processing message for user: {phone_number}")
        
        # Extract message text from DynamoDB Stream format
        # The 'message' field is a Map (M) in DynamoDB Streams, not a String (S)
        message_map = new_image.get('message', {}).get('M', {})
        
        # Try text message first
        text_map = message_map.get('text', {}).get('M', {})
        text = text_map.get('body', {}).get('S', '')
        
        # If no text, try interactive button reply (onboarding buttons)
        if not text:
            interactive_map = message_map.get('interactive', {}).get('M', {})
            button_reply_map = interactive_map.get('button_reply', {}).get('M', {})
            text = button_reply_map.get('title', {}).get('S', '')
        
        # If still no text, try template button (nudge response buttons)
        if not text:
            button_map = message_map.get('button', {}).get('M', {})
            text = button_map.get('text', {}).get('S', '')
        
        print(f"Message text: {text}")
        
        if not text:
            print("No text found in message")
            continue
        
        # Check for NOT YET keywords FIRST (more specific than DONE)
        all_not_yet_keywords = []
        for keywords in NOT_YET_KEYWORDS.values():
            all_not_yet_keywords.extend(keywords)
        
        # Check for DONE keywords
        all_done_keywords = []
        for keywords in DONE_KEYWORDS.values():
            all_done_keywords.extend(keywords)
        
        print(f"Checking keywords in: {text}")
        
        # Check NOT YET first (more specific)
        if detect_keyword(text, all_not_yet_keywords):
            print(f"NOT YET keyword detected!")
            
            # Get active nudges to check reminder status
            active_nudges = get_active_nudges(phone_number)
            dialect = get_user_dialect(phone_number)
            
            # Check if this is after the final (T+48h) reminder
            is_final_reminder = False
            if active_nudges:
                # [0] = newest active nudge (ScanIndexForward=False + filter preserves order)
                latest_nudge = active_nudges[0]
                last_reminder = latest_nudge.get('lastReminder')
                print(f"Using nudge SK={latest_nudge.get('SK')} lastReminder={last_reminder}")
                
                # If last reminder was T+48h, this is the final response
                if last_reminder == 'T+48h':
                    is_final_reminder = True
                    
                    # Mark nudge as EXPIRED (no more reminders)
                    nudge_sk = latest_nudge['SK']
                    nudge_id = nudge_sk.replace('NUDGE#', '')
                    table.update_item(
                        Key={
                            'PK': pk,
                            'SK': nudge_sk
                        },
                        UpdateExpression='SET #status = :status',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'EXPIRED'
                        }
                    )
                    print(f"Marked nudge as EXPIRED (farmer declined after T+48h)")

                    # Delete scheduled reminders/expiry (avoid orphaned expiry invocation)
                    delete_scheduled_reminders(nudge_id)
            
            # Send appropriate acknowledgment
            if is_final_reminder:
                acknowledgment = NOT_YET_FINAL_MESSAGES.get(dialect, NOT_YET_FINAL_MESSAGES['hi'])
                print("Sending final NOT YET acknowledgment (no more reminders)")
            else:
                acknowledgment = NOT_YET_MESSAGES.get(dialect, NOT_YET_MESSAGES['hi'])
                print("Sending NOT YET acknowledgment (reminders will continue)")
            
            send_whatsapp_message(phone_number, acknowledgment)
        
        # Only check DONE if NOT YET wasn't detected
        elif detect_keyword(text, all_done_keywords):
            print(f"DONE keyword detected!")
            
            # Get active nudges
            active_nudges = get_active_nudges(phone_number)
            print(f"Found {len(active_nudges)} active nudges")
            
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
                
                # Send confirmation message
                dialect = get_user_dialect(phone_number)
                confirmation = CONFIRMATION_MESSAGES.get(dialect, CONFIRMATION_MESSAGES['hi'])
                send_whatsapp_message(phone_number, confirmation)
                emit_metric('NudgesCompleted', 1)
    
    return {'statusCode': 200}
