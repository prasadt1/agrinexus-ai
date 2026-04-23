# Nudge Diagnosis for 4917647009148

## Issue Found
You were **not in the allowlist**, which prevented you from receiving new nudges.

## Root Cause
The nudge sender (`src/nudge/sender.py`) has an allowlist check that gates nudges:
```python
if not is_approved_user(table, phone_number):
    print(f"Skipping {phone_number} - not allowlisted for nudges")
    nudges_skipped += 1
    continue
```

## Solution Applied
✅ Added your phone number (4917647009148) to the allowlist using:
```bash
python3 scripts/allowlist-user.py --table agrinexus-data add 4917647009148
```

## Current Status

### User Profile
- **Phone**: 4917647009148
- **Location**: Latur
- **Crop**: Wheat
- **Dialect**: Hindi (hi)
- **Demo Tier**: public
- **Onboarding**: Complete
- **Allowlist**: ✅ **NOW APPROVED** (as of 2026-04-21T09:26:01+00:00)

### Latest Nudge
- **Date**: 2026-04-19T04:15:14
- **Status**: SENT (not responded yet)
- **Activity**: spray
- **Message**: "Latur: गेहूं में स्प्रे के लिए मौसम अनुकूल है। हवा 0.7 km/h है। कृपया स्प्रे करें।"
- **Weather**: Favorable (wind 0.7 km/h, no rain, temp 34.63°C)

### System Stats
- **Total Users**: 7
- **Web Demo Visits**: 0
- **All Users**: 
  - 18475259648
  - 4917647009148 (you)
  - 16465894168
  - 0000000000
  - 918975643452
  - 27783595810
  - 27797515485

## Next Steps

### When Will You Get Nudges?
The weather poller runs **every 6 hours** (configured in template-week2.yaml):
```yaml
Events:
  ScheduledPoll:
    Type: Schedule
    Schedule: rate(6 hours)
```

### Nudge Conditions
You'll receive a nudge when:
1. ✅ You're in the allowlist (NOW FIXED)
2. ✅ Weather is favorable in Latur (wind < 10 km/h, no rain)
3. ✅ You don't have a pending nudge for the same activity today
4. ✅ Your profile has `demo_tier: public` (you get one nudge, no T+24h/T+48h reminders)

### Demo Tier Behavior
Since your `demo_tier` is set to "public", you will:
- ✅ Receive nudges when weather is favorable
- ❌ NOT receive T+24h and T+48h reminder follow-ups
- This is by design for demo users (see `sender.py` line 235-240)

### To Get Full Reminders
If you want T+24h and T+48h reminders, update your profile:
```bash
aws dynamodb update-item \
  --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#4917647009148"},"SK":{"S":"PROFILE"}}' \
  --update-expression "SET demo_tier = :tier" \
  --expression-attribute-values '{":tier":{"S":"full"}}'
```

## Testing
To manually trigger a nudge for testing:
```bash
./scripts/demo-video-nudge-triggers.sh
```

Or invoke the weather poller Lambda directly:
```bash
aws lambda invoke --function-name agrinexus-weather-dev /dev/stdout
```
