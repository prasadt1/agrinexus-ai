#!/bin/bash
# Quick commit script for cleanup

echo "📝 Staging modified files..."
git add .gitignore
git add architecture.md
git add architecture/README.md
git add architecture/diagrams.md
git add src/processor/handler.py
git add src/web-chat/handler.py
git add template-week2.yaml

echo "📝 Staging ADR..."
git add docs/adr/0006-observability-xray-tracing.md

echo "✅ Ready to commit!"
echo ""
echo "Run this to commit:"
echo "  git commit -m 'chore: remove internal files and update architecture docs'"
echo ""
echo "Then push:"
echo "  git push"
