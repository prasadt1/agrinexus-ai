# AgriNexus AI - Web Demo

Privacy-friendly web chat interface for AgriNexus AI. No phone number required.

## Features

- ✅ Text-based queries to Bedrock Knowledge Base
- ✅ Multi-language support (English, Hindi, Marathi, Telugu)
- ✅ Rate limiting (10 queries/hour per IP)
- ✅ No data storage (stateless)
- ✅ Mobile-responsive design
- ✅ Citation display

## Deployment

### Step 1: Deploy Backend

```bash
# From project root
cd ~/Desktop/Agri-Nexus\ AI\ Project

# Build and deploy
sam build
sam deploy

# Note the WebChatApiUrl from outputs
```

### Step 2: Update Frontend

1. Open `docs/web-demo/index.html`
2. Find line with `const API_URL = 'YOUR_API_GATEWAY_URL_HERE';`
3. Replace with your actual API Gateway URL from Step 1
4. Save the file

Example:
```javascript
const API_URL = 'https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev/chat';
```

### Step 3: Deploy to GitHub Pages

#### Option A: GitHub Pages (Recommended)

1. Commit and push changes:
```bash
git add docs/web-demo/
git commit -m "Add web chat demo"
git push origin main
```

2. Enable GitHub Pages:
   - Go to your repo on GitHub
   - Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main`, Folder: `/docs`
   - Save

3. Your demo will be live at:
   ```
   https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/web-demo/
   ```

#### Option B: S3 + CloudFront (Custom Domain)

```bash
# Create S3 bucket
aws s3 mb s3://demo.agrinexus.ai

# Enable static website hosting
aws s3 website s3://demo.agrinexus.ai \
  --index-document index.html

# Upload files
aws s3 sync docs/web-demo/ s3://demo.agrinexus.ai/ \
  --acl public-read

# Configure CloudFront (optional, for HTTPS)
# See AWS CloudFront documentation
```

### Step 4: Test

1. Open the deployed URL in your browser
2. Select a language
3. Type a farming question (e.g., "How to control cotton pests?")
4. Verify response appears with citations
5. Test rate limiting (try 11 queries in a row)

## Testing Locally

You can test the frontend locally before deploying:

```bash
# Serve locally (requires Python)
cd docs/web-demo
python3 -m http.server 8000

# Open in browser
open http://localhost:8000
```

**Note:** You still need to deploy the backend first and update the API_URL.

## Architecture

```
User Browser (index.html)
    ↓ HTTPS POST
API Gateway (/chat)
    ↓
Lambda (web-chat)
    ↓
Bedrock Knowledge Base
    ↓
Response with citations
```

## Rate Limiting

- **Per IP:** 10 queries/hour
- **Global:** 100 requests/second (API Gateway throttle)
- **Storage:** DynamoDB with 1-hour TTL

## Privacy

- ✅ No phone numbers collected
- ✅ No user profiles created
- ✅ No conversation history stored
- ✅ IP addresses hashed (SHA-256) for rate limiting
- ✅ Rate limit records auto-expire after 1 hour

## Cost Estimate

| Service | Usage | Cost/Month |
|---------|-------|------------|
| Lambda | ~1000 invocations | $0.20 |
| API Gateway | ~1000 requests | $0.03 |
| DynamoDB | Rate limit writes | $0.01 |
| Bedrock | Same as WhatsApp | Existing |
| GitHub Pages | Hosting | $0.00 |
| **Total** | | **~$0.25** |

## Troubleshooting

### "API URL not configured" error
- Update the `API_URL` constant in `index.html` with your actual API Gateway URL

### CORS errors
- Check that API Gateway has CORS enabled
- Verify `Access-Control-Allow-Origin: *` in Lambda response headers

### Rate limit not working
- Check DynamoDB table has write permissions
- Verify Lambda has `DynamoDBCrudPolicy`

### No response from API
- Check Lambda logs: `sam logs -n agrinexus-web-chat-dev --tail`
- Verify Bedrock Knowledge Base ID is correct
- Check IAM permissions for Bedrock

## Updating the Demo

To update the frontend:

```bash
# Edit index.html
vim docs/web-demo/index.html

# Commit and push (auto-deploys to GitHub Pages)
git add docs/web-demo/index.html
git commit -m "Update web demo"
git push origin main
```

To update the backend:

```bash
# Edit Lambda function
vim src/web-chat/handler.py

# Deploy
sam build
sam deploy
```

## Disabling the Demo

To temporarily disable:

```bash
# Update Lambda environment variable
aws lambda update-function-configuration \
  --function-name agrinexus-web-chat-dev \
  --environment Variables={ENABLED=false}
```

To permanently remove:

```bash
# Remove from template
# Delete WebChatHandler and WebChatApi from template-week2.yaml

# Redeploy
sam deploy
```

## Support

For issues or questions:
- Check CloudWatch logs: `sam logs -n agrinexus-web-chat-dev --tail`
- Review API Gateway logs in AWS Console
- Test backend directly with curl:

```bash
curl -X POST https://YOUR_API_URL/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How to control pests?", "language": "en"}'
```

---

**Created:** April 13, 2026  
**Status:** Ready for deployment
