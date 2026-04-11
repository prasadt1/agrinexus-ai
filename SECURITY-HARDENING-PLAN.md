# AgriNexus AI - Security Hardening Plan

**Status**: DRAFT - Implementation After Demo Recording  
**Created**: April 6, 2026  
**Priority**: Implement before production launch  
**Visibility**: LOCAL ONLY - DO NOT COMMIT TO GIT

---

## Executive Summary

Current security posture is **good for demo/competition** but needs hardening before production. Main gaps: rate limiting, cost controls, and input validation. This document outlines specific implementation steps to address all identified vulnerabilities.

**Timeline**: Implement after demo video is recorded (current working version preserved).

---

## Current Security Assessment

### ✅ What's Working Well

| Area | Implementation | Status |
|------|----------------|--------|
| Webhook Authentication | HMAC-SHA256 signature verification with timing-safe comparison | ✅ Strong |
| Secrets Management | All credentials in AWS Secrets Manager | ✅ Strong |
| Idempotency | WAMID deduplication in DynamoDB | ✅ Good |
| IAM Policies | Function-specific least-privilege policies | ✅ Good |
| Encryption at Rest | DynamoDB + S3 with AWS-managed keys | ✅ Good |
| Encryption in Transit | TLS 1.2+ for all AWS services | ✅ Good |
| PII Handling | Phone number redaction in logs | ✅ Good |
| Domain Restrictions | Bedrock guardrails + farming-focused prompts | ✅ Good |
| S3 Security | Block Public Access enabled | ✅ Good |

### ⚠️ Gaps to Address

| Area | Current State | Risk Level | Priority |
|------|---------------|------------|----------|
| API Gateway Rate Limiting | None | HIGH | P1 |
| Cost Controls | No billing alarms | HIGH | P1 |
| Input Validation | Minimal | MEDIUM | P1 |
| Per-User Quotas | None | MEDIUM | P2 |
| Dependency Scanning | Manual | MEDIUM | P2 |
| WAF Protection | None | LOW | P3 |
| Penetration Testing | Not done | LOW | P3 |

---

## Implementation Plan

### Phase 1: Critical Security (Before Production)

**Timeline**: 1-2 days after demo recording  
**Goal**: Prevent cost explosion and basic abuse

#### 1.1 API Gateway Rate Limiting

**File**: `template-week2.yaml`

**Add Usage Plan:**
```yaml
  # ============================================================================
  # API Gateway Usage Plan for Rate Limiting
  # ============================================================================
  WebhookUsagePlan:
    Type: AWS::ApiGateway::UsagePlan
    Properties:
      UsagePlanName: !Sub agrinexus-webhook-throttle-${Environment}
      Description: Rate limiting for WhatsApp webhook
      Throttle:
        BurstLimit: 100      # Max concurrent requests
        RateLimit: 50        # Requests per second
      Quota:
        Limit: 100000        # Max 100K requests per month
        Period: MONTH
      ApiStages:
        - ApiId: !Ref WhatsAppApi
          Stage: !Ref Environment

  WebhookUsagePlanKey:
    Type: AWS::ApiGateway::UsagePlanKey
    Properties:
      KeyId: !Ref WebhookApiKey
      KeyType: API_KEY
      UsagePlanId: !Ref WebhookUsagePlan

  WebhookApiKey:
    Type: AWS::ApiGateway::ApiKey
    Properties:
      Name: !Sub agrinexus-webhook-key-${Environment}
      Description: API key for WhatsApp webhook
      Enabled: true
```

**Testing**:
```bash
# Test rate limit
for i in {1..60}; do
  curl -X POST https://your-webhook-url/webhook \
    -H "x-api-key: YOUR_KEY" &
done
# Should see 429 errors after hitting limit
```

**Estimated effort**: 2 hours  
**Cost impact**: $0 (Usage Plans are free)

---

#### 1.2 CloudWatch Billing Alarms

**File**: `template-week2.yaml`

**Add Billing Alarms:**
```yaml
  # ============================================================================
  # Cost Control: Billing Alarms
  # ============================================================================
  BillingAlarmTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub agrinexus-billing-alerts-${Environment}
      DisplayName: AgriNexus Billing Alerts
      Subscription:
        - Endpoint: YOUR_EMAIL@example.com  # REPLACE WITH ACTUAL EMAIL
          Protocol: email

  BillingAlarm50:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub agrinexus-cost-50-${Environment}
      AlarmDescription: Alert when estimated charges exceed $50
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Period: 21600  # 6 hours
      EvaluationPeriods: 1
      Threshold: 50
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref BillingAlarmTopic
      Dimensions:
        - Name: Currency
          Value: USD

  BillingAlarm100:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub agrinexus-cost-100-${Environment}
      AlarmDescription: Alert when estimated charges exceed $100
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Period: 21600
      EvaluationPeriods: 1
      Threshold: 100
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref BillingAlarmTopic
      Dimensions:
        - Name: Currency
          Value: USD

  BillingAlarm200:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub agrinexus-cost-200-${Environment}
      AlarmDescription: CRITICAL - Alert when estimated charges exceed $200
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Period: 21600
      EvaluationPeriods: 1
      Threshold: 200
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref BillingAlarmTopic
      Dimensions:
        - Name: Currency
          Value: USD
```

