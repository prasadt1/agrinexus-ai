# Interactive Buttons - Comprehensive Test Plan

## Test Environment
- WhatsApp Number: +49 176 47009148
- Test Number (API): +1 555 158 3325
- Webhook URL: https://nwo9tkvpoi.execute-api.us-east-1.amazonaws.com/dev/webhook
- DynamoDB Table: agrinexus-data
- Stack: agrinexus-week2

---

## Test Suite 1: Onboarding Flow - All Languages

### Test 1.1: English Onboarding ✓
**Steps:**
1. Clear profile: `aws dynamodb delete-item --table-name agrinexus-data --key '{"PK":{"S":"USER#+4917647009148"},"SK":{"S":"PROFILE"}}'`
2. Send "Hello" to WhatsApp
3. Click [English] button
4. Click [Aurangabad] button
5. Click [Cotton] button
6. Click [Yes ✅] button

**Expected:**
- Multilingual welcome message appears
- District buttons appear with English prompt
- Crop buttons appear: [Cotton] [Wheat] [Soybean]
- Consent buttons appear: [Yes ✅] [No ❌]
- Completion message: "Congratulations! Your profile is ready..."

**Status:** ⏳ TO TEST

---

### Test 1.2: Hindi Onboarding ✓
**Steps:**
1. Clear profile
2. Send "Namaste" to WhatsApp
3. Click [हिंदी] button
4. Click [Aurangabad] button
5. Click [कपास] button
6. Click [हाँ ✅] button

**Expected:**
- Multilingual welcome message appears
- District buttons with Hindi prompt: "बढ़िया! अब मुझे बताएं आप किस जिले में हैं?"
- Crop buttons: [कपास] [गेहूं] [सोयाबीन]
- Consent buttons: [हाँ ✅] [नहीं ❌]
- Completion: "बधाई हो! आपका प्रोफाइल तैयार है..."

**Status:** ✅ TESTED & WORKING

---

### Test 1.3: Marathi Onboarding ✓
**Steps:**
1. Clear profile
2. Send "Namaste"
3. Click [मराठी] button
4. Click [Jalna] button
5. Click [गहू] button (Wheat)
6. Click [होय ✅] button

**Expected:**
- Marathi prompts throughout
- Crop buttons: [कापूस] [गहू] [सोयाबीन]
- Consent buttons: [होय ✅] [नाही ❌]
- Completion: "अभिनंदन! तुमचे प्रोफाइल तयार आहे..."

**Status:** ✅ TESTED & WORKING

---

### Test 1.4: Telugu Onboarding ✓
**Steps:**
1. Clear profile
2. Send "Namaste"
3. Type "Telugu" (no button, type-in option)
4. Click [Nagpur] button
5. Click [సోయాబీన్] button (Soybean)
6. Click [అవును ✅] button

**Expected:**
- Telugu prompts throughout
- Crop buttons: [పత్తి] [గోధుమ] [సోయాబీన్]
- Consent buttons: [అవును ✅] [కాదు ❌]
- Completion: "అభినందనలు! మీ ప్రొఫైల్ సిద్ధంగా ఉంది..."

**Status:** ✅ TESTED & WORKING

---

## Test Suite 2: District Flexibility

### Test 2.1: Click District Button
**Steps:**
1. Start onboarding in Hindi
2. Click [Aurangabad] button

**Expected:**
- Proceeds to crop selection
- Location stored as "Aurangabad"

**Status:** ⏳ TO TEST

---

### Test 2.2: Type Any District Name
**Steps:**
1. Start onboarding in English
2. Type "Mumbai" (not in button list)

**Expected:**
- Accepts "Mumbai" as location
- Proceeds to crop selection
- Location stored as "Mumbai"
- Note: Weather nudges won't work for Mumbai (only Aurangabad/Jalna/Nagpur configured)

**Status:** ⏳ TO TEST

---

### Test 2.3: Type Invalid Input
**Steps:**
1. Start onboarding
2. Type "xyz" (too short)

**Expected:**
- Shows district buttons again with prompt

**Status:** ⏳ TO TEST

---

## Test Suite 3: Nudge Flow - All Languages

### Test 3.1: Hindi Nudge Flow ✓
**Steps:**
1. Complete Hindi onboarding with Aurangabad + Cotton + Yes
2. Trigger weather: `aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/weather-response.json`
3. Receive nudge in Hindi
4. Reply "हो गया"

