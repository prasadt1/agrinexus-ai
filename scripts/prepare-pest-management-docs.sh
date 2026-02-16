#!/bin/bash
set -euo pipefail

# Script to help prepare proper cotton pest management documents
# for your Bedrock Knowledge Base
# 
# Philosophy: Prefer authoritative, open-access government/FAO sources
# over potentially copyrighted research papers

BASE_DIR="data/fao-pdfs/en/new-sources"
MANIFEST="$BASE_DIR/kb_manifest.csv"

echo "=========================================="
echo "Cotton Pest Management Document Preparation"
echo "=========================================="
echo ""

# Create directory for new documents
mkdir -p "$BASE_DIR"

echo "Step 1: Download Core Government / FAO Documents"
echo "------------------------------------------------"
echo "Manually download and save to: $BASE_DIR/"
echo ""
echo "REQUIRED (Indian govt / FAO - high priority, clearly open):"
echo ""
echo "1. PPQS Cotton Pest Advisories (https://ppqs.gov.in/advisories-section)"
echo "   → ppqs-pink-bollworm.pdf (Advisory on Pink boll worm)"
echo "   → ppqs-whitefly.pdf (Advisory on White fly)"
echo ""
echo "2. NIPHM Pest Alerts (https://niphm.gov.in/ > Pest Alerts)"
echo "   → niphm-cotton-advisory-2022-09.pdf (Sept 2022, 604 KB)"
echo "   → niphm-cotton-advisory-2021-09.pdf (Sept 2021, 484 KB)"
echo "   → niphm-cotton-advisory-2020-05.pdf (May 2020, 108 KB)"
echo "   → niphm-cotton-advisory-2019-08.pdf (Aug 2019, 544 KB)"
echo "   → niphm-cotton-advisory-2019-07.pdf (July 2019, 344 KB)"
echo ""
echo "3. FAO Cotton IPM Resources (search: FAO AGRIS cotton IPM CC BY)"
echo "   → Look for FAO documents with CC BY 4.0 license"
echo "   → Save as: fao-cotton-ipm-*.pdf"
echo ""
echo "OPTIONAL (Deep technical references - verify open access first!):"
echo ""
echo "4. Research Papers (ONLY if clearly marked open access)"
echo "   → rajendran-2018-cotton-pests.pdf"
echo "     (https://www.researchgate.net/publication/326762536)"
echo "   → ipm-bt-cotton.pdf"
echo "     (https://www.researchgate.net/publication/268630163)"
echo "   → ipm-cotton-2024.pdf"
echo "     (https://www.researchgate.net/publication/381605032)"
echo ""
echo "⚠️  WARNING: ResearchGate PDFs may be copyrighted journal articles."
echo "   Only use if you confirm they are open access (CC BY, CC0, etc.)"
echo "   For production RAG, stick to government/FAO sources."
echo ""

read -p "Press Enter when you've downloaded the core documents..."

echo ""
echo "Step 2: Verify Downloaded Files"
echo "--------------------------------"

# Core required files
REQUIRED_FILES=(
    "ppqs-pink-bollworm.pdf"
    "ppqs-whitefly.pdf"
)

# Nice to have files
OPTIONAL_FILES=(
    "niphm-cotton-advisory-2022-09.pdf"
    "niphm-cotton-advisory-2021-09.pdf"
    "niphm-cotton-advisory-2020-05.pdf"
    "niphm-cotton-advisory-2019-08.pdf"
    "niphm-cotton-advisory-2019-07.pdf"
    "rajendran-2018-cotton-pests.pdf"
    "ipm-bt-cotton.pdf"
    "ipm-cotton-2024.pdf"
)

