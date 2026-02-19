# Nudge Feature Test Checklist (MVP)

Use this checklist to validate the behavioral nudge system end-to-end.

## 1. Triggering
- Weather favorable -> nudge sent
- Weather unfavorable -> no nudge sent
- District targeting works (only farmers in location get nudged)

## 2. Deduplication
- Same day, same activity -> no duplicate nudge
- Next day -> new nudge allowed

## 3. Reminders
- T+24h reminder sent if no DONE
- T+48h reminder sent if still no DONE

## 4. Responses
- DONE (Hindi/Marathi/Telugu/English) -> mark DONE, cancel reminders, send confirmation
- NOT YET -> reminders continue, acknowledgement sent

## 5. Template vs Fallback
- Template send success -> no text fallback
- Template send fails -> text fallback sent

## 6. Multi-language
- Hindi -> `hi` template
- Marathi -> `mr` template
- Telugu -> `te` template
- English -> `en` template

## 7. Edge Cases
- Missing profile -> no nudge
- Invalid/empty message -> ignored safely

## Quick Demo Run

```bash
WEBHOOK_URL="https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/webhook" \
FROM_NUMBER="919876543210" \
APP_SECRET="YOUR_APP_SECRET" \
./scripts/demo-nudge-flow.sh
```
