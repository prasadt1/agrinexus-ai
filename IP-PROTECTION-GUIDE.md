# AgriNexus AI - IP Protection Guide

**Status**: Ready to Execute  
**Strategy**: Hybrid Public/Private Repository Approach  
**Goal**: Protect competitive advantage while maintaining public portfolio

---

## Overview

This guide implements a **two-repository strategy**:

1. **Public Repo** (`agrinexus-ai`) - Portfolio/demo with redacted IP
2. **Private Repo** (`agrinexus-ai-private`) - Full implementation with all proprietary code

---

## What Gets Protected

### High-Value IP (Must Redact)

| File | Contains | Why Protect |
|------|----------|-------------|
| `src/processor/analyzer.py` | Vision analysis prompts | Optimized prompts for agricultural image analysis |
| `src/nudge/nudge_copy.py` | Contextual nudge templates | District/crop-specific behavioral messaging |
| `src/nudge/bedrock_liner.py` | AI generation logic | Prompt engineering for context hints |
| `src/common-layer/python/common/district_helplines.py` | Curated helpline data | Manually researched KVK/agriculture office contacts |

### Medium-Value IP (Consider Redacting)

| File | Contains | Decision |
|------|----------|----------|
| `src/processor/handler.py` | RAG prompts (lines 510-530) | Keep with generic prompts |
| `src/nudge/sender.py` | Nudge orchestration | Keep (architecture visible) |
| `src/nudge/reminder.py` | Reminder logic | Keep (architecture visible) |

### What Stays Public

- ✅ Architecture and infrastructure code
- ✅ Lambda handlers (with generic prompts)
- ✅ DynamoDB schema
- ✅ SAM templates
- ✅ Deployment scripts
- ✅ Documentation and diagrams

---

## Implementation Steps

### Step 1: Create Private Backup

```bash
# Run the setup script
./scripts/setup-ip-protection.sh
```

This will:
1. Guide you to create a private GitHub repo
2. Add it as a remote named `private`
3. Push your full codebase to the private repo
4. Create local backups in `src/proprietary/`

### Step 2: Redact Sensitive IP

```bash
# Run the redaction script
./scripts/redact-sensitive-ip.sh
```

This will:
1. Replace proprietary files with stub implementations
2. Add clear licensing notices to stubs
3. Update `.gitignore` to exclude backups
4. Keep the system functional for demo purposes

### Step 3: Review and Test

```bash
# Review the stub files
cat src/processor/analyzer.py
cat src/nudge/nudge_copy.py
cat src/nudge/bedrock_liner.py
cat src/common-layer/python/common/district_helplines.py

# Test basic functionality (optional)
sam build --template-file template-week2.yaml
# Don't deploy - just verify it builds
```

### Step 4: Commit to Public Repo

```bash
# Stage the changes
git add .

# Commit with clear message
git commit -m "security: Redact proprietary IP from public repo

- Replaced vision prompts with generic stub
- Replaced nudge templates with generic examples
- Replaced AI generation logic with stub
- Replaced curated helpline data with generic contacts
- Full implementation remains in private repo
- Stubs include licensing contact information"

# Push to public repo
git push origin main
```

---

## Repository Structure After Redaction

### Public Repo (`agrinexus-ai`)
```
agrinexus-ai/
├── src/
│   ├── processor/
│   │   ├── analyzer.py          # ⚠️ STUB - Generic implementation
│   │   └── handler.py           # ✅ PUBLIC - Generic RAG prompts
│   ├── nudge/
│   │   ├── nudge_copy.py        # ⚠️ STUB - Generic templates
│   │   ├── bedrock_liner.py     # ⚠️ STUB - Feature disabled
│   │   ├── sender.py            # ✅ PUBLIC - Architecture visible
│   │   └── reminder.py          # ✅ PUBLIC - Architecture visible
│   └── common-layer/
│       └── python/common/
│           └── district_helplines.py  # ⚠️ STUB - Generic data
├── LICENSE                      # ✅ Source-available license
├── README.md                    # ✅ Portfolio documentation
└── architecture.md              # ✅ System design
```

### Private Repo (`agrinexus-ai-private`)
```
agrinexus-ai-private/
├── src/
│   ├── processor/
│   │   ├── analyzer.py          # ✅ FULL - Proprietary prompts
│   │   └── handler.py           # ✅ FULL - Optimized RAG
│   ├── nudge/
│   │   ├── nudge_copy.py        # ✅ FULL - All templates
│   │   ├── bedrock_liner.py     # ✅ FULL - AI generation
│   │   ├── sender.py            # ✅ FULL - Complete logic
│   │   └── reminder.py          # ✅ FULL - Complete logic
│   └── common-layer/
│       └── python/common/
│           └── district_helplines.py  # ✅ FULL - Curated data
└── ... (everything else)
```

