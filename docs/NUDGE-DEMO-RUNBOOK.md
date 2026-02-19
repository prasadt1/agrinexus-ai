# Nudge Demo Runbook (Judge-Friendly)

Use this script to demonstrate the behavioral nudge loop in ~3 minutes.

## Pre-reqs
- Deployed stack (dev)
- WhatsApp webhook configured
- Test phone number onboarded
- (Optional) `MOCK_WEATHER=true` for deterministic nudges

## Demo Steps

1. **Onboard user (language + location)**
   - Send: `English`
   - Send: `Aurangabad`
   - Send: `Cotton`
   - Send: `Yes`

2. **Trigger nudge**
   ```bash
   aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/response.json
   ```

3. **Show nudge + completion**
   - User receives spray nudge
   - Reply: `DONE`
   - Bot confirms completion

4. **Show NOT YET path**
   - Reply: `NOT YET`
   - Bot acknowledges and reminders continue

## Multi-language Quick Checks
- Hindi: `हिंदी` + `हो गया`
- Marathi: `मराठी` + `झाला`
- Telugu: `తెలుగు` + `అయ్యింది`
- English: `English` + `DONE`

## Automation (Optional)

```bash
WEBHOOK_URL="https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/webhook" \
FROM_NUMBER="919876543210" \
APP_SECRET="YOUR_APP_SECRET" \
./scripts/demo-nudge-flow.sh
```

## Expected Outcome
- Nudge is sent based on location
- DONE marks completion and stops reminders
- NOT YET keeps reminders active
- Completion rate updates in CloudWatch dashboard
