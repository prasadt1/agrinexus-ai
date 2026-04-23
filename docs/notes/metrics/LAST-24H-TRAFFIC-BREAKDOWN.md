# Last 24 Hours Traffic Breakdown
*Generated: April 23, 2026*

## 📊 Total Traffic Summary

### Last 24 Hours (April 22-23)
- **WhatsApp API**: 26 requests
- **Web Demo API**: 15 requests
- **Total**: 41 requests

---

## 📱 WhatsApp Traffic Analysis

### Total: 26 webhook requests

### By User (Messages Only):
**Only 1 active user in last 24 hours:**

| User | Messages | Percentage |
|------|----------|------------|
| **4917647009148** (YOU) | 10 | 100% |

### Message Content (Last 24h):
All 10 messages from **4917647009148**:

**Questions asked:**
1. "gehu mey kis prakaar k kidey lag sakate hai" (4 times)
   - Translation: "What types of pests can affect wheat?"
   
2. "soyabean ko kitana paani dena chaihiye?" (6 times)
   - Translation: "How much water should be given to soybean?"

**Pattern**: Repeated questions (likely testing or waiting for responses)

### Hourly Breakdown (WhatsApp):
| Hour (UTC) | Requests |
|------------|----------|
| 23h (Apr 22) | 5 |
| 00h (Apr 23) | 16 |
| 01h (Apr 23) | 5 |

**Peak**: Midnight UTC (00h) with 16 requests

---

## 🌐 Web Demo Traffic Analysis

### Total: 15 API requests

### Hourly Breakdown:
| Hour (UTC) | Requests |
|------------|----------|
| 08h (Apr 22) | 1 |
| 23h (Apr 22) | 4 |
| 00h (Apr 23) | 6 |
| 01h (Apr 23) | 4 |

**Peak**: Midnight UTC (00h) with 6 requests

### User Identification:
⚠️ **Cannot identify individual users/IPs** because:
1. **API Gateway Access Logs**: Not enabled
2. **DynamoDB**: Web chat doesn't persist sessions (stateless API)
3. **Lambda Logs**: Don't include source IP by default

**What we know:**
- 15 Lambda invocations (15 unique API calls)
- No session tracking in database
- No IP address logging configured

**To track web demo users, you would need to:**
1. Enable API Gateway Access Logs
2. Add IP tracking to Lambda handler
3. Store session data in DynamoDB with IP/client_id

---

## 🕐 Traffic Patterns

### Time Distribution (UTC):
```
22h: ▏ (0)
23h: ████████ (9 total: 5 WhatsApp + 4 Web)
00h: ████████████████████ (22 total: 16 WhatsApp + 6 Web)
01h: ████████ (9 total: 5 WhatsApp + 4 Web)
02h: ▏ (0)
```

**Peak Activity**: Midnight UTC (00:00-01:00)
- WhatsApp: 16 requests
- Web Demo: 6 requests

**Time Zone Analysis**:
- Midnight UTC = 5:30 AM IST (India)
- Midnight UTC = 1:00 AM CET (Germany)

**Your activity (4917647009148)** appears to be from **Germany** (CET timezone), active around midnight-1am local time.

---

## 📈 Comparison: WhatsApp vs Web Demo

| Metric | WhatsApp | Web Demo |
|--------|----------|----------|
| Total Requests | 26 | 15 |
| Peak Hour | 00h (16) | 00h (6) |
| Active Users | 1 (you) | Unknown |
| Messages/Queries | 10 | 15 |
| Ratio | 63% | 37% |

**WhatsApp is 1.7x more active than Web Demo**

---

## 👤 User Breakdown

### WhatsApp Users (Last 24h):
1. **4917647009148** (YOU): 10 messages (100%)
   - Questions: Wheat pests, Soybean watering
   - Language: Hindi (Hinglish)
   - Active hours: 21h-23h, 23h-01h UTC
   - Pattern: Repeated questions (testing behavior)

### Web Demo Users (Last 24h):
**Cannot identify individual users** - no tracking enabled

**Estimated**: 
- 15 API calls could be:
  - 1 user with 15 queries, OR
  - 15 different users with 1 query each, OR
  - Any combination in between

**Recommendation**: Enable IP tracking to understand web demo usage patterns

---

## 🔍 Key Insights

### WhatsApp:
1. **Single user activity**: Only you (4917647009148) used WhatsApp in last 24h
2. **Testing pattern**: Repeated questions suggest testing/debugging
3. **Late night activity**: Active around midnight UTC (1am CET)
4. **Hindi queries**: Using Hinglish for agricultural questions

### Web Demo:
1. **Anonymous usage**: No user identification possible
2. **Similar timing**: Peak at same time as WhatsApp (midnight UTC)
3. **Lower volume**: 15 requests vs 26 WhatsApp
4. **Possible correlation**: Could be same user testing both interfaces?

### Overall:
1. **Low traffic**: 41 total requests in 24h (very light usage)
2. **Concentrated activity**: Most traffic in 3-hour window (23h-01h UTC)
3. **Single active WhatsApp user**: You are the only WhatsApp user in last 24h
4. **No visibility on web users**: Need to enable tracking

---

## 🎯 Recommendations

### To Track Web Demo Users:

1. **Enable API Gateway Access Logs**:
```yaml
# In template-week2.yaml
WebChatApi:
  Type: AWS::Serverless::Api
  Properties:
    AccessLogSetting:
      DestinationArn: !GetAtt AccessLogGroup.Arn
      Format: '$context.requestId $context.identity.sourceIp $context.requestTime'
```

2. **Add IP Tracking to Lambda**:
```python
# In src/web-chat/handler.py
def lambda_handler(event, context):
    source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp')
    client_id = event.get('headers', {}).get('x-client-id', 'anonymous')
    
    # Store in DynamoDB
    table.put_item(Item={
        'PK': f'WEB_CHAT#{source_ip}',
        'SK': f'SESSION#{timestamp}',
        'ip_address': source_ip,
        'client_id': client_id,
        'query': query,
        'timestamp': timestamp
    })
```

3. **Add Client-Side Tracking**:
```javascript
// In web demo HTML
const clientId = localStorage.getItem('clientId') || generateUUID();
localStorage.setItem('clientId', clientId);

fetch('/chat', {
  headers: {
    'X-Client-Id': clientId
  }
});
```

---

## 📊 Summary Card

```
┌─────────────────────────────────────┐
│   Last 24 Hours Traffic Summary     │
│      (April 22-23, 2026)            │
├─────────────────────────────────────┤
│ WhatsApp Requests:           26     │
│ Web Demo Requests:           15     │
│ Total Requests:              41     │
│                                     │
│ WhatsApp Users:               1     │
│   └─ 4917647009148 (YOU):   10 msg │
│                                     │
│ Web Demo Users:          Unknown    │
│   └─ No tracking enabled            │
│                                     │
│ Peak Hour:              00h UTC     │
│   └─ WhatsApp: 16, Web: 6          │
│                                     │
│ Your Questions:                     │
│   └─ Wheat pests (4x)               │
│   └─ Soybean watering (6x)          │
└─────────────────────────────────────┘
```

---

## 🚨 Important Note

**You are the only active WhatsApp user in the last 24 hours.**

All 10 WhatsApp messages came from your number (4917647009148). The other 6 registered users have not sent any messages in the last 24 hours.

For web demo, we cannot identify users without enabling tracking. The 15 requests could be from you testing, or from other anonymous users.

---

*To get detailed web demo user analytics, enable API Gateway Access Logs and add IP/client tracking to the Lambda handler.*
