# Next Actions for Week 2 Completion

## ✅ What's Already Done

Your Week 2 stack is fully deployed and functional:
- All 7 Lambda functions are running
- API Gateway webhook endpoint is live and responding
- DynamoDB Stream is connected to response detector
- Weather poller is scheduled (every 6 hours)
- EventBridge Scheduler role is configured
- FIFO queues are working with proper deduplication
- Onboarding state machine is implemented

## 🔧 What You Need to Do

### 1. Configure WhatsApp Webhook in Meta Dashboard (5 minutes)

**Steps:**
1. Go to https://developers.facebook.com/
2. Select your WhatsApp Business app
3. Go to WhatsApp > Configuration
4. Click "Edit" on Webhook
5. Enter:
   - **Callback URL**: `https://nwo9tkvpoi.execute-api.us-east-1.amazonaws.com/dev/webhook`
   - **Verify Token**: `agrinexus-webhook-verify-2026`
6. Click "Verify and Save"
7. Subscribe to webhook field: `messages`

**Test:** The webhook will verify successfully (already tested with curl).

### 2. Implement WhatsApp API Calls (30 minutes)

Currently, the code just logs messages instead of sending them. You need to implement actual WhatsApp API calls in 3 files:

**File 1: `src/processor/handler.py`**
```python
def send_whatsapp_message(phone_number: str, message: str):
    """Send message via WhatsApp Business API"""
    import requests
    
    # Get credentials
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    phone_id_secret = os.environ.get('PHONE_NUMBER_ID_SECRET', 'agrinexus/whatsapp/phone-number-id')
    
    access_token = secrets.get_secret_value(SecretId=access_token_secret)['SecretString']
    phone_number_id = secrets.get_secret_value(SecretId=phone_id_secret)['SecretString']
    
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
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
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
```

**File 2: `src/nudge/sender.py`**
Add the same `send_whatsapp_message()` function and replace the print statement:
```python
# Replace this:
print(f"Sending nudge to {phone_number}: {message}")

# With this:
send_whatsapp_message(phone_number, message)
```

**File 3: `src/nudge/reminder.py`**
Add the same function and replace the print statement:
```python
# Replace this:
print(f"Sending {reminder_type} reminder to {phone_number}: {message}")

# With this:
send_whatsapp_message(phone_number, message)
```

**Deploy:**
```bash
./scripts/deploy-week2.sh
```

### 3. Test End-to-End Flow (15 minutes)

**Test Onboarding:**
1. Send "Namaste" from your WhatsApp to the business number
2. You should receive: "नमस्ते! AgriNexus AI में आपका स्वागत है..."
3. Reply "Hindi"
4. Reply "Aurangabad"
5. Reply "Cotton"
6. Reply "हाँ" (Yes)
7. You should receive: "बधाई हो! आपका प्रोफाइल तैयार है..."

**Test Nudge Engine:**
1. Manually trigger weather poller:
```bash
aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/weather-response.json
cat /tmp/weather-response.json
```

2. Check if nudge was sent (check CloudWatch Logs or DynamoDB)

3. Reply "हो गया" (Done) from WhatsApp

4. Verify status updated in DynamoDB:
```bash
aws dynamodb query --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"USER#+91XXXXXXXXXX"},":sk":{"S":"NUDGE#"}}'
```

### 4. Optional: Create Bedrock Guardrails (30 minutes)

**Steps:**
1. Go to AWS Bedrock Console
2. Navigate to Guardrails
3. Click "Create guardrail"
4. Add content filters for banned pesticides:
   - Endosulfan
   - Paraquat
   - Monocrotophos
5. Note the Guardrail ID
6. Update stack:
```bash
sam deploy --config-file samconfig-week2.toml \
  --parameter-overrides GuardrailId=<your-guardrail-id>
```

## 🎯 Priority Order

1. **Configure Meta Webhook** (required for any testing)
2. **Implement WhatsApp API calls** (required for messages to actually send)
3. **Test onboarding flow** (verify everything works)
4. **Test nudge engine** (verify behavioral nudges work)
5. **Create Guardrails** (optional safety layer)

## 📊 How to Monitor

**CloudWatch Logs:**
```bash
# Webhook logs
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow

# Processor logs
aws logs tail /aws/lambda/agrinexus-processor-dev --follow

# Nudge sender logs
aws logs tail /aws/lambda/agrinexus-nudge-sender-dev --follow
```

**DynamoDB:**
```bash
# Check user profiles
aws dynamodb scan --table-name agrinexus-data \
  --filter-expression "begins_with(PK, :pk)" \
  --expression-attribute-values '{":pk":{"S":"USER#"}}'

# Check nudges
aws dynamodb scan --table-name agrinexus-data \
  --filter-expression "begins_with(SK, :sk)" \
  --expression-attribute-values '{":sk":{"S":"NUDGE#"}}'
```

## 🚨 Known Issues

1. **Signature Verification Disabled**: The webhook currently skips X-Hub-Signature-256 validation. For production, implement proper HMAC validation.

2. **No Message Templates**: Currently sending plain text. For production, you need approved WhatsApp message templates for proactive messages (nudges).

3. **Mock Weather**: Aurangabad weather is hardcoded. For production, integrate real weather API.

## 📞 Support

If you encounter issues:
1. Check CloudWatch Logs for errors
2. Verify secrets exist in Secrets Manager
3. Check DynamoDB for data
4. Test webhook with curl (already verified working)
