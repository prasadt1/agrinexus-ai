# Scripts Directory

This directory contains both **shared scripts** (tracked in git) and **personal/local scripts** (kept on your machine only).

## Shared Scripts (Tracked in Git)

These are part of the repository and useful for all developers:

- `deploy-week2.sh` - Deploy the SAM stack
- `deploy-with-weather.sh` - Deploy with weather API configuration
- `e2e-test.sh` - End-to-end automated testing
- `reset-profile.sh` - Reset a user profile for re-onboarding
- `clear-nudges.sh` - Delete only **NUDGE#** rows for a phone (keeps profile); use before a fresh `demo-nudge-loop.sh`
- `demo-reset.sh` - Clean all data before demo recording
- `upload-fao-pdfs.sh` - Upload knowledge base documents to S3
- `create-bedrock-guardrail.sh` - Create Bedrock guardrail
- `create-cloudwatch-dashboard.sh` - Create monitoring dashboard
- `demo-nudge-loop.sh` - **One command** demo: first nudge (default district **Latur**) → **T+24h** → **T+48h**; pause **NUDGE_LOOP_INTERVAL_SEC** (default **15s** — time for tap, bot reply, VO). Set `PHONE_NUMBER` in `demo.env`. Flags: `--district`, `--interval`, `--reminders-only` (skip first nudge).

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

- `demo.env` - **NEVER COMMIT** - Contains webhook URL, app secret, phone number
- `demo.env.example` - Template for demo.env (tracked in git)

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
5. **Use meaningful names** - `deploy-week2.sh` is better than `d.sh`

## Need Help?

- Check `.gitignore` to see what patterns are ignored
- Run `git status` to see what's tracked vs untracked
- Use `git rm --cached <file>` to untrack without deleting locally
