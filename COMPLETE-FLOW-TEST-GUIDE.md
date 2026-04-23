# Complete Flow Test Guide

**Phone Number:** +49 1764 7009148  
**WhatsApp Bot:** +49 1512 0105731  
**Date:** April 17, 2026

---

## Test Sequence

### ✅ STEP 1: Onboarding (5 minutes)

**Action:** Send messages to WhatsApp bot

1. **Send:** `Hi`
   - **Expect:** Language selection list (English, हिंदी, मराठी, తెలుగు)

2. **Select:** `मराठी (Marathi)`
   - **Expect:** District selection buttons (लातूर, जालना, नागपूर)

3. **Click:** `नागपूर` (Nagpur)
   - **Expect:** Crop selection buttons (कापूस, गहू, सोयाबीन)

4. **Click:** `कापूस` (Cotton)
   - **Expect:** Consent question with buttons (होय ✅, नाही ❌)

5. **Click:** `होय ✅` (Yes)
   - **Expect:** "अभिनंदन! तुमचे प्रोफाइल तयार आहे..."

**Status:** ✅ Onboarding complete

---

### ✅ STEP 2: Update Profile for Full Reminders

**Action:** Run this command to enable T+24h/T+48h reminders:

```bash
aws dynamodb update-item \
  --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#1555123456789"},"SK":{"S":"PROFILE"}}' \
  --update-expression "SET demo_tier = :tier" \
  --expression-attribute-values '{":tier":{"S":"full"}}'
```

**Status:** ✅ Profile updated to `demo_tier: full`

---

### ✅ STEP 3: Trigger First Nudge

**Action:** Manually invoke weather poller

```bash
aws lambda invoke \
  --function-name agrinexus-weather-dev \
  --payload '{}' \
  /tmp/weather-response.json

cat /tmp/weather-response.json | python3 -m json.tool
```

**Expect in WhatsApp (~10 seconds):**
```
Nagpur: हवामान अनुकूल आहे. वारा X.X km/h आहे. कृपया फवारणी करा.

Buttons: [झाला] [नाही झाला]
```

**Action:** Click `नाही झाला` (Not Yet)

**Expect:**
```
ठीक आहे. आम्ही तुम्हाला आठवण करून देऊ.
```

**Status:** ✅ First nudge sent, acknowledged as "Not Yet"

---

### ✅ STEP 4: Text Query (RAG Test)

**Action:** Send text message

**Send:** `कापसात पांढरी माशी कशी नियंत्रित करावी?`

**Expect (~5-10 seconds):**
```
पांढरी माशी नियंत्रित करण्यासाठी...
[Detailed response with treatment recommendations]

📚 स्त्रोत: FAO/ICAR शेती मार्गदर्शक
```

**Status:** ✅ RAG query successful with source citation

---

### ✅ STEP 5: Voice Note (Transcription Test)

**Action:** Send voice note from WhatsApp

**Example message (in Marathi):**
> "कापसात किडे कसे नियंत्रित करावे?"

**Expect immediately:**
```
आपली आवाज नोंद मिळाली. आम्ही ऐकत आहोत आणि लवकरच उत्तर देऊ.
```

**Expect after ~30-40 seconds:**
```
[Transcribed text + RAG response]

📚 स्त्रोत: FAO/ICAR शेती मार्गदर्शक
```

**Status:** ✅ Voice transcription + RAG successful

---

### ✅ STEP 6: Photo Analysis (Vision Test)

**Action:** Send crop photo from WhatsApp

**Example:** Photo of cotton leaf with pests/disease

**Expect (~10-15 seconds):**
```
हे कापसाचे पान आहे...

[Pest/disease identification]
[Treatment recommendations]
[Preventive measures]
```

**Status:** ✅ Vision analysis successful

---

### ✅ STEP 7: Simulate T+24h Reminder

**Action:** Manually invoke reminder Lambda

First, get the nudge ID:
```bash
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{"pk":{"S":"USER#1555123456789"},":sk":{"S":"NUDGE#"}}' \
  --query 'Items[0].SK.S' \
  --output text
```

Copy the nudge ID (e.g., `NUDGE#2026-04-17T10:15:02.636018#spray`), remove `NUDGE#` prefix.

