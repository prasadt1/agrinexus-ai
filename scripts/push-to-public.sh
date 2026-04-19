#!/usr/bin/env bash
# Guard-rail: push current branch to the PUBLIC remote only after explicit confirmation.
# Workflow B: canonical work lives on PRIVATE (origin should point there); this pushes to `public`.
#
# Usage:
#   ./scripts/push-to-public.sh              # pushes HEAD to public/main
#   ./scripts/push-to-public.sh my-branch    # pushes my-branch to public/main
#
# Requires: git remote named `public` → github.com/prasadt1/agrinexus-ai (or your public URL).

set -euo pipefail
BRANCH="${1:-HEAD}"
if [[ "$BRANCH" == "HEAD" ]]; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
fi

if ! git remote get-url public >/dev/null 2>&1; then
  echo "Error: no git remote named 'public'. Add it, e.g.:" >&2
  echo "  git remote add public git@github.com:prasadt1/agrinexus-ai.git" >&2
  exit 1
fi

PUBLIC_URL="$(git remote get-url public)"
ORIGIN_URL=""
git remote get-url origin >/dev/null 2>&1 && ORIGIN_URL="$(git remote get-url origin)" || true

echo "=== Push to PUBLIC repository ==="
echo "Remote 'public': $PUBLIC_URL"
echo "Remote 'origin': ${ORIGIN_URL:-"(none)"}"
echo "Branch to push:  $BRANCH  →  public/main"
echo ""
echo "Confirm that this branch is safe for the OPEN internet (no secrets, no private-only paths you meant to omit)."
echo ""
read -r -p "Type YES to push: " ans
if [[ "$ans" != "YES" ]]; then
  echo "Aborted."
  exit 1
fi

git push public "$BRANCH:main"

echo "Done. Public main updated from $BRANCH."
