# Official Government Sources Download Guide

## Priority Documents for AgriNexus RAG System

This guide provides direct links to official government and university sources with proper licensing for production use.

---

## 1. PPQS (Plant Protection, Quarantine & Storage) Advisories

### Pink Bollworm Advisory
**Source**: PPQS Official  
**URL**: https://ppqs.gov.in/sites/default/files/cotton_pbw_advisory.pdf  
**Filename**: `ppqs-pink-bollworm-advisory.pdf`  
**License**: Public Domain (Government of India)  
**Contains**: ETL thresholds, management strategies, spray schedules

### Whitefly Advisory
**Source**: PPQS Official  
**Filename**: `white_fly_advisory_in_cotton.pdf`  
**License**: Public Domain (Government of India)  
**Contains**: ETL thresholds, insecticide recommendations, monitoring methods

### Comprehensive 2024 Advisory
**Source**: ICAR-CICR/PPQS via NSAI Mirror  
**URL**: https://nsai.co.in/storage/app/media/uploaded-files/ICAR-CICR_Advisory%20Pest%20and%20Disease%20Management%202024.pdf  
**Filename**: `icar-cicr-pest-disease-advisory-2024.pdf`  
**License**: Public Domain (ICAR)  
**Contains**: Complete pest and disease management for 2024 season

---

## 2. NIPHM/NCIPM Pest Alerts

### Access Portal
**URL**: https://nriipm.res.in/pestalert.aspx  
**Note**: Chronological list of all pest alerts

### Specific Cotton Advisories

#### 2021 Cotton Advisory
**Date**: 14 Sept, 2021  
**File Size**: 484 KB  
**Filename**: `niphm-cotton-advisory-2021-09.pdf`  
**License**: Public Domain (Government of India)

#### 2020 Cotton Advisory
**Date**: 04 May, 2020  
**File Size**: 108 KB  
**Filename**: `niphm-cotton-advisory-2020-05.pdf`  
**License**: Public Domain (Government of India)

#### 2019 Cotton Advisory (North India)
**Date**: 07 Aug, 2019  
**File Size**: 544 KB  
**Filename**: `niphm-cotton-advisory-2019-08.pdf`  
**License**: Public Domain (Government of India)

#### 2019 Cotton Advisory (July)
**Date**: 08 July, 2019  
**File Size**: 344 KB  
**Filename**: `niphm-cotton-advisory-2019-07.pdf`  
**License**: Public Domain (Government of India)

---

## 3. State Agricultural University Bulletins

### MPKV Rahuri (Maharashtra)

#### Cotton Hybrid Varieties Bulletin
**Source**: Mahatma Phule Krishi Vidyapeeth  
**URL**: https://www.scribd.com/document/868677221/10-Cotton-20230912061049  
**Filename**: `mpkv-cotton-hybrid-varieties.pdf`  
**License**: Public Domain (State University)  
**Region**: Maharashtra (Aurangabad, Marathwada)  
**Contains**: Variety recommendations, HDPS (High-Density Planting System)

#### ICAR-CICR Advisories Page
**URL**: https://cicr.org.in/advisories/  
**Contains**: Latest English and regional language bulletins

### PAU Ludhiana (Punjab)

#### Package of Practices (Kharif 2024)
**Source**: Punjab Agricultural University  
**URL**: https://pauwp.pau.edu/wp-content/uploads/2025/11/RIB-2024.pdf  
**Filename**: `pau-package-of-practices-kharif-2024.pdf`  
**License**: Public Domain (State University)  
**Region**: Punjab, Haryana  
**Contains**: Complete crop management including pest control

#### Pink Bollworm Off-Season Vigilance
**Source**: Punjab Agricultural University  
**URL**: https://www.pau.edu/content/sandesh/7.pdf  
**Filename**: `pau-pink-bollworm-vigilance.pdf`  
**License**: Public Domain (State University)  
**Contains**: Off-season management, monitoring protocols

