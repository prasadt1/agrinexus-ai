# Infrastructure Capacity Analysis for Public Demo

**Date:** April 17, 2026  
**Status:** Ready for public demo with recommended monitoring

## Executive Summary

The AgriNexus AI infrastructure is **ready to handle public demo traffic** with current configurations. The system uses serverless AWS services that auto-scale, combined with multi-layer rate limiting to prevent abuse. Key findings:

- ✅ **Rate limits**: Adequate protection at webhook (25 msg/hour/user) and web demo (5 queries/hour/IP)
- ✅ **Lambda concurrency**: Default 1000 concurrent executions per region (sufficient for demo)
- ✅ **DynamoDB**: On-demand capacity auto-scales
- ✅ **Bedrock**: Throttling limits are service-managed
- ⚠️ **Monitoring**: Recommend CloudWatch alarms for cost and error rates

---

## 1. Current Rate Limits

### 1.1 WhatsApp Webhook
**Configuration** (`template.yaml`):
```yaml
RATE_LIMIT_MESSAGES: "25"  # Max messages per user per hour
RATE_LIMIT_WINDOW_SECONDS: "3600"  # 1 hour window
```

**Implementation**: Per-user rate limiting in `src/webhook/handler.py`
- Tracks message count using DynamoDB `MSG#` sort keys
- Enforces limit before SQS enqueue (prevents wasted processing)
- Returns 429 status when limit exceeded

**Capacity**: Can handle **unlimited concurrent users**, each limited to 25 messages/hour

### 1.2 Web Demo API
**Configuration** (`src/web-chat/handler.py`):
```python
WEB_RATE_LIMIT: "5"  # 5 queries per hour per IP
WEB_RATE_LIMIT_WINDOW: "3600"  # 1 hour
```

**Implementation**: Dual-identifier rate limiting (IP + client_id)
- Tracks both IP address and anonymous client_id
- Uses DynamoDB with atomic increments
- Pre-checks both identifiers before incrementing (prevents partial increments)

**Edge Protection** (`template.yaml`):
```yaml
# API Gateway throttling
ThrottlingRateLimit: 2  # 2 req/sec
ThrottlingBurstLimit: 5

# WAF rate limiting
Limit: 300  # 300 requests / 5 minutes per IP
```

**Capacity**: 
- API Gateway: 2 req/sec sustained, 5 burst = **7,200 requests/hour** max
- WAF: 300 req/5min = **3,600 requests/hour per IP**
- Application: 5 queries/hour per IP (strictest limit)

---

## 2. Lambda Capacity

### 2.1 Concurrency Limits
**AWS Default**: 1,000 concurrent executions per region (us-east-1)

**Current Functions** (11 total):
| Function | Timeout | Memory | Trigger | Expected Concurrency |
|----------|---------|--------|---------|---------------------|
| WebhookHandler | 30s | 256MB | API Gateway | Low (fast validation) |
| MessageProcessor | 60s | 512MB | SQS | Medium (RAG queries) |
| VoiceProcessor | 90s | 512MB | SQS | Low (voice is allowlisted) |
| WebChatHandler | 60s | 512MB | API Gateway | Medium (public demo) |
| NudgeSender | 60s | 512MB | Step Functions | Low (scheduled) |
| ReminderSender | 30s | 512MB | EventBridge | Low (scheduled) |
| ResponseDetector | 30s | 512MB | DynamoDB Streams | Low (batch processing) |
| WeatherPoller | 60s | 256MB | EventBridge (6h) | Very Low (1 every 6h) |
| DLQHandler | 30s | 512MB | SQS DLQ | Very Low (errors only) |

**Worst-Case Scenario** (public demo spike):
- 100 concurrent web chat queries (60s each) = 100 concurrent executions
- 50 concurrent webhook requests (30s each) = 50 concurrent executions
- 20 concurrent message processors (60s each) = 20 concurrent executions
- **Total**: ~170 concurrent executions (well under 1,000 limit)

