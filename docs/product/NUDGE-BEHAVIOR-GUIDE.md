# Behavioral Nudge System - Complete Flow Guide

## Overview

The nudge system sends weather-based reminders to farmers and follows up if they haven't completed the task. The system is designed to be helpful but not annoying.

## Complete Flow

### 1. Initial Nudge (T+0)

**Trigger**: Weather poller finds favorable conditions (wind < 10 km/h, no rain)

**Message** (Hindi example):
```
आज स्प्रे करने के लिए अच्छा मौसम है। हवा 8.5 km/h है और बारिश नहीं होगी। क्या आपने स्प्रे कर दिया?

कृपया "हो गया" भेजें जब आप स्प्रे कर लें।
```

**User Options**:
- Reply "हो गया" (DONE) → Flow ends, completion message sent
- Reply "अभी नहीं" (NOT YET) → Reminders scheduled
- No reply → Reminders scheduled

**System Action**:
- Creates nudge record with status: SENT
- Schedules T+24h reminder
- Schedules T+48h reminder

---

### 2. First Reminder (T+24h)

**Trigger**: 24 hours after initial nudge, if status is not DONE

**Message** (Hindi example):
```
याद दिलाना: कल हमने स्प्रे करने के लिए कहा था। क्या आपने कर लिया? "हो गया" या "अभी नहीं" भेजें।
```

**User Options**:

#### Option A: User replies "हो गया" (DONE)
- **Response**: "बहुत अच्छा! आपका काम पूरा हो गया। धन्यवाद! 🎉"
- **System Action**:
  - Updates status to DONE
  - Cancels T+48h reminder
  - Emits NudgesCompleted metric
  - Flow ends

#### Option B: User replies "अभी नहीं" (NOT YET)
- **Response**: "कोई बात नहीं। मैं आपको बाद में याद दिलाऊंगा। 👍"
- **System Action**:
  - Updates status to REMINDED
  - T+48h reminder remains scheduled
  - Flow continues

#### Option C: No reply
- **System Action**:
  - Updates status to REMINDED
  - T+48h reminder remains scheduled
  - Flow continues

---

### 3. Final Reminder (T+48h)

**Trigger**: 48 hours after initial nudge, if status is not DONE

**Message** (Hindi example):
```
अंतिम याद दिलाना: स्प्रे करना बाकी है। कृपया जल्द करें और "हो गया" भेजें।
```

**User Options**:

#### Option A: User replies "हो गया" (DONE)
- **Response**: "बहुत अच्छा! आपका काम पूरा हो गया। धन्यवाद! 🎉"
- **System Action**:
  - Updates status to DONE
  - Emits NudgesCompleted metric
  - Flow ends

#### Option B: User replies "अभी नहीं" (NOT YET)
- **Response**: "कोई बात नहीं। जब आप तैयार हों तो कर लें। अगली बार मौसम अच्छा होगा तो मैं फिर से याद दिलाऊंगा। 👍"
  - Translation: "No problem. Do it when you're ready. Next time the weather is good, I'll remind you again."
- **System Action**:
  - No more reminders for this nudge
  - Flow ends gracefully
  - User will get a fresh nudge next time weather is favorable

#### Option C: No reply
- **System Action**:
  - No more reminders for this nudge
  - Flow ends
  - User will get a fresh nudge next time weather is favorable

---

## Key Behaviors

### Duplicate Prevention
- **Rule**: Max 1 nudge per activity per day
- **Check**: Before creating new nudge, system checks for existing pending nudges
- **Result**: Farmers won't get spammed with multiple nudges on the same day

### Reminder Cancellation
- **Trigger**: User replies "हो गया" (DONE) at any stage
- **Action**: All scheduled reminders are immediately cancelled
- **Implementation**: EventBridge Scheduler schedules are deleted

### Response Detection
- **Method**: DynamoDB Streams trigger on new messages
- **Keywords Detected**:
  - DONE: हो गया, कर दिया, done, completed
  - NOT YET: अभी नहीं, बाद में, not yet, later
- **Multi-language**: Works in Hindi, Marathi, Telugu, English

### Status Transitions
```
SENT → REMINDED → DONE
  ↓       ↓         ↑
  └───────┴─────────┘
   (user replies "हो गया")
```

### Weather Polling
- **Frequency**: Every 6 hours (configurable via EventBridge)
- **Mode**: Mock mode (default) or Real weather API
- **Mock Mode**: Always returns favorable conditions for Latur, Jalna, Nagpur
- **Real Mode**: Calls OpenWeather API with actual conditions

---

## Message Templates by Language

### Hindi (hi)
- **Initial**: "आज स्प्रे करने के लिए अच्छा मौसम है..."
- **T+24h**: "याद दिलाना: कल हमने स्प्रे करने के लिए कहा था..."
- **T+48h**: "अंतिम याद दिलाना: स्प्रे करना बाकी है..."
- **DONE**: "बहुत अच्छा! आपका काम पूरा हो गया। धन्यवाद! 🎉"
- **NOT YET (T+24h)**: "कोई बात नहीं। मैं आपको बाद में याद दिलाऊंगा। 👍"
- **NOT YET (T+48h)**: "कोई बात नहीं। जब आप तैयार हों तो कर लें। अगली बार मौसम अच्छा होगा तो मैं फिर से याद दिलाऊंगा। 👍"