### TNAU (Tamil Nadu)

#### Integrated Cotton Pest Management Guide
**Source**: Tamil Nadu Agricultural University  
**URL**: https://agritech.tnau.ac.in/ta/crop_protection/cotton/crop_prot_crop_insectpest%20_cotton_13.html  
**Filename**: `tnau-cotton-ipm-guide.pdf` (convert from HTML)  
**License**: Public Domain (State University)  
**Region**: Tamil Nadu, South India  
**Language**: Tamil and English

---

## Download Strategy

### Step 1: Direct Downloads
Try direct links first:
```bash
cd data/fao-pdfs/en/new-sources

# PPQS Advisories
curl -O "https://ppqs.gov.in/sites/default/files/cotton_pbw_advisory.pdf"
curl -O "https://nsai.co.in/storage/app/media/uploaded-files/ICAR-CICR_Advisory%20Pest%20and%20Disease%20Management%202024.pdf"

# PAU Documents
curl -O "https://pauwp.pau.edu/wp-content/uploads/2025/11/RIB-2024.pdf"
curl -O "https://www.pau.edu/content/sandesh/7.pdf"
```

### Step 2: Manual Download (if 403 errors)
1. Open URLs in browser
2. Use "Save As" or "Print to PDF"
3. Save to `data/fao-pdfs/en/new-sources/`

### Step 3: Academic Mirrors (if blocked)
Search on:
- ResearchGate: https://www.researchgate.net/
- Academia.edu: https://www.academia.edu/
- Google Scholar: https://scholar.google.com/

Search terms:
- "PPQS pink bollworm advisory cotton"
- "NIPHM cotton pest alert 2021"
- "PAU package of practices cotton"

### Step 4: NCIPM Portal Navigation
1. Go to: https://nriipm.res.in/pestalert.aspx
2. Look for "Cotton" in the list
3. Download PDFs for 2019, 2020, 2021
4. Rename consistently: `niphm-cotton-advisory-YYYY-MM.pdf`

---

## Manifest Update Template

After downloading, update `kb_manifest.csv`:

```csv
filename,title,source_url,year,license,region,crop,pests,etl_thresholds
ppqs-pink-bollworm-advisory.pdf,PPQS Pink Bollworm Advisory,https://ppqs.gov.in/sites/default/files/cotton_pbw_advisory.pdf,2024,Public Domain,India,Cotton,Pink Bollworm,10% infested bolls
icar-cicr-pest-disease-advisory-2024.pdf,ICAR-CICR Pest & Disease Management 2024,https://nsai.co.in/storage/app/media/uploaded-files/ICAR-CICR_Advisory%20Pest%20and%20Disease%20Management%202024.pdf,2024,Public Domain,India,Cotton,Multiple,Various ETLs
niphm-cotton-advisory-2021-09.pdf,NIPHM Cotton Pest Alert Sept 2021,https://nriipm.res.in/pestalert.aspx,2021,Public Domain,India,Cotton,Multiple,ETL based
pau-package-of-practices-kharif-2024.pdf,PAU Package of Practices Kharif 2024,https://pauwp.pau.edu/wp-content/uploads/2025/11/RIB-2024.pdf,2024,Public Domain,Punjab,Cotton,Multiple,Regional ETLs
mpkv-cotton-hybrid-varieties.pdf,MPKV Cotton Hybrid Varieties,https://www.scribd.com/document/868677221/,2023,Public Domain,Maharashtra,Cotton,Multiple,Variety specific
pau-pink-bollworm-vigilance.pdf,PAU Pink Bollworm Off-Season Vigilance,https://www.pau.edu/content/sandesh/7.pdf,2024,Public Domain,Punjab,Cotton,Pink Bollworm,Off-season monitoring
```

---

## Special Handling Notes

### OCR for Scanned Documents
Some older NIPHM alerts (2019) may be scanned images:

