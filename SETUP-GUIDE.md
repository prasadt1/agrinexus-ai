# Complete Setup Guide - Step by Step

## Step 1: Install Homebrew (if needed)

```bash
# Check if Homebrew is installed
which brew

# If not installed, install it:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Follow the on-screen instructions to add Homebrew to your PATH
```

## Step 2: Install AWS SAM CLI

```bash
# Add AWS tap to Homebrew
brew tap aws/tap

# Install SAM CLI
brew install aws-sam-cli

# Verify installation
sam --version
# Expected output: SAM CLI, version 1.x.x
```

## Step 3: Install AWS CLI

```bash
# Install AWS CLI v2
brew install awscli

# Verify installation
aws --version
# Expected output: aws-cli/2.x.x Python/3.x.x Darwin/xx.x.x
```

## Step 4: Get AWS Credentials

### Option A: If you already have an AWS account

1. **Login to AWS Console**
   - Go to: https://console.aws.amazon.com/
   - Sign in with your email and password

2. **Navigate to IAM**
   - Click your account name (top right corner)
   - Click "Security credentials"
   - OR search for "IAM" in the search bar

3. **Create Access Key**
   - Scroll down to "Access keys" section
   - Click "Create access key"
   - Select "Command Line Interface (CLI)"
   - Check the confirmation box
   - Click "Next"
   - Add description: "AgriNexus Development"
   - Click "Create access key"

4. **Download Credentials**
   - Click "Download .csv file" (IMPORTANT!)
   - Save it somewhere safe (you'll need it in the next step)
   - The CSV contains:
     - Access Key ID (looks like: AKIAIOSFODNN7EXAMPLE)
     - Secret Access Key (looks like: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY)

5. **IMPORTANT**: Never share these credentials or commit them to Git!

### Option B: If you DON'T have an AWS account

1. **Create AWS Account**
   - Go to: https://aws.amazon.com/
   - Click "Create an AWS Account"
   - Follow the signup process
   - You'll need:
     - Email address
     - Credit card (for verification, won't be charged if you stay in free tier)
     - Phone number (for verification)

2. **Wait for account activation** (usually instant, can take up to 24 hours)

3. **Then follow Option A above** to create access keys

## Step 5: Configure AWS CLI

```bash
# Run AWS configure
aws configure

# You'll be prompted for 4 things:
```

**Prompt 1: AWS Access Key ID**
```
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
```
→ Copy from the CSV file you downloaded (column: "Access key ID")

**Prompt 2: AWS Secret Access Key**
```
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```
→ Copy from the CSV file (column: "Secret access key")

**Prompt 3: Default region**
```
Default region name [None]: us-east-1
```
→ Type: `us-east-1` (Bedrock is available here)

**Prompt 4: Output format**
```
Default output format [None]: json
```
→ Type: `json`

## Step 6: Verify AWS Configuration

```bash
# Test your credentials
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }

# If you see this, your credentials are working! ✓
```

## Step 7: Enable Bedrock Models (CRITICAL!)

Bedrock models require manual approval before you can use them.

### Via AWS Console (Easier):

1. **Go to Bedrock Console**
   - https://console.aws.amazon.com/bedrock/
   - Make sure you're in **us-east-1** region (top right corner)

2. **Request Model Access**
   - Click "Model access" in the left sidebar
   - Click "Manage model access" (orange button)
   - Find and enable these models:
     - ✓ **Claude 3 Sonnet** (anthropic.claude-3-sonnet-20240229-v1:0)
     - ✓ **Titan Embeddings G1 - Text** (amazon.titan-embed-text-v1)
   - Click "Request model access"
   - Wait for approval (usually instant)

3. **Verify Access**
   - Refresh the page
   - Status should show "Access granted" (green checkmark)

### Via AWS CLI (Alternative):

```bash
# List available models
aws bedrock list-foundation-models --region us-east-1

# Check if you have access
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude-3-sonnet`)]'
```

## Step 8: Install Python Dependencies

```bash
# Install required Python packages
pip3 install -r requirements.txt

# Or install individually:
pip3 install boto3 pytest

# Verify installation
python3 -c "import boto3; print('boto3 version:', boto3.__version__)"
pytest --version
```

## Step 9: Validate Your Setup

Run this validation script:

```bash
# Create validation script
cat > validate-setup.sh << 'EOF'
#!/bin/bash
echo "=== Validating Setup ==="
echo ""

# Check SAM
echo -n "SAM CLI: "
if command -v sam &> /dev/null; then
    sam --version | head -1
else
    echo "❌ NOT INSTALLED"
fi

# Check AWS CLI
echo -n "AWS CLI: "
if command -v aws &> /dev/null; then
    aws --version
else
    echo "❌ NOT INSTALLED"
fi

# Check Python
echo -n "Python: "
python3 --version

# Check boto3
echo -n "boto3: "
python3 -c "import boto3; print(boto3.__version__)" 2>/dev/null || echo "❌ NOT INSTALLED"