**Note**: Billing metrics are only available in us-east-1. If deploying to other regions, create alarms separately.

**Estimated effort**: 1 hour  
**Cost impact**: $0.10/month per alarm

---

#### 1.3 Input Validation

**File**: `src/webhook/handler.py`

**Add validation module:**
```python
# Add to top of handler.py
MAX_TEXT_LENGTH = 4000  # WhatsApp limit is 4096
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_AUDIO_SIZE = 16 * 1024 * 1024  # 16MB (WhatsApp limit)
MAX_AUDIO_DURATION = 120  # 2 minutes
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_AUDIO_TYPES = {'audio/ogg', 'audio/mpeg', 'audio/amr'}

def validate_message(message: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate incoming message for size, type, and content limits.
    Returns (is_valid, error_message)
    """
    msg_type = message.get('type')
    
    if msg_type == 'text':
        text = message.get('text', {}).get('body', '')
        if len(text) > MAX_TEXT_LENGTH:
            return False, f"Text message too long ({len(text)} > {MAX_TEXT_LENGTH})"
    
    elif msg_type == 'image':
        image = message.get('image', {})
        file_size = image.get('file_size', 0)
        mime_type = image.get('mime_type', '')
        
        if file_size > MAX_IMAGE_SIZE:
            return False, f"Image too large ({file_size} > {MAX_IMAGE_SIZE})"
        if mime_type not in ALLOWED_IMAGE_TYPES:
            return False, f"Invalid image type: {mime_type}"
    
    elif msg_type == 'audio':
        audio = message.get('audio', {})
        file_size = audio.get('file_size', 0)
        mime_type = audio.get('mime_type', '')
        
        if file_size > MAX_AUDIO_SIZE:
            return False, f"Audio too large ({file_size} > {MAX_AUDIO_SIZE})"
        if mime_type not in ALLOWED_AUDIO_TYPES:
            return False, f"Invalid audio type: {mime_type}"
    
    return True, ""

# In lambda_handler, before processing:
is_valid, error_msg = validate_message(message)
if not is_valid:
    logger.warning(f"Invalid message rejected: {error_msg}")
    # Optionally send error message to user
    continue
```

**Testing**:
- Send very long text message (>4000 chars)
- Send large image (>5MB)
- Send long audio (>2 min)

**Estimated effort**: 3 hours  
**Cost impact**: $0

---

### Phase 2: Enhanced Security (Week After Demo)

**Timeline**: 3-5 days  
**Goal**: Per-user quotas and dependency management

#### 2.1 Per-User Quotas

**File**: `src/webhook/handler.py`

**Add quota tracking:**
```python
# New module: src/common-layer/python/common/quotas.py
import time
from typing import Tuple
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

class QuotaManager:
    def __init__(self, table_name: str):
        self.table = dynamodb.Table(table_name)
        self.daily_message_limit = 100
        self.daily_voice_limit = 20
        self.daily_image_limit = 10
    
    def check_quota(self, user_id: str, message_type: str) -> Tuple[bool, str]:
        """
        Check if user has quota remaining for this message type.
        Returns (allowed, reason)
        """
        today = time.strftime('%Y-%m-%d')
        quota_key = f"QUOTA#{user_id}#{today}"
        
        try:
            response = self.table.get_item(
                Key={'PK': quota_key, 'SK': 'USAGE'}
            )
            
            usage = response.get('Item', {})
            messages = int(usage.get('messages', 0))
            voice = int(usage.get('voice', 0))
            images = int(usage.get('images', 0))
            
            # Check limits
            if message_type == 'text' and messages >= self.daily_message_limit:
                return False, f"Daily message limit reached ({self.daily_message_limit})"
            elif message_type == 'audio' and voice >= self.daily_voice_limit:
                return False, f"Daily voice limit reached ({self.daily_voice_limit})"
            elif message_type == 'image' and images >= self.daily_image_limit:
                return False, f"Daily image limit reached ({self.daily_image_limit})"
            
            return True, ""
        
        except Exception as e:
            logger.error(f"Quota check failed: {e}")
            return True, ""  # Fail open to avoid blocking legitimate users
    
    def increment_quota(self, user_id: str, message_type: str):
        """Increment usage counter for user"""
        today = time.strftime('%Y-%m-%d')
        quota_key = f"QUOTA#{user_id}#{today}"
        ttl = int(time.time()) + (7 * 24 * 3600)  # 7 days
        
        update_expr = "ADD messages :one"
        if message_type == 'audio':
            update_expr = "ADD voice :one"
        elif message_type == 'image':
            update_expr = "ADD images :one"
        
        self.table.update_item(
            Key={'PK': quota_key, 'SK': 'USAGE'},
            UpdateExpression=f"{update_expr} SET #ttl = :ttl",
            ExpressionAttributeNames={'#ttl': 'TTL'},
            ExpressionAttributeValues={
                ':one': Decimal(1),
                ':ttl': Decimal(ttl)
            }
        )
```

