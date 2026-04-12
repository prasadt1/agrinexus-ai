#!/bin/bash
# Remove internal documentation from public repo
# These files should only exist in the private repo

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Remove Internal Documentation from Public Repo         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

echo "⚠️  WARNING: This will remove internal files from public repo!"
echo ""
echo "Files to remove:"
echo "  - IP-PROTECTION-GUIDE.md (reveals IP strategy)"
echo "  - GUARDRAIL-*.md (internal setup)"
echo "  - SECURITY-*.md (security strategy)"
echo "  - COMPETITION-*.md (competition details)"
echo "  - DEPLOYMENT-*.md (internal status)"
echo "  - ISSUES-LOG.md (internal tracking)"
echo "  - AWS-CREDITS-AND-COSTS.md (cost details)"
echo "  - BEFORE-AFTER-COMPARISON.md (internal)"
echo "  - CURSOR-*.md, CLAUDE.md (dev notes)"
echo "  - FINALIST-*.md (competition strategy)"
echo "  - IMPLEMENTATION-VERIFICATION.md (internal)"
echo "  - scripts/setup-ip-protection.sh (reveals strategy)"
echo "  - scripts/redact-sensitive-ip.sh (reveals redaction)"
echo "  - scripts/demo-*.sh (personal demo scripts)"
echo "  - scripts/reset-*.sh (internal testing)"
echo "  - scripts/create-bedrock-guardrail.sh (internal)"
echo ""
echo "These files will remain in:"
echo "  ✅ Private repo (already pushed)"
echo "  ✅ Local backups (if you want)"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Removing internal documentation..."

# Internal strategy and planning docs
git rm IP-PROTECTION-GUIDE.md
git rm GUARDRAIL-SETUP.md
git rm GUARDRAIL-TEST-PLAN.md
git rm SECURITY-HARDENING-PLAN.md
git rm SECURITY-INCIDENT-RESPONSE.md
git rm COMPETITION-FINALIST-BRIEFING.md
git rm CURSOR-IMPLEMENTATION-SUMMARY.md
git rm DEPLOYMENT-STATUS.md
git rm DEPLOYMENT-SUCCESS.md
git rm FINALIST-IMPROVEMENTS.md
git rm IMPLEMENTATION-VERIFICATION.md
git rm ISSUES-LOG.md
git rm AWS-CREDITS-AND-COSTS.md
git rm BEFORE-AFTER-COMPARISON.md
git rm CLAUDE.md

# Internal scripts
git rm scripts/setup-ip-protection.sh
git rm scripts/redact-sensitive-ip.sh
git rm scripts/demo-nudge-flow.sh
git rm scripts/demo-nudge-loop.sh
git rm scripts/demo-nudge-multilang.sh
git rm scripts/demo-nudge.sh
git rm scripts/demo-reset.sh
git rm scripts/demo-scenario.sh
git rm scripts/reset-onboard-and-demo.sh
git rm scripts/reset-profile.sh
git rm scripts/create-bedrock-guardrail.sh

echo ""
echo "✅ Internal files removed from git"
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Commit: git commit -m 'security: Remove internal documentation from public repo'"
echo "  3. Push to public: git push origin main"
echo ""
echo "⚠️  These files still exist in your private repo!"
echo ""