**Recommendation**: No reserved concurrency needed for demo. Monitor CloudWatch metrics.

### 2.2 Cold Start Impact
**First Request Latency**:
- Webhook: ~1-3s (lightweight, minimal dependencies)
- Processor: ~3-5s (imports Bedrock SDK, common layer)
- Web Chat: ~3-5s (similar to processor)

**Mitigation**: 
- Common layer reduces cold start time (shared dependencies)
- Provisioned concurrency not needed for demo (cost vs benefit)
- Users expect some latency in demo environment

---

## 3. DynamoDB Capacity

### 3.1 Current Configuration
**Mode**: On-demand (auto-scaling)
- No capacity planning required
- Scales automatically to handle traffic
- Pay per request (no idle cost)

### 3.2 Access Patterns
| Pattern | Frequency | Type |
|---------|-----------|------|
| User profile lookup | Per message | Read |
| Rate limit check | Per request | Read + Write |
| Message storage | Per message | Write |
| Nudge status update | Per nudge | Write |
| DynamoDB Streams | Continuous | Read |

**Estimated Load** (100 concurrent users):
- Reads: ~200/sec (profile + rate limit checks)
- Writes: ~100/sec (messages + rate limits)
- **Total**: ~300 RCU/WCU per second

**DynamoDB Limits**:
- On-demand: 40,000 RCU/WCU per table per second (default)
- Can request increase to millions if needed

**Capacity**: Current on-demand mode can handle **10,000+ concurrent users** without configuration changes.

---

## 4. Bedrock Capacity

### 4.1 Service Quotas
**Claude 3 Sonnet** (us-east-1):
- Tokens per minute: 200,000 (default)
- Requests per minute: Varies by account

**Knowledge Base**:
- RetrieveAndGenerate calls: Service-managed throttling
- No published hard limits (scales with account usage)

### 4.2 Expected Usage
**Per Query**:
- Input tokens: ~1,000 (prompt + context)
- Output tokens: ~500 (response)
- Total: ~1,500 tokens per query

**Capacity Calculation**:
- 200,000 tokens/min ÷ 1,500 tokens/query = **~133 queries/minute**
- = **~8,000 queries/hour**

**Demo Rate Limits**:
- Web demo: 5 queries/hour per IP
- WhatsApp: 25 messages/hour per user
- Even with 1,000 concurrent users, rate limits prevent Bedrock throttling

**Recommendation**: Monitor Bedrock throttling metrics. Request quota increase if needed (typically approved within 24 hours).

---

## 5. Cost Projections for Public Demo

### 5.1 Baseline Costs (Current)
**1,000 farmers** (private pilot): ~$53/month
- Bedrock: $32
- Transcribe: $12
- Polly: $2
- Vision: $5
- S3 Vectors: $1.30
- DynamoDB: $0.90
- Other: $0 (free tier)

### 5.2 Public Demo Scenario
**Assumptions**:
- 500 web demo users/day (5 queries each) = 2,500 queries/day
- 100 WhatsApp users/day (10 messages each) = 1,000 messages/day
- Total: 3,500 queries/day = 105,000 queries/month

**Projected Costs**:
| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Bedrock Claude 3 Sonnet | 105K queries (105M input + 52.5M output tokens) | ~$1,120 |
| S3 Vectors (Knowledge Base) | Storage + 105K queries | ~$45 |
| DynamoDB (on-demand) | 3.5M reads, 1.75M writes | ~$32 |
| Lambda | 105K invocations, 60s avg | ~$5 |
| API Gateway | 105K requests | ~$0.35 |
| WAF | 105K requests | ~$0.60 |
| **Total** | | **~$1,203/month** |

**Cost per Query**: $1,203 ÷ 105,000 = **$0.011 per query**

### 5.3 Cost Controls
**Existing**:
- ✅ Rate limits (5-10 queries/hour per user)
- ✅ WAF protection (300 req/5min per IP)
- ✅ API Gateway throttling (2 req/sec)
- ✅ CloudWatch alarm ($20/day threshold)

