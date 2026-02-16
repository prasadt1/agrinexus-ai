"""
Message Processor
Processes messages from SQS, interacts with Bedrock, and sends responses
"""
import json
import os
import boto3
from typing import Dict, Any, Optional
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
bedrock_agent = boto3.client('bedrock-agent-runtime')
secrets = boto3.client('secretsmanager')

TABLE_NAME = os.environ['TABLE_NAME']
KB_ID = os.environ['KNOWLEDGE_BASE_ID']
GUARDRAIL_ID = os.environ['GUARDRAIL_ID']
GUARDRAIL_VERSION = os.environ['GUARDRAIL_VERSION']

table = dynamodb.Table(TABLE_NAME)


def get_user_profile(phone_number: str) -> Optional[Dict[str, Any]]:
    """Retrieve user profile from DynamoDB"""
    response = table.get_item(
        Key={
            'PK': f'USER#{phone_number}',
            'SK': 'PROFILE'
        }
    )
    return response.get('Item')


def save_message(phone_number: str, wamid: str, message_data: Dict[str, Any], response_text: str, source_citation: str):
    """Save message to DynamoDB with TTL"""
    timestamp = datetime.utcnow().isoformat()
    ttl = int(datetime.utcnow().timestamp()) + (90 * 24 * 60 * 60)  # 90 days
    
    table.put_item(
        Item={
            'PK': f'USER#{phone_number}',
            'SK': f'MSG#{timestamp}',
            'wamid': wamid,
            'message': message_data,
            'response': response_text,
            'source_citation': source_citation,
            'ttl': ttl
        }
    )


def query_bedrock(query: str, dialect: str = 'hi') -> Dict[str, Any]:
    """Query Bedrock Knowledge Base with RAG"""
    response = bedrock_agent.retrieve_and_generate(
        input={'text': query},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KB_ID,
                'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
                'generationConfiguration': {
                    'promptTemplate': {
                        'textPromptTemplate': f'''You are an agricultural extension agent helping smallholder farmers in India. 
Respond in {dialect} dialect (hi=Hindi, mr=Marathi, te=Telugu).
Use simple, practical language. Include source citations.

Question: {{input}}

Context: {{context}}

Provide actionable advice with source references.'''
                    },
                    'guardrailConfiguration': {
                        'guardrailId': GUARDRAIL_ID,
                        'guardrailVersion': GUARDRAIL_VERSION
                    }
                }
            }
        }
    )
    
    return {
        'text': response['output']['text'],
        'citations': response.get('citations', [])
    }


def send_whatsapp_message(phone_number: str, message: str):
    """Send message via WhatsApp Business API"""
    # Get WhatsApp credentials
    secret_response = secrets.get_secret_value(SecretId='agrinexus-whatsapp-dev')
    creds = json.loads(secret_response['SecretString'])
    
    # TODO: Implement WhatsApp API call
    # For now, just log
    print(f"Sending to {phone_number}: {message}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process messages from SQS"""
    for record in event['Records']:
        body = json.loads(record['body'])
        
        wamid = body['wamid']
        from_number = body['from']
        message_type = body['type']
        message = body['message']
        
        # Get user profile
        profile = get_user_profile(from_number)
        
        # If no profile, start onboarding
        if not profile:
            # TODO: Implement onboarding flow
            send_whatsapp_message(from_number, "Welcome to AgriNexus AI! Let's get started...")
            continue
        
        dialect = profile.get('dialect', 'hi')
        
        # Process based on message type
        if message_type == 'text':
            text = message.get('text', {}).get('body', '')
            
            # Query Bedrock
            result = query_bedrock(text, dialect)
            
            # Save to DynamoDB
            save_message(from_number, wamid, message, result['text'], str(result['citations']))
            
            # Send response
            send_whatsapp_message(from_number, result['text'])
        
        elif message_type == 'image':
            # TODO: Implement Claude Vision processing
            send_whatsapp_message(from_number, "Image processing coming soon!")
        
        elif message_type == 'audio':
            # TODO: Implement Transcribe processing
            send_whatsapp_message(from_number, "Voice processing coming soon!")
    
    return {'statusCode': 200}
