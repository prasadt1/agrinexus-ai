#!/bin/bash
set -euo pipefail

# Script to download official government sources for AgriNexus RAG
# Based on research from official PPQS, NIPHM, ICAR-CICR, and State Universities

TARGET_DIR="data/fao-pdfs/en/new-sources"
mkdir -p "$TARGET_DIR"

echo "=========================================="
echo "Downloading Official Government Sources"
echo "=========================================="
echo ""

# Phase 1: Critical Sources
echo "Phase 1: Critical Sources (Do First)"
echo "------------------------------------"
echo ""

echo "1. ICAR-CICR 2024 Comprehensive Advisory..."
curl -L -o "$TARGET_DIR/icar-cicr-pest-disease-advisory-2024.pdf" \
  "https://nsai.co.in/storage/app/media/uploaded-files/ICAR-CICR_Advisory%20Pest%20and%20Disease%20Management%202024.pdf" \
  2>/dev/null && echo "✓ Downloaded" || echo "✗ Failed (try manual download)"

echo ""
echo "2. PPQS Pink Bollworm Advisory..."
curl -L -o "$TARGET_DIR/ppqs-pink-bollworm-advisory.pdf" \
  "https://ppqs.gov.in/sites/default/files/cotton_pbw_advisory.pdf" \
  2>/dev/null && echo "✓ Downloaded" || echo "✗ Failed (try manual download)"

echo ""
echo "3. PAU Package of Practices Kharif 2024..."
curl -L -o "$TARGET_DIR/pau-package-of-practices-kharif-2024.pdf" \
  "https://pauwp.pau.edu/wp-content/uploads/2025/11/RIB-2024.pdf" \
  2>/dev/null && echo "✓ Downloaded" || echo "✗ Failed (try manual download)"

echo ""
echo "4. PAU Pink Bollworm Vigilance..."
curl -L -o "$TARGET_DIR/pau-pink-bollworm-vigilance.pdf" \
  "https://www.pau.edu/content/sandesh/7.pdf" \
  2>/dev/null && echo "✓ Downloaded" || echo "✗ Failed (try manual download)"

echo ""
echo "=========================================="
echo "Download Summary"
echo "=========================================="
echo ""

# Check what was downloaded
DOWNLOADED=0
FAILED=0

FILES=(
    "icar-cicr-pest-disease-advisory-2024.pdf"
    "ppqs-pink-bollworm-advisory.pdf"
    "pau-package-of-practices-kharif-2024.pdf"
    "pau-pink-bollworm-vigilance.pdf"
)

for file in "${FILES[@]}"; do
    if [ -f "$TARGET_DIR/$file" ] && [ -s "$TARGET_DIR/$file" ]; then
        SIZE=$(du -h "$TARGET_DIR/$file" | cut -f1)
        echo "✓ $file ($SIZE)"
        ((DOWNLOADED++))
    else
        echo "✗ $file (failed or empty)"
        ((FAILED++))
    fi
done

echo ""
echo "Downloaded: $DOWNLOADED/${#FILES[@]}"
echo "Failed: $FAILED/${#FILES[@]}"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "=========================================="
    echo "Manual Download Required"
    echo "=========================================="
    echo ""
    echo "Some files failed to download automatically."
    echo "Please download manually from:"
    echo ""
    echo "1. ICAR-CICR Advisory:"
    echo "   https://nsai.co.in/storage/app/media/uploaded-files/ICAR-CICR_Advisory%20Pest%20and%20Disease%20Management%202024.pdf"
    echo ""
    echo "2. PPQS Pink Bollworm:"
    echo "   https://ppqs.gov.in/sites/default/files/cotton_pbw_advisory.pdf"
    echo ""
    echo "3. PAU Package of Practices:"
    echo "   https://pauwp.pau.edu/wp-content/uploads/2025/11/RIB-2024.pdf"
    echo ""
    echo "4. PAU Pink Bollworm Vigilance:"
    echo "   https://www.pau.edu/content/sandesh/7.pdf"
    echo ""
    echo "5. NIPHM Pest Alerts (manual navigation required):"
    echo "   https://nriipm.res.in/pestalert.aspx"
    echo "   - Look for Cotton advisories from 2019-2021"
    echo "   - Download and save as: niphm-cotton-advisory-YYYY-MM.pdf"
    echo ""
fi

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Verify downloaded files:"
echo "   ls -lh $TARGET_DIR/*.pdf"
echo ""
echo "2. Update manifest:"
echo "   nano $TARGET_DIR/kb_manifest.csv"
echo ""
echo "3. Upload to S3:"
echo "   aws s3 sync $TARGET_DIR/ s3://agrinexus-kb-043624892076-us-east-1/en/ --exclude '*.csv'"
echo ""
echo "4. Trigger ingestion:"
echo "   aws bedrock-agent start-ingestion-job --knowledge-base-id H81XLD3YWY --data-source-id GVNHYZZBIT"
echo ""
echo "5. Test (after 10-15 minutes):"
echo "   pytest tests/test_golden_questions_realistic.py -v"
echo ""
echo "=========================================="
