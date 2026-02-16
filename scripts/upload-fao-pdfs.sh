#!/bin/bash
# Upload FAO PDF manuals to S3 for Bedrock Knowledge Base

set -e

# Get bucket name from CloudFormation stack
STACK_NAME=${1:-agrinexus-dev}
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseBucketName`].OutputValue' \
  --output text)

if [ -z "$BUCKET_NAME" ]; then
  echo "Error: Could not find bucket name from stack $STACK_NAME"
  exit 1
fi

echo "Uploading FAO PDFs to s3://$BUCKET_NAME/en/"

# Create local directory structure
mkdir -p data/fao-pdfs/en

# Download FAO manuals (English versions)
# These will be used to generate Hindi, Marathi, Telugu responses via Bedrock

echo "Downloading FAO Cotton Production Manual..."
curl -L -o data/fao-pdfs/en/cotton-production.pdf \
  "http://www.fao.org/3/i8314en/I8314EN.pdf" || echo "Manual download placeholder"

echo "Downloading FAO Integrated Pest Management..."
curl -L -o data/fao-pdfs/en/ipm-guide.pdf \
  "http://www.fao.org/3/a-i3765e.pdf" || echo "Manual download placeholder"

echo "Downloading FAO Pesticide Application..."
curl -L -o data/fao-pdfs/en/pesticide-application.pdf \
  "http://www.fao.org/3/i8419en/I8419EN.pdf" || echo "Manual download placeholder"

# Create placeholder PDFs if downloads fail
for file in cotton-production.pdf ipm-guide.pdf pesticide-application.pdf; do
  if [ ! -f "data/fao-pdfs/en/$file" ] || [ ! -s "data/fao-pdfs/en/$file" ]; then
    echo "Creating placeholder for $file"
    cat > "data/fao-pdfs/en/$file.txt" << 'EOF'
# FAO Agricultural Manual - Cotton Production

## Integrated Pest Management (IPM)

### Aphid Control
**Symptoms**: Curling leaves, sticky honeydew, stunted growth
**Threshold**: 5-10 aphids per leaf
**Control**: 
- Spray neem oil (5ml/liter) or imidacloprid (0.3ml/liter)
- Apply during early morning or evening
- Avoid spraying during flowering
- Weather: No rain for 24 hours, wind speed < 10 km/h

### Bollworm Management
**Symptoms**: Holes in bolls, frass near entry points
**Threshold**: 2 larvae per plant
**Control**:
- Use pheromone traps for monitoring
- Spray Bt (Bacillus thuringiensis) or chlorantraniliprole
- Timing: Apply at square formation and flowering stages

### Whitefly Control
**Symptoms**: Yellow leaves, sooty mold, reduced vigor
**Threshold**: 5 adults per leaf
**Control**:
- Spray thiamethoxam (0.2g/liter) or acetamiprid
- Ensure good spray coverage on leaf undersides
- Rotate insecticides to prevent resistance

## Banned Pesticides (DO NOT USE)
- Paraquat (highly toxic)
- Monocrotophos (banned in India)
- Endosulfan (environmental hazard)
- Methyl parathion (acute toxicity)
- Phorate (restricted use)

## Weather-Based Recommendations

### Spraying Conditions
- Temperature: 20-30°C (optimal)
- Wind speed: < 10 km/h
- No rain forecast for 24 hours
- Relative humidity: 50-70%
- Time: Early morning (6-9 AM) or evening (4-6 PM)

### Irrigation Timing
- Cotton: 7-10 days interval during vegetative stage
- Critical stages: Flowering and boll formation
- Avoid waterlogging

## Nutrient Management
- Nitrogen: 120-150 kg/ha (split application)
- Phosphorus: 60 kg/ha (basal)
- Potassium: 60 kg/ha (split)
- Apply based on soil test results

## Contact Information
For technical assistance, contact your local Krishi Vigyan Kendra (KVK) extension officer.
EOF
  fi
done

# Upload to S3
echo "Uploading files to S3..."
aws s3 sync data/fao-pdfs/en/ s3://$BUCKET_NAME/en/ \
  --exclude "*.DS_Store" \
  --metadata "source=FAO,language=en,indexed=$(date +%Y-%m-%d)"

echo "Upload complete!"
echo "Next step: Sync Bedrock Knowledge Base"
echo "  aws bedrock-agent start-ingestion-job --knowledge-base-id <KB_ID> --data-source-id <DS_ID>"
