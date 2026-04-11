#!/bin/bash
# AgriNexus AI - IP Protection Setup Script
# This script helps you create a private backup and redact sensitive IP from public repo

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  AgriNexus AI - IP Protection Setup                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Create private repo backup
echo "STEP 1: Create Private Backup Repository"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Go to GitHub: https://github.com/new"
echo "2. Repository name: agrinexus-ai-private"
echo "3. Description: AgriNexus AI - Full Implementation (Private)"
echo "4. Visibility: PRIVATE ⚠️"
echo "5. Click 'Create repository'"
echo ""
read -p "Press ENTER when you've created the private repo..."

echo ""
echo "Adding private remote..."
read -p "Enter your private repo URL (e.g., git@github.com:prasadt1/agrinexus-ai-private.git): " PRIVATE_REPO

git remote add private "$PRIVATE_REPO" 2>/dev/null || echo "Remote 'private' already exists"

echo ""
echo "Pushing full codebase to private repo..."
git push private main

echo ""
echo "✅ Full codebase backed up to private repo!"
echo ""

# Step 2: Identify sensitive files
echo "STEP 2: Files to Redact from Public Repo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The following files contain proprietary IP:"
echo ""
echo "HIGH-VALUE IP (Must Redact):"
echo "  1. src/processor/analyzer.py          - Vision analysis prompts"
echo "  2. src/nudge/nudge_copy.py            - Contextual nudge templates"
echo "  3. src/nudge/bedrock_liner.py         - AI generation logic"
echo "  4. src/common-layer/python/common/district_helplines.py - Curated data"
echo ""
echo "MEDIUM-VALUE IP (Consider Redacting):"
echo "  5. src/processor/handler.py           - RAG prompts (lines 510-530)"
echo "  6. src/nudge/sender.py                - Nudge logic"
echo "  7. src/nudge/reminder.py              - Reminder logic"
echo ""

# Step 3: Create proprietary folder
echo "STEP 3: Create Proprietary Folder (Local Only)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

mkdir -p src/proprietary

echo "Moving sensitive files to src/proprietary/..."
cp src/processor/analyzer.py src/proprietary/analyzer.py.backup
cp src/nudge/nudge_copy.py src/proprietary/nudge_copy.py.backup
cp src/nudge/bedrock_liner.py src/proprietary/bedrock_liner.py.backup
cp src/common-layer/python/common/district_helplines.py src/proprietary/district_helplines.py.backup

echo ""
echo "✅ Backups created in src/proprietary/"
echo ""

# Step 4: Instructions for next steps
echo "STEP 4: Next Steps (Manual)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Run the redaction script to replace sensitive files with stubs:"
echo ""
echo "  ./scripts/redact-sensitive-ip.sh"
echo ""
echo "This will:"
echo "  - Replace proprietary code with stub implementations"
echo "  - Add clear licensing notices"
echo "  - Keep the repo functional for demo purposes"
echo "  - Protect your competitive advantage"
echo ""
echo "After redaction, review changes and commit to public repo."
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✅ IP Protection Setup Complete!                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
