# Security Incident Response - OpenWeatherMap API Key Exposure

## Incident Summary

**Date**: April 6, 2026  
**Severity**: Medium  
**Type**: API Key Exposure in Git History  
**Detected By**: GitGuardian automated scan

## What Happened

The OpenWeatherMap API key was committed to the git repository in multiple files (e.g. SAM config and internal notes). **Do not paste real keys in incident write-ups** — the value was **rotated** and is not reproduced here.

**Redacted reference**: a 32-character hex key was exposed; it was **revoked** on OpenWeatherMap and replaced. Never commit keys even in incident postmortems.

## Impact Assessment

**Risk Level**: Low to Medium
- OpenWeatherMap free tier has rate limits (60 calls/min, 1M calls/month)
- No financial impact (free tier)
- No access to other AWS resources
- No PII or sensitive data exposed
- Key only provides weather data access

**Potential Abuse**:
- Unauthorized weather API calls consuming our quota
- Rate limit exhaustion preventing legitimate use

## Remediation Steps

### 1. Immediate Actions (Completed)

✅ **Rotate API Key**
```bash
# Run the rotation script
./scripts/rotate-weather-api-key.sh
```

✅ **Move to AWS Secrets Manager**
- Created secret: `agrinexus/weather/api-key`
- Updated Lambda to read from Secrets Manager with caching
- Added IAM policy for secretsmanager:GetSecretValue

✅ **Remove from Code**
- Weather Lambda reads the key from **AWS Secrets Manager** (`WEATHER_API_KEY_SECRET`, e.g. `agrinexus/weather/api-key`), not from `samconfig` or template parameters
- Removed plain-text / deploy-parameter key usage from tracked config
- `src/weather/handler.py` uses `get_secret_value` with in-memory cache

### 2. Deployment

```bash
# Build and deploy with new secret-based configuration
sam build -t template-week2.yaml
sam deploy --config-file samconfig-week2.toml
```

### 3. Verification

```bash
# Test weather Lambda still works
aws lambda invoke \
  --function-name agrinexus-weather-dev \
  --payload '{}' \
  response.json

# Check CloudWatch logs for successful API calls
aws logs tail /aws/lambda/agrinexus-weather-dev --follow
```

### 4. Git History Cleanup (Optional)

**Note**: The exposed key is already rotated, so cleaning git history is optional. If you want to remove it from history:

```bash
# WARNING: This rewrites git history - coordinate with team
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch samconfig-week2.toml" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (requires coordination)
git push origin --force --all
```

**Recommendation**: Don't rewrite history. The key is rotated and the new architecture prevents future exposure.

## Prevention Measures

### 1. Secrets Management Policy

✅ **All API keys and secrets MUST be stored in AWS Secrets Manager**
- WhatsApp credentials: ✅ Already in Secrets Manager
- Weather API key: ✅ Moved to Secrets Manager
- Bedrock credentials: ✅ IAM role-based (no keys)

### 2. Git Pre-Commit Hooks

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Check for potential secrets before commit

if git diff --cached | grep -E '(api[_-]?key|secret|password|token).*=.*[a-zA-Z0-9]{20,}'; then
    echo "ERROR: Potential secret detected in commit"
    echo "Please use AWS Secrets Manager instead"
    exit 1
fi
```

### 3. .gitignore Updates

Already configured:
```
samconfig*.toml  # Deployment configs with parameters
.env             # Environment files
*.pem            # Private keys
*.key            # Key files
```

### 4. Documentation Review

Files to sanitize (internal docs, not in public repo):
- `TEST-REPORT.md` - Remove API key reference
- `DEPLOYMENT-STATUS.md` - Remove API key reference
- `READY-FOR-TESTING.md` - Remove API key reference

These are already excluded from git commits (internal planning docs).

## Lessons Learned

1. **Use Secrets Manager from Day 1**: Even for "low-risk" API keys
2. **Never commit secrets to git**: Use environment variables or Secrets Manager
3. **Automated scanning works**: GitGuardian caught this immediately
4. **NoEcho isn't enough**: CloudFormation NoEcho only hides from console, not from git
5. **Free tier != No risk**: Even free API keys should be protected

## New Architecture

```
┌─────────────────┐
│ Weather Lambda  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ AWS Secrets Manager     │
│ agrinexus/weather/      │
│   api-key               │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│ OpenWeatherMap API      │
└─────────────────────────┘
```

**Benefits**:
- Centralized secret management
- Rotation without code changes
- Audit trail (CloudTrail logs GetSecretValue)
- No secrets in git history
- IAM-based access control

## Timeline

- **2026-04-06 14:00**: GitGuardian alert received
- **2026-04-06 14:15**: Incident confirmed, remediation started
- **2026-04-06 14:30**: API key rotated on OpenWeatherMap
- **2026-04-06 14:45**: Secret created in Secrets Manager
- **2026-04-06 15:00**: Code updated to use Secrets Manager
- **2026-04-06 15:15**: Deployed and verified
- **2026-04-06 15:30**: Documentation updated

**Total Resolution Time**: 90 minutes

## Status

✅ **RESOLVED**

- Old API key revoked
- New API key in Secrets Manager
- Code updated and deployed
- Prevention measures in place
- Documentation updated

---

**Prepared by**: Technical Team  
**Reviewed by**: Security Lead  
**Date**: April 6, 2026
