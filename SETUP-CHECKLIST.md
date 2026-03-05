# Setup Checklist - Follow in Order

## Pre-Deployment Checklist

### 1. Install Tools
- [ ] Install Homebrew: `brew --version`
- [ ] Install SAM CLI: `sam --version`
- [ ] Install AWS CLI: `aws --version`
- [ ] Install Python packages: `pip3 install boto3 pytest`

### 2. AWS Account Setup
- [ ] Have AWS account (or create one at https://aws.amazon.com/)
- [ ] Login to AWS Console: https://console.aws.amazon.com/
- [ ] Create IAM access keys (save the CSV file!)
- [ ] Run `aws configure` and enter credentials
- [ ] Test credentials: `aws sts get-caller-identity`

### 3. Enable Bedrock Models
- [ ] Go to Bedrock Console: https://console.aws.amazon.com/bedrock/
- [ ] Switch to **us-east-1** region (top right)
- [ ] Click "Model access" → "Manage model access"
- [ ] Enable **Claude 3 Sonnet**
- [ ] Enable **Titan Embeddings G1 - Text**
- [ ] Wait for "Access granted" status (usually instant)

### 4. Validate Setup
- [ ] Run: `sam validate --lint`
- [ ] Run: `sam build`
- [ ] Check: No errors in output

### 5. Understand Costs
- [ ] Read cost breakdown (~$25/month)
- [ ] Decide if you want to proceed
- [ ] Know how to delete stack to stop charges

## Deployment Checklist

### 6. Deploy Infrastructure
- [ ] Run: `bash scripts/setup-week1.sh agrinexus-dev us-east-1`
- [ ] Wait 15-20 minutes
- [ ] Watch for errors in output

### 7. Verify Deployment
- [ ] Check CloudFormation stack status: `aws cloudformation describe-stacks --stack-name agrinexus-dev`
- [ ] Verify DynamoDB table exists: `aws dynamodb list-tables`
- [ ] Verify S3 bucket exists: `aws s3 ls`
- [ ] Check KB ingestion status (should be COMPLETE)

### 8. Run Tests
- [ ] Tests should run automatically at end of setup script
- [ ] Verify 20/20 golden questions passed
- [ ] Check guardrail tests passed

### 9. Monitor Costs
- [ ] Go to AWS Billing Dashboard
- [ ] Check current month costs
- [ ] Set up billing alarm at $75

## Post-Deployment Checklist

### 10. Test Manually (Optional)
- [ ] Run: `python3 test_rag_example.py`
- [ ] Test a Hindi question manually
- [ ] Verify response includes citations

### 11. Review Logs
- [ ] Check CloudWatch Logs
- [ ] Look for any errors or warnings

### 12. Document Your Setup
- [ ] Note your Knowledge Base ID
- [ ] Note your stack name
- [ ] Save any important outputs

## Cleanup Checklist (When Done Testing)

### 13. Delete Resources to Stop Charges
- [ ] Run: `aws cloudformation delete-stack --stack-name agrinexus-dev`
- [ ] Wait for deletion to complete (~5 min)
- [ ] Verify stack is deleted: `aws cloudformation describe-stacks --stack-name agrinexus-dev`
- [ ] Check S3 bucket is deleted
- [ ] Verify no charges in Billing Dashboard

---

## Quick Commands Reference

```bash
# Install everything
brew tap aws/tap
brew install aws-sam-cli awscli
pip3 install boto3 pytest

# Configure AWS
aws configure

# Validate
sam validate --lint
sam build

# Deploy
bash scripts/setup-week1.sh agrinexus-dev us-east-1

# Test manually
python3 test_rag_example.py

# Delete (stop charges)
aws cloudformation delete-stack --stack-name agrinexus-dev
```

---

## Troubleshooting Quick Fixes

**"sam: command not found"**
→ Run: `brew install aws-sam-cli`

**"Access Denied"**
→ Check: `aws sts get-caller-identity`
→ Fix: Run `aws configure` again

**"Bedrock model not available"**
→ Go to: https://console.aws.amazon.com/bedrock/
→ Enable: Claude 3 Sonnet + Titan Embeddings

**"Region not supported"**
→ Use: `us-east-1` (Virginia)

**"Stack already exists"**
→ Delete first: `aws cloudformation delete-stack --stack-name agrinexus-dev`

---

## Current Status

Mark your progress:
- [ ] Tools installed
- [ ] AWS configured
- [ ] Bedrock enabled
- [ ] Validation passed
- [ ] Infrastructure deployed
- [ ] Tests passed
- [ ] Ready for Week 2

---

## Need Help?

See detailed instructions in:
- `SETUP-GUIDE.md` - Complete step-by-step guide
- `INSTALL-PREREQUISITES.md` - Installation details
- `DEPLOYMENT.md` - Deployment troubleshooting
- `README.md` - Project overview