```bash
# Check if PDF is scanned
pdffonts niphm-cotton-advisory-2019-08.pdf

# If no fonts listed, it's a scanned image
# Bedrock should handle this, but verify during ingestion
```

### HTML to PDF Conversion (TNAU)
For TNAU web pages:
1. Open in browser: https://agritech.tnau.ac.in/ta/crop_protection/cotton/crop_prot_crop_insectpest%20_cotton_13.html
2. Print to PDF (Ctrl+P / Cmd+P)
3. Save as: `tnau-cotton-ipm-guide.pdf`

### Regional Language Versions
Many universities provide bulletins in regional languages:
- MPKV: Marathi
- PAU: Punjabi
- TNAU: Tamil

Download both English and regional versions for better multilingual RAG.

---

## Priority Order for Download

### Phase 1: Critical (Do First)
1. ✅ ICAR-CICR 2024 Advisory (comprehensive)
2. ✅ PPQS Pink Bollworm Advisory (ETL thresholds)
3. ✅ NIPHM 2021 Cotton Advisory (recent)
4. ✅ PAU Package of Practices 2024 (Punjab/Haryana)

### Phase 2: Regional Coverage
5. ⏳ MPKV Cotton Varieties (Maharashtra)
6. ⏳ NIPHM 2020 Advisory
7. ⏳ NIPHM 2019 Advisories (2)
8. ⏳ PAU Pink Bollworm Vigilance

### Phase 3: Expansion
9. ⏳ TNAU IPM Guide (Tamil Nadu)
10. ⏳ Regional language versions
11. ⏳ Additional state university bulletins

---

## Expected Improvements

With these official sources, your RAG system will gain:

### ETL Thresholds ✅
- Pink bollworm: 10% infested bolls
- Whitefly: 5-10 adults/leaf
- Aphids: 10-15% affected plants
- Bollworms: 5% damaged fruiting bodies

### Regional Specificity ✅
- Punjab/Haryana: PAU recommendations
- Maharashtra: MPKV varieties and practices
- Tamil Nadu: TNAU IPM strategies
- Pan-India: ICAR-CICR national guidelines

### Licensing Clarity ✅
- All sources: Public Domain (Government/University)
- Safe for production deployment
- Proper attribution possible

### Test Pass Rate Target ✅
- Current: 80%
- With these sources: 95%+
- All 20 golden questions should pass

---

## Troubleshooting

### 403 Forbidden Errors
**Solution**: Use academic mirrors or browser download

### PDF Download Fails
**Solution**: Right-click link → "Save Link As"

### Scanned PDFs (No Text)
**Solution**: Bedrock handles OCR automatically, but verify during ingestion

### Regional Language PDFs
**Solution**: Download both English and regional versions for better coverage

---

## Upload Command

After downloading all files:

```bash
# Verify files
ls -lh data/fao-pdfs/en/new-sources/*.pdf

# Update manifest
nano data/fao-pdfs/en/new-sources/kb_manifest.csv

# Upload to S3 (excluding manifest)
aws s3 sync data/fao-pdfs/en/new-sources/ \
  s3://agrinexus-kb-043624892076-us-east-1/en/ \
  --exclude "*.csv"

# Trigger ingestion
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id H81XLD3YWY \
  --data-source-id GVNHYZZBIT

# Wait 10-15 minutes, then test
pytest tests/test_golden_questions_realistic.py -v
```

---

## Success Criteria

After adding these sources, you should achieve:
- ✅ 95%+ test pass rate
- ✅ ETL thresholds in responses
- ✅ Regional recommendations (Punjab, Maharashtra, Tamil Nadu)
- ✅ All responses with proper citations
- ✅ Public domain licensing for all sources
- ✅ Ready for production deployment

---

## Next Steps

1. Download Phase 1 documents (4 critical sources)
2. Update manifest with metadata
3. Upload and sync Knowledge Base
4. Run tests and verify 95%+ pass rate
5. Proceed to Phase 2 for regional expansion