**Estimated effort**: 4 hours  
**Cost impact**: Minimal DynamoDB reads/writes

---

#### 2.2 Dependency Vulnerability Scanning

**File**: `.github/workflows/security-scan.yml` (new)

```yaml
name: Security Scan

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install safety
        run: pip install safety
      
      - name: Scan dependencies
        run: |
          find src -name requirements.txt -exec safety check -r {} \;
      
      - name: Bandit security scan
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: bandit-report.json
```

**Manual check (run now):**
```bash
pip install safety bandit
find src -name requirements.txt -exec safety check -r {} \;
bandit -r src/
```

**Estimated effort**: 2 hours  
**Cost impact**: $0 (GitHub Actions free tier)

---

### Phase 3: Advanced Security (Pre-Production)

**Timeline**: 1-2 weeks before production launch  
**Goal**: WAF, penetration testing, audit

#### 3.1 AWS WAF Integration

**File**: `template-week2.yaml`

**Add WAF:**
```yaml
  # ============================================================================
  # AWS WAF for Advanced Protection
  # ============================================================================
  WebhookWAF:
    Type: AWS::WAFv2::WebACL
    Properties:
      Name: !Sub agrinexus-webhook-waf-${Environment}
      Scope: REGIONAL
      DefaultAction:
        Allow: {}
      Rules:
        # Rate limiting
        - Name: RateLimitRule
          Priority: 1
          Statement:
            RateBasedStatement:
              Limit: 2000  # 2000 requests per 5 minutes per IP
              AggregateKeyType: IP
          Action:
            Block:
              CustomResponse:
                ResponseCode: 429
          VisibilityConfig:
            SampledRequestsEnabled: true
            CloudWatchMetricsEnabled: true
            MetricName: RateLimitRule
        
        # Block known bad IPs (AWS managed rule)
        - Name: AWSManagedRulesAmazonIpReputationList
          Priority: 2
          OverrideAction:
            None: {}
          Statement:
            ManagedRuleGroupStatement:
              VendorName: AWS
              Name: AWSManagedRulesAmazonIpReputationList
          VisibilityConfig:
            SampledRequestsEnabled: true
            CloudWatchMetricsEnabled: true
            MetricName: AWSIPReputation
        
        # Block common attacks
        - Name: AWSManagedRulesCommonRuleSet
          Priority: 3
          OverrideAction:
            None: {}
          Statement:
            ManagedRuleGroupStatement:
              VendorName: AWS
              Name: AWSManagedRulesCommonRuleSet
          VisibilityConfig:
            SampledRequestsEnabled: true
            CloudWatchMetricsEnabled: true
            MetricName: AWSCommonRules
      
      VisibilityConfig:
        SampledRequestsEnabled: true
        CloudWatchMetricsEnabled: true
        MetricName: WebhookWAF

  WebhookWAFAssociation:
    Type: AWS::WAFv2::WebACLAssociation
    Properties:
      ResourceArn: !Sub arn:aws:apigateway:${AWS::Region}::/restapis/${WhatsAppApi}/stages/${Environment}
      WebACLArn: !GetAtt WebhookWAF.Arn
```

**Estimated effort**: 3 hours  
**Cost impact**: ~$5-10/month (WAF charges)

---

#### 3.2 Penetration Testing

**Scope**:
- API Gateway webhook endpoint
- WhatsApp message injection
- Cost explosion attacks
- Data exfiltration attempts

**Recommended tools**:
- OWASP ZAP
- Burp Suite
- Custom scripts for WhatsApp-specific attacks

**Checklist**:
- [ ] Signature bypass attempts
- [ ] Replay attack testing
- [ ] Rate limit validation
- [ ] Input fuzzing (oversized, malformed)
- [ ] SQL injection (if any raw queries)
- [ ] Prompt injection attacks
- [ ] Cost explosion scenarios

