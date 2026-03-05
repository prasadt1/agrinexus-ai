"""
WhatsApp Business API Utilities
Consolidated send_whatsapp_message with Secrets Manager caching
"""
import json
import os
import time
import boto3
import requests
from typing import Optional, Tuple
from datetime import datetime, timedelta

secrets = boto3.client('secretsmanager')

# Cache for Secrets Manager credentials (5-minute TTL)
_credentials_cache = {
    'access_token': None,
    'phone_number_id': None,
    'expires_at': None
}

CACHE_TTL_SECONDS = 300  # 5 minutes


def get_whatsapp_credentials() -> Tuple[str, str]:
    """
    Get WhatsApp credentials from Secrets Manager with caching
    
    Returns:
        (access_token, phone_number_id)
    """
    now = datetime.utcnow()
    
    # Check if cache is valid
    if (_credentials_cache['expires_at'] and 
        now < _credentials_cache['expires_at'] and
        _credentials_cache['access_token'] and
        _credentials_cache['phone_number_id']):
        return _credentials_cache['access_token'], _credentials_cache['phone_number_id']
    
    # Cache miss - fetch from Secrets Manager
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    phone_id_secret = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')
    
    access_token_response = secrets.get_secret_value(SecretId=access_token_secret)
    access_token = access_token_response['SecretString']
    
    phone_id_response = secrets.get_secret_value(SecretId=phone_id_secret)
    phone_number_id = phone_id_response['SecretString']
    
    # Update cache
    _credentials_cache['access_token'] = access_token
    _credentials_cache['phone_number_id'] = phone_number_id
    _credentials_cache['expires_at'] = now + timedelta(seconds=CACHE_TTL_SECONDS)
    
    print(f"Cached WhatsApp credentials (expires in {CACHE_TTL_SECONDS}s)")
    
    return access_token, phone_number_id


def send_whatsapp_message(phone_number: str, message: str, audio_url: Optional[str] = None) -> bool:
    """
    Send message via WhatsApp Business API
    Supports both text and audio messages
    
    Args:
        phone_number: Recipient phone number
        message: Text message to send
        audio_url: Optional audio URL for voice message
    
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        access_token, phone_number_id = get_whatsapp_credentials()
        
        # Send via WhatsApp Business API
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # If audio URL provided, send audio message
        if audio_url:
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "audio",
                "audio": {
                    "link": audio_url
                }
            }
            print(f"Sending voice message to {phone_number[:6]}***: {audio_url}")
        else:
            # Send text message
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {
                    "body": message
                }
            }
            print(f"Sending text to {phone_number[:6]}***: {message[:50]}...")
        
        # Retry logic with exponential backoff
        response = None
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=5)
                if response.status_code < 500 and response.status_code != 429:
                    break
            except requests.RequestException as e:
                print(f"WhatsApp request error (attempt {attempt + 1}): {e}")
            time.sleep(0.5 * (2 ** attempt))
        
        if response and response.status_code == 200:
            print(f"Message sent successfully: {response.json()}")
            return True
        else:
            status = response.status_code if response else 'no_response'
            text = response.text if response else 'no_response_body'
            print(f"Failed to send message: {status} - {text}")
            return False
    
    except Exception as e:
        print(f"Exception sending WhatsApp message: {e}")
        return False


def send_whatsapp_template(phone_number: str, template_name: str, language_code: str) -> bool:
    """
    Send WhatsApp template message
    
    Args:
        phone_number: Recipient phone number
        template_name: Template name registered in WhatsApp Business
        language_code: Language code (hi, mr, te, en)
    
    Returns:
        True if template sent successfully, False otherwise
    """
    try:
        access_token, phone_number_id = get_whatsapp_credentials()
        
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }
        
        print(f"Sending template '{template_name}' ({language_code}) to {phone_number[:6]}***...")
        response = None
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=5)
                if response.status_code < 500 and response.status_code != 429:
                    break
            except requests.RequestException as e:
                print(f"WhatsApp template request error (attempt {attempt + 1}): {e}")
            time.sleep(0.5 * (2 ** attempt))
        
        if response and response.status_code == 200:
            print(f"Template sent successfully: {response.json()}")
            return True
        
        status = response.status_code if response else 'no_response'
        text = response.text if response else 'no_response_body'
        print(f"Failed to send template: {status} - {text}")
        return False
    
    except Exception as e:
        print(f"Exception sending WhatsApp template: {e}")
        return False


def send_whatsapp_list(phone_number: str, body_text: str, button_text: str, sections: list) -> bool:
    """
    Send WhatsApp list message (supports up to 10 options per section)
    
    Args:
        phone_number: Recipient phone number
        body_text: Main message body
        button_text: Text for the list button (e.g., "Select Language")
        sections: List of sections, each with title and rows
                  Example: [{"title": "Languages", "rows": [{"id": "en", "title": "English"}, ...]}]
    
    Returns:
        True if list sent successfully, False otherwise
    """
    try:
        access_token, phone_number_id = get_whatsapp_credentials()
        
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {
                    "text": body_text
                },
                "action": {
                    "button": button_text,
                    "sections": sections
                }
            }
        }
        
        print(f"Sending list message to {phone_number[:6]}***: {body_text[:50]}...")
        response = None
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=5)
                if response.status_code < 500 and response.status_code != 429:
                    break
            except requests.RequestException as e:
                print(f"WhatsApp list request error (attempt {attempt + 1}): {e}")
            time.sleep(0.5 * (2 ** attempt))
        
        if response and response.status_code == 200:
            print(f"List message sent successfully: {response.json()}")
            return True
        
        status = response.status_code if response else 'no_response'
        text = response.text if response else 'no_response_body'
        print(f"Failed to send list message: {status} - {text}")
        return False
    
    except Exception as e:
        print(f"Exception sending WhatsApp list: {e}")
        return False
