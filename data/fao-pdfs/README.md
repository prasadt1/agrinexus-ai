# Knowledge Base Source Documents

This directory contains the source documents for the AgriNexus AI knowledge base. The PDF files are **not included in the git repository** due to copyright and licensing considerations.

## Directory Structure

```
data/fao-pdfs/
├── en/                          # English source documents
│   ├── cotton-production.pdf
│   ├── ipm-guide.pdf
│   ├── pesticide-application.pdf
│   └── new-sources/             # Additional Indian government sources
│       ├── icar-cicr-pest-disease-advisory-2024.pdf
│       ├── ipm-bt-cotton.pdf
│       ├── ipm-cotton-2024.pdf
│       ├── kb_manifest.csv
│       ├── niphm-cotton-advisory-2022.pdf
│       ├── nriipm-crop-sap-book.pdf
│       ├── pau-package-of-practices-kharif-2024.pdf
│       └── rajendran-2018-cotton-pests.pdf
```

## Source Documents

### FAO Publications (Public Domain / Open Access)

1. **Cotton Production Guide**
   - Source: FAO (Food and Agriculture Organization of the United Nations)
   - URL: http://www.fao.org/3/i8314en/I8314EN.pdf
   - License: FAO open access policy allows reproduction for educational purposes

2. **Integrated Pest Management (IPM) Guide**
   - Source: FAO
   - URL: http://www.fao.org/3/a-i3765e.pdf
   - License: FAO open access

3. **Pesticide Application Guide**
   - Source: FAO
   - URL: http://www.fao.org/3/i8419en/I8419EN.pdf
   - License: FAO open access

### Indian Government Publications (Open Access)

4. **ICAR-CICR Pest & Disease Advisory 2024**
   - Source: Indian Council of Agricultural Research - Central Institute for Cotton Research
   - URL: https://cicr.org.in/
   - License: Government of India open access policy

5. **IPM for Bt Cotton**
   - Source: National Institute of Plant Health Management (NIPHM)
   - URL: https://niphm.gov.in/
   - License: Government of India open access

6. **IPM Cotton 2024**
   - Source: NIPHM
   - License: Government of India open access

7. **NIPHM Cotton Advisory 2022**
   - Source: National Institute of Plant Health Management
   - License: Government of India open access

8. **NRIIPM Crop SAP Book**
   - Source: National Research Institute for Integrated Pest Management
   - License: Government of India open access

9. **PAU Package of Practices (Kharif 2024)**
   - Source: Punjab Agricultural University
   - URL: https://pau.edu/
   - License: Educational use permitted

### Academic Publications

10. **Rajendran 2018 - Cotton Pests**
    - Source: Academic research paper
    - Note: Verify copyright before redistribution

## How to Populate the Knowledge Base

### Option 1: Download from Original Sources

1. Download the PDFs from the URLs listed above
2. Place them in the appropriate directories as shown in the structure
3. Run the ingestion script (if available) or upload to S3

### Option 2: Use Your Own Documents

You can replace these with your own agricultural extension documents:

1. Place PDF files in `data/fao-pdfs/en/`
2. Update the Bedrock Knowledge Base to sync from S3
3. The system will automatically index the new documents

## S3 Upload

Once you have the PDFs locally, upload them to your S3 bucket:

```bash
# Upload to S3 knowledge base bucket
aws s3 sync data/fao-pdfs/en/ s3://agrinexus-knowledge-base-dev/en/ \
    --exclude "*.DS_Store" \
    --exclude "README.md"

# Trigger Bedrock Knowledge Base ingestion
aws bedrock-agent start-ingestion-job \
    --knowledge-base-id ARZ4XQEBCU \
    --data-source-id <your-data-source-id>
```

## Copyright Notice

The documents listed above are believed to be in the public domain or available under open access licenses that permit educational and non-commercial use. However, users should:

1. Verify the current licensing terms from the original sources
2. Comply with any attribution requirements
3. Not redistribute copyrighted materials without permission
4. Use the content only for educational and non-commercial purposes

AgriNexus AI is an educational project for the AWS 10,000 AIdeas Competition and does not claim ownership of any source documents.

## Alternative Knowledge Sources

If you cannot access the documents listed above, consider these alternatives:

- **ICAR Publications**: https://icar.org.in/
- **FAO Digital Library**: http://www.fao.org/documents/
- **State Agricultural Universities**: Most Indian state agricultural universities publish extension guides
- **Krishi Vigyan Kendras (KVKs)**: Local agricultural extension centers

## Questions?

For questions about the knowledge base setup, see the main README.md or contact the project maintainers.