**Estimated effort**: 1-2 days  
**Cost impact**: $0 (self-testing) or $500-2000 (professional)

---

#### 3.3 Security Audit

**Create**: `SECURITY.md` (public, for GitHub)

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

Please report security vulnerabilities to: security@agrinexus.ai

**Do not** open public GitHub issues for security vulnerabilities.

We will respond within 48 hours and provide a fix timeline.

## Security Measures

- Webhook signature verification (HMAC-SHA256)
- All secrets in AWS Secrets Manager
- Rate limiting at API Gateway
- Input validation and sanitization
- Encryption at rest and in transit
- Regular dependency scanning
- AWS WAF protection

## Responsible Disclosure

We follow responsible disclosure practices and will credit researchers who report vulnerabilities responsibly.
```

**Estimated effort**: 2 hours  
**Cost impact**: $0

---

## IP Protection Strategy

### License Recommendation

**Current**: Likely MIT (permissive)  
**Recommended**: **AGPL-3.0** for stronger protection

**Why AGPL-3.0:**
- Forces anyone using your code in a network service to open-source their modifications
- Prevents competitors from taking your code and closing it
- Still allows commercial use with proper attribution
- Common for SaaS products

**How to change:**
1. Replace LICENSE file with AGPL-3.0 text
2. Add copyright headers to all source files
3. Update README.md to mention license

**File**: `LICENSE`
```
GNU AFFERO GENERAL PUBLIC LICENSE
Version 3, 19 November 2007
[Full AGPL-3.0 text]
```

### What to Keep Private

**Move to private repo/modules:**
- Production prompt engineering
- Curated knowledge base content
- Advanced nudge algorithms
- Customer-specific customizations
- Cost optimization secrets
- Partnership agreements

**Keep public:**
- Reference architecture
- Basic integration code
- Documentation
- Sample prompts

---

## Testing Plan

### Security Test Suite

**File**: `tests/test_security.py` (new)

```python
import pytest
import hmac
import hashlib
import json

def test_webhook_signature_validation():
    """Test that invalid signatures are rejected"""
    # Test with wrong signature
    # Test with missing signature
    # Test with timing attack
    pass

def test_rate_limiting():
    """Test that rate limits are enforced"""
    # Send 100 requests rapidly
    # Verify 429 responses
    pass

def test_input_validation():
    """Test that oversized inputs are rejected"""
    # Test long text
    # Test large files
    # Test invalid MIME types
    pass

def test_quota_enforcement():
    """Test per-user quotas"""
    # Send 101 messages from same user
    # Verify quota exceeded message
    pass

def test_cost_controls():
    """Test that cost alarms trigger"""
    # Mock high usage
    # Verify alarm state
    pass
```

---

## Deployment Checklist

### Pre-Demo (Current State)
- [x] Webhook signature verification
- [x] Secrets in Secrets Manager
- [x] Basic IAM policies
- [x] Encryption enabled
- [ ] Document security gaps (this file)

### Post-Demo (Phase 1)
- [ ] Deploy API Gateway rate limiting
- [ ] Deploy billing alarms
- [ ] Add input validation
- [ ] Test all security controls
- [ ] Update architecture.md

### Pre-Production (Phase 2 + 3)
- [ ] Implement per-user quotas
- [ ] Set up dependency scanning
- [ ] Deploy WAF
- [ ] Run penetration tests
- [ ] Security audit
- [ ] Update LICENSE to AGPL-3.0
- [ ] Create SECURITY.md
- [ ] Final security review

---

## Cost Impact Summary

| Item | Monthly Cost | One-Time Effort |
|------|--------------|-----------------|
| API Gateway Usage Plan | $0 | 2 hours |
| Billing Alarms | $0.30 | 1 hour |
| Input Validation | $0 | 3 hours |
| Per-User Quotas | ~$1 | 4 hours |
| Dependency Scanning | $0 | 2 hours |
| AWS WAF | $5-10 | 3 hours |
| Penetration Testing | $0-2000 | 1-2 days |
| **Total** | **~$6-11/month** | **~20 hours** |

**ROI**: Prevents potential $1000+ cost explosion from abuse.

---

## References

- [AWS WAF Best Practices](https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html)
- [API Gateway Throttling](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [WhatsApp Security Best Practices](https://developers.facebook.com/docs/whatsapp/security)

---

## Notes

- This document is LOCAL ONLY - do not commit to git
- Implement after demo video is recorded
- Test each change in dev environment first
- Monitor CloudWatch metrics after each deployment
- Keep this document updated as you implement

---

**Last Updated**: April 6, 2026  
**Next Review**: After demo recording