### Marathi (mr)
- **Initial**: "आज फवारणीसाठी चांगले हवामान आहे..."
- **T+24h**: "आठवण: काल आम्ही फवारणी करण्यास सांगितले होते..."
- **T+48h**: "शेवटची आठवण: फवारणी बाकी आहे..."
- **DONE**: "खूप छान! तुमचे काम पूर्ण झाले. धन्यवाद! 🎉"
- **NOT YET (T+24h)**: "काही हरकत नाही. मी तुम्हाला नंतर आठवण करून देईन. 👍"
- **NOT YET (T+48h)**: "काही हरकत नाही. तुम्ही तयार असाल तेव्हा करा. पुढच्या वेळी हवामान चांगले असेल तर मी पुन्हा आठवण करून देईन. 👍"

### Telugu (te)
- **Initial**: "ఈరోజు స్ప్రే చేయడానికి మంచి వాతావరణం..."
- **T+24h**: "గుర్తు: నిన్న మేము స్ప్రే చేయమని చెప్పాము..."
- **T+48h**: "చివరి గుర్తు: స్ప్రే చేయడం మిగిలి ఉంది..."
- **DONE**: "చాలా బాగుంది! మీ పని పూర్తయింది. ధన్యవాదాలు! 🎉"
- **NOT YET (T+24h)**: "పర్వాలేదు. నేను మీకు తర్వాత గుర్తు చేస్తాను. 👍"
- **NOT YET (T+48h)**: "పర్వాలేదు. మీరు సిద్ధంగా ఉన్నప్పుడు చేయండి. తదుపరిసారి వాతావరణం మంచిగా ఉంటే నేను మళ్లీ గుర్తు చేస్తాను. 👍"

---

## Testing Scripts

### Reset User Profile
```bash
./scripts/reset-user-profile.sh 919876543210
```
Deletes profile, messages, and nudges for fresh onboarding test.

### Trigger Nudge
```bash
./scripts/trigger-nudge-test.sh 919876543210
```
Manually triggers weather poller and checks if nudge was created.

### Test T+24h Reminder
```bash
./scripts/test-reminder.sh 919876543210 T+24h
```
Immediately sends T+24h reminder (bypasses 24h wait).

### Test T+48h Reminder
```bash
./scripts/test-reminder.sh 919876543210 T+48h
```
Immediately sends T+48h reminder (bypasses 48h wait).

---

## Monitoring

### CloudWatch Metrics
- **AgriNexus/NudgesSent**: Count of nudges sent
- **AgriNexus/NudgesCompleted**: Count of completed tasks

### CloudWatch Logs
```bash
# Weather poller
aws logs tail /aws/lambda/agrinexus-weather-dev --follow

# Nudge sender
aws logs tail /aws/lambda/agrinexus-nudge-sender-dev --follow

# Reminder sender
aws logs tail /aws/lambda/agrinexus-reminder-dev --follow

# Response detector
aws logs tail /aws/lambda/agrinexus-response-detector-dev --follow
```

### DynamoDB Queries
```bash
# Check nudge status
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"USER#919876543210"},":sk":{"S":"NUDGE#"}}'

# Check scheduled reminders
aws scheduler list-schedules --query 'Schedules[?contains(Name, `reminder`)]'
```

---

## Design Rationale

### Why T+24h and T+48h?
- **T+24h**: Gives farmer one day to complete the task
- **T+48h**: Final reminder before giving up
- **No T+72h**: Avoids being annoying; weather may have changed

### Why Different Messages for Final "NOT YET"?
- **Empathy**: Acknowledges farmer's constraints
- **Clarity**: Explicitly states no more reminders for this nudge
- **Reassurance**: Confirms they'll get help next time
- **Reduces Anxiety**: Farmer doesn't feel pressured or guilty

### Why Cancel Reminders on "DONE"?
- **Respect**: Don't bother farmers after they've completed the task
- **Cost**: Reduces unnecessary Lambda invocations
- **UX**: Shows system is responsive and intelligent

---

## Future Enhancements

1. **Adaptive Timing**: Learn optimal reminder times per farmer
2. **Activity Types**: Support irrigation, fertilizer, harvesting nudges
3. **Weather Forecasts**: "Rain expected tomorrow, spray today"
4. **Completion Rates**: Track and optimize nudge effectiveness
5. **Personalization**: Adjust frequency based on farmer responsiveness

---

## Summary

The nudge system is designed to be:
- **Helpful**: Timely reminders based on weather
- **Respectful**: Max 3 messages per nudge (initial + 2 reminders)
- **Intelligent**: Responds differently to DONE vs NOT YET
- **Empathetic**: Different final message acknowledges farmer's situation
- **Non-intrusive**: Stops after T+48h, waits for next favorable weather

This creates a positive behavioral intervention that helps farmers without being annoying.
