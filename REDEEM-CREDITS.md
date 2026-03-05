# How to Redeem Your Competition Credits

## You Have $200 AWS Credits!

**Credit Code**: `PC28JCENFLC4ZKR`

## Step-by-Step Redemption

### 1. Login to AWS Console
```
https://console.aws.amazon.com/
```

### 2. Go to Billing & Credits
```
https://console.aws.amazon.com/billing/home#/credits
```

Or navigate:
- Click your account name (top right)
- Click "Billing and Cost Management"
- Click "Credits" in left sidebar

### 3. Redeem Credit Code

1. Click **"Redeem credit"** button (orange button)
2. Enter code: `PC28JCENFLC4ZKR`
3. Click **"Redeem credit"**
4. Wait for confirmation message

### 4. Verify Credits Applied

You should see:
```
Credit Details:
- Amount: $200.00
- Status: Active
- Expiration: [Date - usually 12 months]
- Remaining: $200.00
```

## How to Check Credit Balance

### Via AWS Console
```
https://console.aws.amazon.com/billing/home#/credits
```

### Via AWS CLI
```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-02-01,End=2026-02-28 \
  --granularity MONTHLY \
  --metrics UnblendedCost
```

## Credit Usage Priority

AWS automatically uses credits in this order:

```
1. Free Tier (automatic)
   ↓
2. AWS Credits ($200)
   ↓
3. Your credit card (only if credits exhausted)
```

**You won't be charged** until you use all $200 credits!

## Expected Credit Usage for Competition

| Week | Services | Cost | Credits Remaining |
|------|----------|------|-------------------|
| Week 1 | DynamoDB + S3 + OpenSearch + Bedrock | $25 | $175 |
| Week 2 | + WhatsApp + Step Functions | $25 | $150 |
| Week 3 | + Transcribe + Polly + Vision | $30 | $120 |
| Week 4 | Testing + Demo | $30 | $90 |
| **Total** | | **$110** | **$90 remaining** |

**You have enough credits for the entire competition + extra!**

## Set Up Billing Alerts (Recommended)

Even with credits, set up alerts to monitor usage:

### Via AWS Console

1. Go to: https://console.aws.amazon.com/billing/home#/preferences
2. Check "Receive Billing Alerts"
3. Click "Save preferences"
4. Go to CloudWatch: https://console.aws.amazon.com/cloudwatch/
5. Click "Alarms" → "Create alarm"
6. Set thresholds:
   - Alert at $50 (25% of credits)
   - Alert at $100 (50% of credits)
   - Alert at $150 (75% of credits)

### Via AWS CLI

```bash
# Enable billing alerts
aws ce put-cost-anomaly-monitor \
  --monitor '{
    "MonitorName": "Competition Budget Monitor",
    "MonitorType": "DIMENSIONAL",
    "MonitorDimension": "SERVICE"
  }'

# Create budget
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget '{
    "BudgetName": "Competition Budget",
    "BudgetLimit": {
      "Amount": "200",
      "Unit": "USD"
    },
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }'
```

## Troubleshooting

### Issue: "Invalid credit code"

**Solutions**:
1. Check you copied the code exactly: `PC28JCENFLC4ZKR`
2. Make sure there are no extra spaces
3. Try again in a different browser
4. Contact AWS Support if still failing

### Issue: "Credit already redeemed"

**Solution**: 
- Check if credits are already in your account
- Go to: https://console.aws.amazon.com/billing/home#/credits
- Look for $200 credit

### Issue: "Credit not showing up"

**Solution**:
- Wait 5-10 minutes for processing
- Refresh the page
- Check "Credit history" tab
- Contact AWS Support if not appearing after 1 hour

### Issue: "Credit expired"

**Solution**:
- Competition credits are usually valid for 12 months
- Check expiration date in credits page
- Contact competition organizers if expired prematurely

## AWS Support for Credit Issues

If you have problems redeeming credits:

1. **AWS Support Center**: https://support.aws.amazon.com/
2. **Kiro Billing Support**: https://support.aws.amazon.com/#/contacts/kiro
3. **Competition Organizers**: Email from your competition notification

## After Redeeming Credits

### 1. Verify Credits Active
```bash
# Check credit balance
aws ce get-cost-and-usage \
  --time-period Start=2026-02-01,End=2026-02-28 \
  --granularity MONTHLY \
  --metrics UnblendedCost
```

### 2. Deploy Week 1
```bash
# Now you can deploy without cost concerns!
bash scripts/setup-week1.sh agrinexus-dev us-east-1
```

### 3. Monitor Usage
```bash
# Check daily costs
aws ce get-cost-and-usage \
  --time-period Start=2026-02-14,End=2026-02-15 \
  --granularity DAILY \
  --metrics UnblendedCost
```

## Credit Usage Best Practices

1. **Deploy only when needed**
   - Don't leave resources running 24/7 during development
   - Delete stack when not actively testing

2. **Monitor daily**
   - Check billing dashboard daily
   - Watch for unexpected charges

3. **Use free tier first**
   - DynamoDB: 25 GB free
   - Lambda: 1M requests free
   - S3: 5 GB free

4. **Optimize costs**
   - Use smallest instance sizes
   - Delete unused resources
   - Implement caching

## Summary

✓ You have $200 AWS credits
✓ Code: `PC28JCENFLC4ZKR`
✓ Redeem at: https://console.aws.amazon.com/billing/home#/credits
✓ Enough for entire competition ($110 needed)
✓ No credit card charges until credits exhausted

**You're ready to deploy without cost concerns!**
