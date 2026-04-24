# Install Prerequisites for Week 1

## 1. Install AWS SAM CLI

### Option A: Using Homebrew (Recommended for macOS)
```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install AWS SAM CLI
brew tap aws/tap
brew install aws-sam-cli

# Verify installation
sam --version
# Should show: SAM CLI, version 1.x.x
```

### Option B: Using pip (Alternative)
```bash
# Install via pip
pip3 install aws-sam-cli

# Verify installation
sam --version
```

## 2. Install AWS CLI

```bash
# Install AWS CLI v2
brew install awscli

# Verify installation
aws --version
# Should show: aws-cli/2.x.x
```

## 3. Configure AWS Credentials

```bash
# Run AWS configure
aws configure

# You'll be prompted for:
# AWS Access Key ID: [Your access key]
# AWS Secret Access Key: [Your secret key]
# Default region name: us-east-1
# Default output format: json
```

### How to get AWS credentials:

1. Go to AWS Console: https://console.aws.amazon.com/
2. Click your name (top right) → Security credentials
3. Scroll to "Access keys"
4. Click "Create access key"
5. Download the CSV file (save it securely!)
6. Use those credentials in `aws configure`

## 4. Install Python Dependencies

```bash
# Install Python packages
pip3 install -r requirements.txt

# Or install individually
pip3 install boto3 pytest
```

## 5. Verify Everything is Installed

```bash
# Check SAM
sam --version

# Check AWS CLI
aws --version

# Check Python
python3 --version

# Check boto3
python3 -c "import boto3; print(boto3.__version__)"

# Check pytest
pytest --version

# Test AWS credentials
aws sts get-caller-identity
# Should show your AWS account ID
```

## 6. Enable Bedrock Models (One-time setup)

```bash
# Go to AWS Console
# Navigate to: Bedrock → Model access
# Request access to:
# - Claude 3 Sonnet
# - Titan Embeddings

# Or use CLI:
aws bedrock list-foundation-models --region us-east-1
```

## 6.5 WhatsApp Webhook Secret (Week 2)

For webhook signature verification, create the WhatsApp app secret in Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name agrinexus/whatsapp/app-secret \
  --secret-string "YOUR_APP_SECRET"
```

## 6.6 Weather API Key (Optional)

For real spray-condition checks, create an OpenWeatherMap key and store it in **Secrets Manager** as `agrinexus/weather/api-key` (see `WEATHER-API-SETUP.md`). The Weather Lambda uses `WEATHER_API_KEY_SECRET`—**do not** pass the key via `sam deploy` parameters or commit it to git.

Ensure `MOCK_WEATHER` is false on the Weather poller for production when you want live weather.

## Troubleshooting

### Issue: "sam: command not found"
**Solution**: Install SAM CLI using Homebrew (see above)

### Issue: "aws: command not found"
**Solution**: Install AWS CLI using Homebrew (see above)

### Issue: "Access Denied" when running aws commands
**Solution**: 
1. Check credentials: `aws configure list`
2. Verify IAM permissions in AWS Console
3. Ensure your IAM user has AdministratorAccess or required permissions

### Issue: "Bedrock model not available"
**Solution**: 
1. Go to AWS Console → Bedrock → Model access
2. Request access to Claude 3 Sonnet and Titan Embeddings
3. Wait for approval (usually instant)

### Issue: "Region not supported"
**Solution**: Use us-east-1 or us-west-2 (Bedrock available in these regions)

## Required IAM Permissions

Your AWS user needs these permissions:
- CloudFormation (create/update/delete stacks)
- DynamoDB (create tables)
- S3 (create buckets, upload files)
- Bedrock (create knowledge bases, invoke models)
- Bedrock Knowledge Base / vector store (S3 Vectors for current path; OpenSearch Serverless only if you maintain a legacy collection)
- IAM (create roles for Bedrock)
- Lambda (create functions)

**Easiest**: Attach `AdministratorAccess` policy to your IAM user (for development)

## Cost Estimate

Before deploying, use **`README.md`** as the source of truth for **current** costs. Summary:

**Current stack (S3 Vectors + Bedrock, post–April 2026):** on the order of **~$53/month** for ~1,000 farmers (mostly Bedrock usage; S3 vectors ~$1.30).

**Legacy note:** OpenSearch Serverless was **~$174/month fixed** and drove **~$214/month** totals in early deployments—replaced by S3 Vectors for this project.

> **Detail:** See `../architecture.md` for system-level context.

## Ready to Deploy?

Once everything is installed:

```bash
# Validate template
sam validate --lint

# Deploy
bash scripts/setup-week1.sh agrinexus-dev us-east-1
```

## Quick Installation Script

Run this to install everything at once:

```bash
# Install Homebrew (if needed)
which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install SAM CLI
brew tap aws/tap
brew install aws-sam-cli

# Install AWS CLI
brew install awscli

# Install Python dependencies
pip3 install boto3 pytest

# Configure AWS
echo "Now run: aws configure"
echo "Enter your AWS credentials when prompted"
```
