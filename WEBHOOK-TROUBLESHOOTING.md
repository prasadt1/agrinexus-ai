# WhatsApp Webhook Troubleshooting

## Current Status
✅ Webhook endpoint is live and responding
✅ Webhook verification works
✅ Test messages via curl work
❌ Real WhatsApp messages not reaching the webhook

## Webhook URL
```
https://nwo9tkvpoi.execute-api.us-east-1.amazonaws.com/dev/webhook
```

## Verify Token
```
agrinexus-webhook-verify-2026
```

## Steps to Fix

### 1. Check Meta Dashboard Configuration

Go to: https://developers.facebook.com/apps

1. Select your WhatsApp Business app
2. Go to **WhatsApp > Configuration** (left sidebar)
3. Under **Webhook**, verify:
   - ✅ Callback URL: `https://nwo9tkvpoi.execute-api.us-east-1.amazonaws.com/dev/webhook`
   - ✅ Verify Token: `agrinexus-webhook-verify-2026`
   - ✅ Status shows "Verified" (green checkmark)

### 2. Check Webhook Subscriptions

In the same Configuration page:

1. Under **Webhook fields**, ensure `messages` is **subscribed** (toggle should be ON)
2. You should see a green checkmark next to `messages`

### 3. Check Phone Number Configuration

1. Go to **WhatsApp > API Setup** (left sidebar)
2. Verify:
   - Your test phone number is listed
   - Phone Number ID matches: `980018638530494`
   - The number shows as "Active"

### 4. Test Message Flow

Send a test message from your phone to the WhatsApp Business number:

```
Namaste
```

Then check CloudWatch logs:
```bash
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow
```

You should see:
```
[INFO] Event received: {...}
[INFO] HTTP method: POST
[INFO] Processing 1 message(s)
[INFO] Message - wamid: wamid.xxx, from: 91XXXXXXXXXX, type: text
```

### 5. Common Issues

**Issue: Webhook shows "Not Verified"**
- Solution: Click "Edit" and re-verify with the correct token

**Issue: Messages field not subscribed**
- Solution: Toggle the `messages` field to ON

**Issue: Phone number not connected**
- Solution: Go to API Setup and add your test phone number

**Issue: Using wrong WhatsApp number**
- Solution: Make sure you're sending TO the business number, not FROM it

**Issue: App in Development Mode**
- Solution: This is OK for testing. Make sure your phone number is added as a test user.

### 6. Check App Permissions

1. Go to **App Settings > Basic** (left sidebar)
2. Scroll to **App Mode**
3. If in "Development Mode":
   - Go to **Roles > Roles**
   - Add your phone number as a test user

### 7. Real-time Debugging

Run this in terminal to watch for incoming webhooks:
```bash
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow
```

Then send a message from your phone. You should see logs appear within 1-2 seconds.

### 8. Verify Webhook is Receiving Requests

Check recent invocations:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=agrinexus-webhook-dev \
  --start-time $(date -u -v-10M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

If you see invocations when you send messages, the webhook is working.
If you don't see invocations, Meta isn't sending webhooks.

## Next Steps After Webhook Works

Once messages are flowing:

1. Implement actual WhatsApp API calls (currently just logging)
2. Test onboarding flow
3. Test nudge engine
4. Test response detection

## Need Help?

If webhook still not working after checking all above:
1. Screenshot your Meta Dashboard webhook configuration
2. Check if your WhatsApp Business account is approved
3. Verify you're using the correct phone number format (+91XXXXXXXXXX)