Then invoke reminder:
```bash
aws lambda invoke \
  --function-name agrinexus-reminder-dev \
  --payload '{
    "phone_number": "1555123456789",
    "nudge_id": "2026-04-17T10:15:02.636018#spray",
    "reminder_type": "T+24h",
    "dialect": "mr"
  }' \
  /tmp/reminder-response.json
```

**Expect in WhatsApp (~5 seconds):**
```
अजून फवारणी केली नाही का? हवामान अनुकूल आहे.

Buttons: [झाला] [नाही झाला]
```

**Action:** Click `झाला` (Done)

**Expect:**
```
बढ़िया! तुम्ही फवारणी केली. धन्यवाद!
```

**Status:** ✅ T+24h reminder sent, marked as DONE

---

## Verification Commands

### Check Profile
```bash
aws dynamodb get-item \
  --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#1555123456789"},"SK":{"S":"PROFILE"}}' \
  --query 'Item.{dialect:dialect.S,location:location.S,crop:crop.S,demo_tier:demo_tier.S,consent:consent.BOOL}'
```

### Check Messages
```bash
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{"pk":{"S":"USER#1555123456789"},":sk":{"S":"MSG#"}}' \
  --query 'Count'
```

### Check Nudges
```bash
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{"pk":{"S":"USER#1555123456789"},":sk":{"S":"NUDGE#"}}' \
  --query 'Items[*].{nudge_id:SK.S,status:status.S,activity:activity.S}'
```

### Check Logs
```bash
# Webhook logs
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow

# Processor logs
aws logs tail /aws/lambda/agrinexus-processor-dev --follow

# Voice logs
aws logs tail /aws/lambda/agrinexus-voice-dev --follow

# Nudge sender logs
aws logs tail /aws/lambda/agrinexus-nudge-sender-dev --follow

# Reminder logs
aws logs tail /aws/lambda/agrinexus-reminder-dev --follow
```

---

## Automated Script (Optional)

If you want to automate steps 1-3 and 7:

```bash
cd scripts
./test-complete-flow.sh
```

This will:
- ✅ Run onboarding automatically
- ✅ Update profile to full tier
- ✅ Trigger weather poller
- ⏸️  Pause for manual voice note
- ⏸️  Pause for manual photo
- ✅ Simulate T+24h reminder

---

## Expected Timeline

| Step | Action | Time |
|------|--------|------|
| 1 | Onboarding | 5 min |
| 2 | Update profile | 10 sec |
| 3 | First nudge | 10 sec |
| 4 | Text query | 10 sec |
| 5 | Voice note | 40 sec |
| 6 | Photo | 15 sec |
| 7 | T+24h reminder | 10 sec |
| **Total** | | **~7 minutes** |

---

## Success Criteria

- ✅ Onboarding completed in Marathi
- ✅ Profile created with Nagpur, Cotton, consent=true
- ✅ First nudge received and acknowledged as "Not Yet"
- ✅ Text query answered with RAG + source citation
- ✅ Voice note transcribed and answered
- ✅ Photo analyzed with pest/disease identification
- ✅ T+24h reminder received and marked as "Done"
- ✅ Nudge status updated to DONE in DynamoDB
- ✅ Scheduled reminders cancelled

---

## Troubleshooting

### No nudge received after weather poll
```bash
# Check weather poller output
cat /tmp/weather-response.json | python3 -m json.tool

# Check if Nagpur had favorable weather
# Should show: "favorable": true, "wind_speed": < 10
```

### Voice note not transcribed
```bash
# Check voice processor logs
aws logs tail /aws/lambda/agrinexus-voice-dev --since 5m

# Verify audio was downloaded to S3
aws s3 ls s3://agrinexus-temp-audio-dev-043624892076/voice/
```

### Photo not analyzed
```bash
# Check processor logs for vision errors
aws logs tail /aws/lambda/agrinexus-processor-dev --since 5m | grep -i vision
```

### Reminder not sent
```bash
# Check if nudge exists
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{"pk":{"S":"USER#1555123456789"},":sk":{"S":"NUDGE#"}}'

# Check reminder Lambda logs
aws logs tail /aws/lambda/agrinexus-reminder-dev --since 5m
```

---

**Ready to start?** Follow the steps above in order! 🚀
