# Scripts Directory

This directory contains both **shared scripts** (tracked in git) and **personal/local scripts** (kept on your machine only).

## Shared Scripts (Tracked in Git)

Scripts actually present in this repo (others may live under `scripts/local/` on your machine):

- `push-to-public.sh` — Type **YES** to run `git push public <branch>:main` (workflow B: treat **private** as the superset repo; review diffs before pushing to **public**)
- `e2e-smoke.sh` — SAM validate + fast pytest + optional KB + web chat curl (see script header)
- `reset-profile.sh` / `delete-user-data.sh` — Non-interactive or interactive DynamoDB user reset
- `clear-nudges.sh` — Delete **NUDGE#** rows for a phone (keeps profile); useful before `demo-nudge-loop.sh`
- `reset-onboard-and-demo.sh` — Reset profile / drive onboarding + optional weather + webhook messages (needs `WEBHOOK_URL`, etc.)
- `demo-nudge-loop.sh` — **One command** demo: first nudge (default **Latur**) → **T+24h** → **T+48h**; uses `demo.env` for `PHONE_NUMBER`. Flags: `--district`, `--interval`, `--reminders-only`
- `demo-nudge-flow.sh`, `demo-nudge-multilang.sh`, `demo-nudge.sh`, `demo-scenario.sh` — Additional demo flows
- `create-bedrock-guardrail.sh` — Create a Bedrock guardrail resource
- `cleanup-internal-scripts.sh`, `remove-internal-docs.sh` — Maintainer cleanup helpers

**Deploy:** use the SAM CLI from the repo root (see **README.md**): `sam build --template-file template-week2.yaml` then `sam deploy --config-file samconfig-week2.toml`.

## Personal Scripts (Keep Local)

Personal scripts for testing, demos, or machine-specific workflows should NOT be committed to git.

### Option A: Use `scripts/local/` folder (Recommended)

```bash
# Create the local folder
mkdir -p scripts/local

# Move your personal script
mv scripts/my-demo-script.sh scripts/local/

# If it was already tracked in git, remove it
git rm --cached scripts/my-demo-script.sh
```

The entire `scripts/local/` folder is ignored via the `**/local/` pattern in `.gitignore`.

### Option B: Use `.local.sh` suffix

```bash
# Rename your script with .local.sh suffix
mv scripts/demo-nudge.sh scripts/demo-nudge.local.sh

# If it was already tracked in git, remove it
git rm --cached scripts/demo-nudge.sh
```

Any file matching `*.local.sh` in the scripts directory (flat or nested) is ignored.

## Examples of Personal Scripts

These types of scripts should be kept local:

- Demo triggers with your phone number
- WhatsApp profile helpers with personal data
- One-off testing scripts
- Machine-specific configurations
- Scripts with API keys or credentials

## Configuration Files

- `demo.env` — **Do not commit** — Local file with `WEBHOOK_URL`, `APP_SECRET`, `PHONE_NUMBER`, etc. Create it yourself; scripts `source` it when present.

## After Moving a Script

If you move a script that was previously tracked:

```bash
# Remove from git tracking (keeps local copy)
git rm --cached scripts/old-script.sh

# Verify it's staged for deletion
git status

# Commit the removal
git commit -m "chore: Move personal script to local"
```

## Best Practices

1. **Never commit credentials** - Use `demo.env` or AWS Secrets Manager
2. **Keep phone numbers private** - Use environment variables or local scripts
3. **Document shared scripts** - Add comments explaining what they do
4. **Test before committing** - Run shared scripts to ensure they work for others
5. **Use meaningful names** — e.g. `reset-onboard-and-demo.sh` rather than `d.sh`

## Need Help?

- Check `.gitignore` to see what patterns are ignored
- Run `git status` to see what's tracked vs untracked
- Use `git rm --cached <file>` to untrack without deleting locally
