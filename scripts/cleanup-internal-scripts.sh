#!/bin/bash
# Remove internal testing and demo scripts from public repo

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Remove Internal Scripts from Public Repo               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

echo "Scripts to remove (internal testing/demo only):"
echo ""
echo "Testing Scripts:"
echo "  - test-*.sh (all language tests)"
echo "  - e2e-test.sh"
echo "  - interactive-test.sh"
echo "  - trigger-*-test.sh"
echo "  - send-reminder.sh"
echo ""
echo "Demo/Setup Scripts:"
echo "  - demo.env.example (contains personal info)"
echo "  - update-whatsapp-profile*.sh (personal setup)"
echo "  - update-test-expectations.py (internal testing)"
echo ""
echo "Internal Maintenance:"
echo "  - aws-cost-report.sh (internal cost tracking)"
echo "  - rotate-weather-api-key.sh (personal API key)"
echo ""
echo "These scripts will remain in private repo only."
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Removing internal scripts..."

# Testing scripts
git rm scripts/test-english.sh
git rm scripts/test-hindi.sh
git rm scripts/test-marathi.sh
git rm scripts/test-telugu.sh
git rm scripts/test-reminder.sh
git rm scripts/test-whatsapp-profile.sh
git rm scripts/e2e-test.sh
git rm scripts/interactive-test.sh
git rm scripts/trigger-nudge-test.sh
git rm scripts/trigger-test-nudge.sh
git rm scripts/send-reminder.sh

# Demo/setup scripts with personal info
git rm scripts/demo.env.example
git rm scripts/update-whatsapp-profile.sh
git rm scripts/update-whatsapp-profile-pic.sh
git rm scripts/update-test-expectations.py

# Internal maintenance
git rm scripts/aws-cost-report.sh
git rm scripts/rotate-weather-api-key.sh

echo ""
echo "✅ Internal scripts removed"
echo ""
echo "Scripts that remain (deployment/setup only):"
echo "  ✅ deploy-week2.sh - Main deployment"
echo "  ✅ deploy-with-weather.sh - Weather integration"
echo "  ✅ setup-week1.sh - Initial setup"
echo "  ✅ create-cloudwatch-dashboard.sh - Monitoring setup"
echo "  ✅ rebuild-kb-s3-vectors.sh - Knowledge base rebuild"
echo "  ✅ download-official-sources.sh - Data sources"
echo "  ✅ prepare-pest-management-docs.sh - Data prep"
echo "  ✅ upload-fao-pdfs.sh - Data upload"
echo "  ✅ create_s3_vector_resources.py - S3 setup"
echo "  ✅ README.md - Documentation"
echo ""
echo "Next steps:"
echo "  git status"
echo "  git commit -m 'security: Remove internal testing scripts'"
echo "  git push origin main"
echo ""