**Expected:**
- Nudge: "आज स्प्रे करने के लिए अच्छा मौसम है..."
- Response: "बहुत अच्छा! आपका काम पूरा हो गया। धन्यवाद! 🎉"
- DynamoDB: Nudge status = DONE
- EventBridge: Reminders cancelled

**Status:** ✅ TESTED & WORKING

---

### Test 3.2: Marathi Nudge Flow ✓
**Steps:**
1. Complete Marathi onboarding
2. Trigger weather
3. Reply "झाला"

**Expected:**
- Nudge in Marathi
- Response: "खूप छान! तुमचे काम पूर्ण झाले. धन्यवाद! 🎉"

**Status:** ✅ TESTED & WORKING

---

### Test 3.3: Telugu Nudge Flow ✓
**Steps:**
1. Complete Telugu onboarding
2. Trigger weather
3. Reply "అయ్యింది"

**Expected:**
- Nudge in Telugu
- Response: "చాలా బాగుంది! మీ పని పూర్తయింది. ధన్యవాదాలు! 🎉"

**Status:** ✅ TESTED & WORKING

---

### Test 3.4: English Nudge Flow
**Steps:**
1. Complete English onboarding
2. Trigger weather
3. Reply "done"

**Expected:**
- Nudge in English (need to add English nudge messages to sender.py)
- Response: "Great! Task completed. Thank you! 🎉"

**Status:** ⏳ TO TEST (Need to add English nudge messages)

---

### Test 3.5: NOT YET Response - Hindi
**Steps:**
1. Receive Hindi nudge
2. Reply "अभी नहीं"

**Expected:**
- Response: "कोई बात नहीं। मैं आपको बाद में याद दिलाऊंगा। 👍"
- Reminders remain active

**Status:** ⏳ TO TEST

---

## Test Suite 4: RAG Query Flow

### Test 4.1: Hindi Query After Onboarding
**Steps:**
1. Complete Hindi onboarding
2. Send: "कपास में कीट कैसे नियंत्रित करें?"

**Expected:**
- Immediate acknowledgment: "✓ आपका सवाल मिल गया। जवाब तैयार कर रहे हैं..."
- Bedrock response with citations (~13 seconds)

**Status:** ⏳ TO TEST

---

### Test 4.2: English Query
**Steps:**
1. Complete English onboarding
2. Send: "How to control pests in cotton?"

**Expected:**
- Acknowledgment: "✓ Question received. Preparing answer..."
- Bedrock response in English

**Status:** ⏳ TO TEST

---

## Test Suite 5: Edge Cases

### Test 5.1: Button Click vs Text Input
**Steps:**
1. Start onboarding
2. Instead of clicking [Hindi], type "Hindi"

**Expected:**
- Should work the same as clicking button

**Status:** ⏳ TO TEST

---

### Test 5.2: Invalid Language Selection
**Steps:**
1. Start onboarding
2. Type "French"

**Expected:**
- Shows language buttons again

**Status:** ⏳ TO TEST

---

### Test 5.3: Onboarding Interruption
**Steps:**
1. Start onboarding, select language
2. Send random message before completing

**Expected:**
- Continues onboarding flow
- Asks for next step (location)

**Status:** ⏳ TO TEST

---

### Test 5.4: Multiple Nudges Same Day
**Steps:**
1. Complete onboarding
2. Trigger weather multiple times
3. Reply "हो गया" to first nudge

**Expected:**
- Only first active nudge marked as DONE
- Other nudges remain SENT

**Status:** ⏳ TO TEST

---

## Test Suite 6: Performance

### Test 6.1: Response Time - Onboarding
**Steps:**
1. Measure time from button click to next message

**Expected:**
- < 2 seconds for button responses

**Status:** ⏳ TO TEST

---

### Test 6.2: Response Time - RAG Query
**Steps:**
1. Send query, measure time to acknowledgment
2. Measure time to full response

**Expected:**
- Acknowledgment: < 2 seconds
- Full response: < 15 seconds

**Status:** ⏳ TO TEST

---

## Test Suite 7: Data Verification