### Local Backups (`src/proprietary/` - Not in Git)
```
src/proprietary/
├── analyzer.py.backup
├── nudge_copy.py.backup
├── bedrock_liner.py.backup
└── district_helplines.py.backup
```

---

## Working with Two Repos

### Daily Development (Private Repo)

```bash
# Work on private repo
git checkout main
# Make changes to full implementation
git add .
git commit -m "feat: Improve vision prompts"
git push private main
```

### Updating Public Repo (Selective)

```bash
# If you want to update public repo with non-sensitive changes
# (e.g., architecture docs, deployment scripts)

# Make changes
git add README.md architecture.md
git commit -m "docs: Update architecture diagram"
git push origin main  # Public repo
```

### Syncing Infrastructure Changes

```bash
# If you update SAM templates or infrastructure
# (these are safe to share publicly)

git add template-week2.yaml
git commit -m "infra: Update Lambda timeout"
git push origin main   # Public
git push private main  # Private
```

---

## What Each Stub Does

### 1. `analyzer.py` (Vision Stub)

**Public Version**:
- Returns generic "send clear photo" message
- Shows function signatures
- Documents what production version does
- Includes licensing contact

**Private Version**:
- Sophisticated vision analysis prompts
- Multi-language responses
- Confidence scoring
- IPM-style recommendations

### 2. `nudge_copy.py` (Nudge Templates Stub)

**Public Version**:
- Generic weather message
- Basic structure visible
- Documents template variations
- Includes licensing contact

**Private Version**:
- 12 district-specific templates
- 8 crop-specific variations
- Weather-aware phrasing
- Cultural context adaptation

### 3. `bedrock_liner.py` (AI Generation Stub)

**Public Version**:
- Feature disabled by default
- Returns empty string
- Documents capability
- Includes licensing contact

**Private Version**:
- Bedrock Haiku integration
- Context-aware hint generation
- Cost-optimized prompts

### 4. `district_helplines.py` (Helpline Data Stub)

**Public Version**:
- Generic Kisan Call Centre only
- Basic keyword matching
- Structure visible
- Includes licensing contact

**Private Version**:
- Comprehensive KVK contacts
- District agriculture offices
- Pesticide dealer information
- Emergency helplines

---

## Legal Protection

### What's Protected

1. **Copyright** - LICENSE file covers all code
2. **Trade Secrets** - Proprietary prompts and data not in public repo
3. **Source-Available License** - Prohibits commercial use without permission

### What's Not Protected

- Architecture and design patterns (visible in public repo)
- Infrastructure code (SAM templates, deployment scripts)
- General approach (behavioral nudges, RAG, etc.)

### If Someone Copies

**They Get**:
- System architecture
- Infrastructure setup
- Generic implementations
- No competitive advantage

**They Don't Get**:
- Optimized prompts
- Curated data
- Behavioral messaging templates
- District-specific knowledge

---

## Maintenance

### Adding New Features

**If feature contains proprietary IP**:
1. Develop in private repo
2. Create stub for public repo
3. Push to both repos separately

**If feature is infrastructure/architecture**:
1. Develop in either repo
2. Push to both repos

### Updating Documentation

**Public repo**: Update freely (portfolio value)  
**Private repo**: Keep in sync with public

---

## Emergency: Accidental Exposure

If you accidentally push sensitive code to public repo:

```bash
# 1. Remove the sensitive file
git rm --cached path/to/sensitive/file.py

# 2. Commit the removal
git commit -m "security: Remove accidentally exposed file"

# 3. Push to public
git push origin main

# 4. Contact GitHub support to purge from history (if needed)
# https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
```

---

## FAQ

**Q: Can I make the entire repo private?**  
A: Yes, but you lose portfolio visibility. Hybrid approach is better.

**Q: What if someone forks the public repo before redaction?**  
A: They get the full code. That's why we do this BEFORE competition submission.

**Q: Can I share private repo with investors/partners?**  
A: Yes, add them as collaborators on GitHub.

**Q: What about the LICENSE file?**  
A: It's in both repos. Prohibits commercial use without permission.

**Q: Do stubs break the system?**  
A: No. Stubs provide basic functionality. Full features require private code.

---

## Contact

For questions about IP protection strategy:  
**Prasad Tilloo** - prasad@prasadtilloo.com

---

**Last Updated**: April 7, 2026  
**Status**: Ready to Execute