FOUND_REQUIRED=0
FOUND_OPTIONAL=0
TOTAL_REQUIRED=${#REQUIRED_FILES[@]}
TOTAL_OPTIONAL=${#OPTIONAL_FILES[@]}

echo "Required files:"
for file in "${REQUIRED_FILES[@]}"; do
    PATH_FILE="$BASE_DIR/$file"
    if [ -f "$PATH_FILE" ]; then
        echo "  ✓ Found: $file"
        SIZE=$(du -h "$PATH_FILE" | cut -f1)
        echo "    Size: $SIZE"
        ((FOUND_REQUIRED++))
    else
        echo "  ✗ Missing: $file"
    fi
done

echo ""
echo "Optional files:"
for file in "${OPTIONAL_FILES[@]}"; do
    PATH_FILE="$BASE_DIR/$file"
    if [ -f "$PATH_FILE" ]; then
        echo "  ✓ Found: $file"
        SIZE=$(du -h "$PATH_FILE" | cut -f1)
        echo "    Size: $SIZE"
        ((FOUND_OPTIONAL++))
    else
        echo "  · Not present: $file (ok)"
    fi
done

echo ""
echo "Summary: $FOUND_REQUIRED/$TOTAL_REQUIRED required, $FOUND_OPTIONAL/$TOTAL_OPTIONAL optional"

if [ $FOUND_REQUIRED -lt $TOTAL_REQUIRED ]; then
    echo ""
    echo "⚠️  Missing core PPQS advisories. These are essential for your RAG system."
    echo "   Download from: https://ppqs.gov.in/advisories-section"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please download required files first."
        exit 1
    fi
fi

echo ""
echo "Step 3: Check / Create Metadata Manifest"
echo "----------------------------------------"

if [ ! -f "$MANIFEST" ]; then
    echo "Creating new manifest: $MANIFEST"
    cat > "$MANIFEST" << 'EOF'
filename,title,source_url,year,license,region,crop,pests
# Example row:
# ppqs-pink-bollworm.pdf,Advisory on Pink Bollworm,https://ppqs.gov.in/advisories-section,2023,Public Domain,India,Cotton,Pink Bollworm
# 
# Instructions:
# 1. Add one row per PDF file
# 2. Use actual filename from new-sources folder
# 3. License: "Public Domain" for govt docs, "CC BY 4.0" for FAO, "Check" for research papers
# 4. Region: India, Global, etc.
# 5. Pests: Comma-separated list (use semicolon if needed)
#
# This manifest helps with:
# - RAG evaluation and citations
# - Tracking document provenance
# - Filtering by region/crop/pest
# - Ensuring licensing compliance
EOF
    echo "✓ Created $MANIFEST"
    echo ""
    echo "📝 TODO: Open $MANIFEST and add metadata for each PDF you downloaded."
    echo "   This is your single source of truth for what's in your Knowledge Base."
else
    echo "✓ Found existing manifest: $MANIFEST"
    ROWS=$(tail -n +2 "$MANIFEST" | grep -v '^#' | grep -v '^$' | wc -l)
    echo "  Contains $ROWS document entries"
fi

echo ""
echo "Step 4: Upload to S3"
echo "--------------------"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)

if [ -z "$ACCOUNT_ID" ]; then
    echo "⚠️  Could not get AWS account ID. Make sure AWS CLI is configured."
    echo ""
    echo "Run manually:"
    echo "  aws s3 sync \"$BASE_DIR/\" s3://agrinexus-kb-YOUR_ACCOUNT_ID-us-east-1/en/"
else
    BUCKET="s3://agrinexus-kb-${ACCOUNT_ID}-us-east-1/en/"
    echo "Target bucket: $BUCKET"
    echo ""
    
    # Show what will be uploaded
    echo "Files to upload:"
    find "$BASE_DIR" -type f -name "*.pdf" | while read file; do
        echo "  - $(basename "$file")"
    done
    echo ""
    
    read -p "Proceed with upload? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        aws s3 sync "$BASE_DIR/" "$BUCKET" --exclude "*.csv"
        echo "✓ Upload complete!"
        echo ""
        echo "Note: Manifest file (kb_manifest.csv) was NOT uploaded to S3."
        echo "      It's for your local tracking only."
    else
        echo "Skipped. Run manually when ready:"
        echo "  aws s3 sync \"$BASE_DIR/\" \"$BUCKET\" --exclude \"*.csv\""
    fi
fi

echo ""
echo "Step 5: Trigger Knowledge Base Ingestion"
echo "----------------------------------------"
echo "Option 1 (Console):"
echo "  1. Go to AWS Console > Bedrock > Knowledge Bases"
echo "  2. Select your Knowledge Base (ID: H81XLD3YWY)"
echo "  3. Click 'Sync' button"
echo "  4. Wait 5-10 minutes for ingestion to complete"
echo ""
echo "Option 2 (CLI):"
echo "  # First, get your data source ID:"
echo "  aws bedrock-agent list-data-sources \\"
echo "    --knowledge-base-id H81XLD3YWY \\"
echo "    --query 'dataSourceSummaries[0].dataSourceId' \\"
echo "    --output text"
echo ""
echo "  # Then start ingestion:"
echo "  aws bedrock-agent start-ingestion-job \\"
echo "    --knowledge-base-id H81XLD3YWY \\"
echo "    --data-source-id YOUR_DATA_SOURCE_ID"
echo ""

echo "Step 6: Run Golden Question Test Suite"
echo "--------------------------------------"
echo "After ingestion completes, validate your RAG system:"
echo ""
echo "  python test_rag_example.py"
echo ""
echo "Expected improvements with proper documents:"
echo "  ✓ Specific pesticide names (imidacloprid, thiamethoxam, neem)"
echo "  ✓ Economic thresholds (5-10 aphids/leaf, 10% affected plants)"
echo "  ✓ Spray timing and weather conditions"
echo "  ✓ Irrigation schedules (7-10 days during flowering)"
echo "  ✓ Banned pesticide warnings (paraquat, monocrotophos)"
echo ""
echo "Then run full test suite:"
echo "  pytest tests/test_golden_questions.py -v"
echo ""
echo "=========================================="
echo "Best Practices for RAG Document Curation"
echo "=========================================="
echo ""
echo "✓ Prefer government/FAO sources over research papers"
echo "✓ Track metadata in kb_manifest.csv"
echo "✓ Verify licensing before production use"
echo "✓ Test with golden questions after each update"
echo "✓ Keep 5-10 high-quality docs per topic (cotton pests)"
echo "✓ Expand systematically (wheat rust, rice blast, etc.)"
echo ""
echo "Next steps:"
echo "  1. Fill out kb_manifest.csv with document metadata"
echo "  2. Create a 15-20 question golden set for cotton pests"
echo "  3. Re-run tests after every KB update"
echo "  4. Repeat this pattern for other crops/pests"
echo ""
echo "=========================================="