### Test 7.1: Profile Storage
**Steps:**
1. Complete onboarding
2. Check DynamoDB:
```bash
aws dynamodb get-item --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#+4917647009148"},"SK":{"S":"PROFILE"}}'
```

**Expected:**
- dialect: correct value
- location: correct value
- crop: correct value
- consent: true/false
- onboarding_complete: true

**Status:** ⏳ TO TEST

---

### Test 7.2: Nudge Storage
**Steps:**
1. Trigger weather
2. Check DynamoDB for nudge records

**Expected:**
- PK: USER#+4917647009148
- SK: NUDGE#{timestamp}#spray
- status: SENT
- message: in correct dialect

**Status:** ⏳ TO TEST

---

## Known Issues to Document

1. **Telugu Button**: No button for Telugu (WhatsApp 3-button limit) - must type "Telugu"
2. **English Nudges**: Need to add English nudge messages to sender.py
3. **District Validation**: Accepts any district, but weather nudges only work for 3 configured districts
4. **Font Rendering**: Some devices may show messy text for Indic scripts (device-specific, not our issue)

---

## Testing Commands

### Clear User Profile
```bash
aws dynamodb delete-item --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#+4917647009148"},"SK":{"S":"PROFILE"}}'
```

### Trigger Weather Poller
```bash
aws lambda invoke --function-name agrinexus-weather-dev \
  --payload '{}' /tmp/weather-response.json && cat /tmp/weather-response.json
```

### Check User Profile
```bash
aws dynamodb get-item --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#+4917647009148"},"SK":{"S":"PROFILE"}}'
```

### Check Nudges
```bash
aws dynamodb query --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"USER#+4917647009148"},":sk":{"S":"NUDGE#"}}'
```

### Check CloudWatch Logs
```bash
# Webhook
aws logs tail /aws/lambda/agrinexus-webhook-dev --since 5m --follow

# Processor
aws logs tail /aws/lambda/agrinexus-processor-dev --since 5m --follow

# Nudge Sender
aws logs tail /aws/lambda/agrinexus-nudge-sender-dev --since 5m --follow

# Response Detector
aws logs tail /aws/lambda/agrinexus-response-detector-dev --since 5m --follow
```

---

## Test Execution Plan

### Phase 1: Core Onboarding (30 minutes)
- [ ] Test 1.1: English onboarding
- [ ] Test 1.2: Hindi onboarding (already done)
- [ ] Test 1.3: Marathi onboarding (already done)
- [ ] Test 1.4: Telugu onboarding (already done)

### Phase 2: District Flexibility (15 minutes)
- [ ] Test 2.1: Click district button
- [ ] Test 2.2: Type any district
- [ ] Test 2.3: Invalid input

### Phase 3: Nudge Flows (30 minutes)
- [ ] Test 3.1: Hindi nudge (already done)
- [ ] Test 3.2: Marathi nudge (already done)
- [ ] Test 3.3: Telugu nudge (already done)
- [ ] Test 3.4: English nudge (need to add English messages first)
- [ ] Test 3.5: NOT YET response

### Phase 4: RAG Queries (15 minutes)
- [ ] Test 4.1: Hindi query
- [ ] Test 4.2: English query

### Phase 5: Edge Cases (20 minutes)
- [ ] Test 5.1-5.4: All edge cases

### Phase 6: Performance & Data (15 minutes)
- [ ] Test 6.1-6.2: Performance
- [ ] Test 7.1-7.2: Data verification

**Total Estimated Time: 2 hours**

---

## Test Results Summary

| Test Suite | Total Tests | Passed | Failed | Pending |
|------------|-------------|--------|--------|---------|
| Onboarding | 4 | 3 | 0 | 1 |
| District | 3 | 0 | 0 | 3 |
| Nudge Flow | 5 | 3 | 0 | 2 |
| RAG Query | 2 | 0 | 0 | 2 |
| Edge Cases | 4 | 0 | 0 | 4 |
| Performance | 2 | 0 | 0 | 2 |
| Data | 2 | 0 | 0 | 2 |
| **TOTAL** | **22** | **6** | **0** | **16** |

---

## Next Steps After Testing

1. Fix any issues found
2. Add English nudge messages if missing
3. Document any limitations
4. Update WEEK2-COMPLETE.md with test results
5. Commit final tested version
6. Move to Week 3 (Voice + Vision)