# Check pytest
echo -n "pytest: "
pytest --version 2>/dev/null | head -1 || echo "❌ NOT INSTALLED"

# Check AWS credentials
echo ""
echo "AWS Credentials:"
aws sts get-caller-identity 2>/dev/null && echo "✓ Credentials working" || echo "❌ Credentials not configured"

echo ""
echo "=== Setup Validation Complete ==="
EOF

chmod +x validate-setup.sh
./validate-setup.sh
```

## Step 10: Test SAM Template

```bash
# Validate the SAM template
sam validate --lint

# Expected output:
# template.yaml is a valid SAM Template

# Build the template (doesn't deploy, just prepares)
sam build

# Expected output:
# Build Succeeded
```

## Step 11: Ready to Deploy!

If all validations passed, you're ready:

```bash
# Deploy Week 1 infrastructure
bash scripts/setup-week1.sh agrinexus-dev us-east-1

# This will take 15-20 minutes and will:
# 1. Deploy infrastructure (~5-10 min)
# 2. Upload FAO PDFs (~2-3 min)
# 3. Start KB ingestion (~5-15 min)
# 4. Run tests (~1-2 min)
```

## Troubleshooting

### Issue: "Access Denied" errors

**Check IAM permissions:**
```bash
# Your user needs these permissions:
# - CloudFormation
# - DynamoDB
# - S3
# - Bedrock
# - OpenSearch Serverless
# - IAM (to create roles)

# Easiest solution: Attach AdministratorAccess policy
# 1. Go to IAM Console
# 2. Click "Users" → Your username
# 3. Click "Add permissions" → "Attach policies directly"
# 4. Search for "AdministratorAccess"
# 5. Check the box and click "Add permissions"
```

### Issue: "Bedrock model not available"

**Solution:**
```bash
# Go to Bedrock Console
# https://console.aws.amazon.com/bedrock/
# Click "Model access" → "Manage model access"
# Enable Claude 3 Sonnet and Titan Embeddings
```

### Issue: "Region not supported"

**Solution:**
```bash
# Use us-east-1 (Virginia) or us-west-2 (Oregon)
# These regions have full Bedrock support

# Update your AWS config:
aws configure set region us-east-1
```

### Issue: "OpenSearch Serverless not available"

**Solution:**
```bash
# OpenSearch Serverless is only in certain regions
# Use us-east-1 for guaranteed availability
```

## Cost Warning ⚠️

Before deploying, understand the costs:

| Service | Cost |
|---------|------|
| OpenSearch Serverless | ~$20/month (minimum) |
| Bedrock queries | ~$5/month (pay-per-use) |
| DynamoDB | $0 (free tier) |
| S3 | $0 (free tier) |
| Lambda | $0 (free tier) |
| **Total** | **~$25/month** |

**To minimize costs:**
- Deploy only when testing
- Delete stack when done: `aws cloudformation delete-stack --stack-name agrinexus-dev`
- Monitor costs: https://console.aws.amazon.com/billing/

## Next Steps

After successful deployment:
1. Review CloudWatch logs
2. Test the 20 golden questions
3. Verify guardrails are working
4. Check actual costs in Billing Dashboard
5. Proceed to Week 2 (WhatsApp integration)

## CloudWatch Dashboard (Optional)

Create the prebuilt dashboard for ops visibility:

```bash
./scripts/create-cloudwatch-dashboard.sh dev us-east-1
```

## Real Weather API (Optional)

To enable real weather ingestion (post-MVP):

1. Create an OpenWeatherMap API key.
2. Update Lambda environment variables:

```bash
USE_REAL_WEATHER=true
WEATHER_API_KEY="YOUR_OPENWEATHER_API_KEY"
```

**Note**: Keep `MOCK_WEATHER=true` for deterministic demos.

## Week 2 WhatsApp Prerequisite (Webhook Signature)

Create the WhatsApp app secret in Secrets Manager so webhook signature verification can be enabled:

```bash
aws secretsmanager create-secret \
  --name agrinexus/whatsapp/app-secret \
  --secret-string "YOUR_APP_SECRET"
```

## Need Help?

- AWS Documentation: https://docs.aws.amazon.com/
- SAM CLI Guide: https://docs.aws.amazon.com/serverless-application-model/
- Bedrock Guide: https://docs.aws.amazon.com/bedrock/

## Security Best Practices

1. **Never commit credentials to Git**
   - `.gitignore` already excludes `.env` files
   - Never hardcode access keys in code

2. **Use IAM roles in production**
   - For Lambda functions, use execution roles
   - For EC2, use instance profiles

3. **Enable MFA on your AWS account**
   - Go to IAM → Your user → Security credentials
   - Enable MFA for extra security

4. **Rotate access keys regularly**
   - Create new keys every 90 days
   - Delete old keys

5. **Monitor CloudTrail logs**
   - Track all API calls
   - Detect suspicious activity