**Recommended**:
- Set Bedrock budget alert ($1,500/month)
- Monitor daily spend in Cost Explorer
- Add "kill switch" environment variable to disable demo without redeploy

---

## 6. Monitoring & Alerts

### 6.1 Existing Alarms
**Cost Alarm** (`template.yaml`):
```yaml
CostAlarm:
  Threshold: 20  # Alert if daily cost >= $20
  Period: 86400  # 24 hours
```

**Nudge Workflow Failures**:
```yaml
NudgeWorkflowFailureAlarm:
  Threshold: 1  # Alert on any failure
  Period: 300  # 5 minutes
```

### 6.2 Recommended Additional Alarms

**1. Bedrock Throttling**
```yaml
BedrockThrottlingAlarm:
  MetricName: ThrottledRequests
  Namespace: AWS/Bedrock
  Threshold: 10
  Period: 300  # 5 minutes
```

**2. Lambda Errors**
```yaml
LambdaErrorAlarm:
  MetricName: Errors
  Namespace: AWS/Lambda
  Threshold: 10
  Period: 300  # 5 minutes
```

**3. API Gateway 4xx/5xx**
```yaml
ApiGatewayErrorAlarm:
  MetricName: 4XXError + 5XXError
  Namespace: AWS/ApiGateway
  Threshold: 50
  Period: 300  # 5 minutes
```

**4. DynamoDB Throttling**
```yaml
DynamoDBThrottlingAlarm:
  MetricName: UserErrors
  Namespace: AWS/DynamoDB
  Threshold: 10
  Period: 300  # 5 minutes
```

### 6.3 CloudWatch Dashboard
**Recommended Metrics**:
- Lambda invocations, duration, errors (all functions)
- API Gateway request count, latency, 4xx/5xx
- DynamoDB read/write capacity, throttles
- Bedrock invocations, latency, throttles
- WAF blocked requests
- Estimated charges (daily)

---

## 7. Scaling Recommendations

### 7.1 Immediate Actions (Before Public Launch)
1. ✅ **Rate limits configured** (webhook: 10/hour, web: 5/hour)
2. ✅ **WAF protection enabled** (300 req/5min per IP)
3. ✅ **Cost alarm set** ($20/day threshold)
4. ⚠️ **Add Bedrock budget alert** ($1,500/month)
5. ⚠️ **Create CloudWatch dashboard** (key metrics)
6. ⚠️ **Test load** (simulate 100 concurrent users)

### 7.2 If Traffic Exceeds Expectations
**Symptoms**:
- Bedrock throttling errors
- Lambda concurrency limit reached
- Cost alarm triggered frequently

**Actions**:
1. **Immediate**: Reduce rate limits (5 → 3 queries/hour)
2. **Short-term**: Request Bedrock quota increase (24h approval)
3. **Medium-term**: Add Lambda reserved concurrency for critical functions
4. **Long-term**: Consider caching common queries (ElastiCache)

### 7.3 Cost Optimization
**If costs exceed budget**:
1. Reduce rate limits (5 → 3 queries/hour)
2. Add query caching (reduce Bedrock calls)
3. Implement "demo credits" system (10 free queries per user)
4. Add captcha to reduce bot traffic
5. Temporary "kill switch" to pause demo

---

## 8. Security Considerations

### 8.1 Existing Protections
- ✅ WhatsApp signature verification (HMAC-SHA256)
- ✅ Per-user rate limiting (DynamoDB)
- ✅ WAF rate limiting (IP-based)
- ✅ API Gateway throttling (2 req/sec)
- ✅ Input validation (max 500 chars)
- ✅ PII redaction (common layer)

### 8.2 Potential Risks
**Distributed Abuse** (many IPs):
- Current: WAF limits 300 req/5min per IP
- Risk: Botnet with 1,000 IPs could bypass IP-based limits
- Mitigation: Monitor for unusual patterns, add captcha if needed

