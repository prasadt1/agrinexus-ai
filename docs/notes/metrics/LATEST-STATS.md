# Latest System Stats - April 22, 2026

## 📊 Web Demo (Public Chat API)

### Last 7 Days (April 15-21)
| Date | Requests |
|------|----------|
| Apr 15 | 3 |
| Apr 16 | 14 |
| Apr 17 | 4 |
| Apr 18 | 38 (peak) |
| Apr 19 | 14 |
| Apr 20 | 24 |
| Apr 21 | 8 |
| **Total** | **105 requests** |

### Last 24 Hours (Hourly)
- 08:00 UTC: 6 requests
- 14:00 UTC: 2 requests
- **Total**: 8 requests

### API Health
- ✅ **5XX Errors**: 0 (no server errors)
- ⚠️ **4XX Errors**: 15 (client errors - likely rate limits or invalid requests)
- **Error Rate**: 14.3% (15/105)

### Database Activity
- **Web Chat Sessions in DB**: 0
- **Note**: Web chat doesn't persist sessions to DynamoDB (stateless API)

## 👥 WhatsApp Users
- **Total Users**: 7 unique phone numbers
- **Countries**: US, Germany, India, South Africa

## 🔔 Nudge Activity

### Total Nudges: 8

### Status Breakdown:
- ✅ **DONE**: 1 (12.5%) - User completed the action
- ⏰ **REMINDED**: 1 (12.5%) - Reminder sent, awaiting response
- 📤 **SENT**: 4 (50%) - Initial nudge sent, no response yet
- ⏱️ **EXPIRED**: 2 (25%) - No response after 72h

### Completion Rate: 12.5% (1/8)

## 🌐 CloudWatch RUM (Browser Monitoring)
- **Status**: Configured and active
- **Sessions Recorded**: 0
- **Reason**: Users accessing API directly (not loading HTML page in browser)
- **App Monitor**: `agrinexus-web-demo` (created Apr 20)

## ⚠️ Lambda Errors (Last 7 Days)

### Critical Issues:
- 🔴 **response-detector**: 4,359 errors (CRITICAL)
- 🔴 **dlq**: 2,014 errors (CRITICAL)
- 🟡 **webhook**: 56 errors
- 🟡 **reminder**: 9 errors

### Healthy Functions:
- ✅ **web-chat**: 0 errors
- ✅ **voice**: 0 errors
- ✅ **nudge-sender**: 0 errors
- ✅ **processor**: 1 error
- ✅ **weather**: 2 errors

### Analysis:
The high error count in `response-detector` (4,359) and `dlq` (2,014) suggests:
1. **DynamoDB Streams processing issues** - response-detector reads from streams
2. **Message processing failures** - messages landing in DLQ
3. **Possible retry loops** - same errors being retried multiple times

## 📈 Traffic Patterns

### Peak Activity:
- **Busiest Day**: April 18 (38 requests)
- **Busiest Hour**: Today at 08:00 UTC (6 requests)
- **Average**: 15 requests/day

### User Engagement:
- Web demo getting consistent traffic (105 requests over 7 days)
- Nudge system active with 8 nudges sent
- Low completion rate (12.5%) suggests need for optimization

## 🎯 Key Insights

### Positive:
✅ Web chat API is stable (0 server errors)
✅ Core Lambda functions working well
✅ Nudge system operational
✅ RUM monitoring configured

### Needs Attention:
⚠️ High error rate in response-detector and DLQ handlers
⚠️ 14.3% client error rate on web API
⚠️ Low nudge completion rate (12.5%)
⚠️ No RUM browser data (users not loading HTML page)

## 🔧 Recommended Actions

1. **Investigate response-detector errors** - Check CloudWatch Logs for root cause
2. **Review DLQ messages** - Understand why messages are failing
3. **Analyze 4XX errors** - Check if rate limiting is too aggressive
4. **Improve nudge engagement** - Current 12.5% completion is low
5. **Promote HTML demo page** - To get RUM browser telemetry

## 📊 Quick Stats Summary

```
Web Demo Requests (7d):     105
WhatsApp Users:             7
Nudges Sent:                8
Nudge Completion:           12.5%
API Error Rate:             14.3%
Lambda Errors (critical):   6,373
RUM Sessions:               0
```

---
*Generated: April 22, 2026 at $(date -u +"%H:%M UTC")*