**Cost Attack**:
- Current: Rate limits + cost alarm
- Risk: Sustained traffic at rate limit could increase costs
- Mitigation: Budget alerts, kill switch, query caching

**Data Retention**:
- Current: 90-day TTL on messages, 7-day TTL on demo users
- Risk: GDPR compliance for EU users
- Mitigation: Privacy notice in UI, data deletion on request

---

## 9. Load Testing Plan

### 9.1 Test Scenarios
**Scenario 1: Normal Load**
- 50 concurrent users
- 5 queries each over 1 hour
- Expected: No errors, <5s latency

**Scenario 2: Spike Load**
- 200 concurrent users
- 5 queries each over 10 minutes
- Expected: Some throttling, <10s latency

**Scenario 3: Sustained Load**
- 100 concurrent users
- 5 queries/hour for 4 hours
- Expected: No errors, stable latency

### 9.2 Test Tools
**Option 1: Artillery** (recommended)
```yaml
config:
  target: 'https://h4bt24ycdl.execute-api.us-east-1.amazonaws.com/dev'
  phases:
    - duration: 60
      arrivalRate: 10
scenarios:
  - flow:
      - post:
          url: '/chat'
          json:
            message: 'How to control cotton pests?'
            language: 'en'
```

**Option 2: Locust**
```python
from locust import HttpUser, task

class WebChatUser(HttpUser):
    @task
    def query(self):
        self.client.post('/chat', json={
            'message': 'How to control cotton pests?',
            'language': 'en'
        })
```

### 9.3 Success Criteria
- ✅ 99% success rate (< 1% errors)
- ✅ P95 latency < 10 seconds
- ✅ No Lambda throttling
- ✅ No Bedrock throttling
- ✅ Cost within budget ($50/day max)

---

## 10. Conclusion

**Infrastructure Status**: ✅ **READY FOR PUBLIC DEMO**

**Key Strengths**:
- Serverless architecture auto-scales
- Multi-layer rate limiting prevents abuse
- On-demand DynamoDB handles variable load
- Cost controls in place

**Recommended Actions Before Launch**:
1. Add Bedrock budget alert ($1,500/month)
2. Create CloudWatch dashboard (key metrics)
3. Run load test (100 concurrent users)
4. Document "kill switch" procedure
5. Set up daily cost monitoring

**Expected Performance**:
- Can handle 500+ concurrent users
- Rate limits prevent cost overruns
- Latency: 5-10s per query (acceptable for demo)
- Cost: ~$1,200/month for 105K queries

**Monitoring Plan**:
- Daily cost review (Cost Explorer)
- Weekly CloudWatch metrics review
- Monthly capacity planning review
- Immediate alerts for errors/throttling

---

## Appendix A: Emergency Procedures

### A.1 Cost Overrun
**If daily cost exceeds $50**:
1. Check CloudWatch dashboard for spike source
2. Review top Lambda invocations
3. Reduce rate limits (5 → 3 queries/hour)
4. Add temporary "maintenance mode" message

### A.2 Service Throttling
**If Bedrock throttling detected**:
1. Request quota increase (AWS Support)
2. Add query caching (short-term)
3. Reduce rate limits (temporary)
4. Notify users of temporary slowdown

### A.3 Kill Switch
**To disable demo without redeploy**:
```bash
# Option 1: Update Lambda environment variable
aws lambda update-function-configuration \
  --function-name agrinexus-web-chat-dev \
  --environment "Variables={DEMO_ENABLED=false,...}"

# Option 2: Update API Gateway throttling
aws apigateway update-stage \
  --rest-api-id h4bt24ycdl \
  --stage-name dev \
  --patch-operations op=replace,path=/throttle/rateLimit,value=0
```

---

**Document Version**: 1.0  
**Last Updated**: April 17, 2026  
**Next Review**: May 1, 2026 (after 2 weeks of public demo)
