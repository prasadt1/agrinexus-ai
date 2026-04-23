# Issues Log (Resolved)

This file tracks notable issues encountered while building and deploying AgriNexus AI and how they were resolved.

> Note: This is a **public** troubleshooting history intended for judges/reviewers. It avoids secrets, phone numbers, and account-specific details.

## 2026-04-23 — Vision analysis: non-agri images were incorrectly diagnosed

- **Symptom**: UI screenshots / leaf logos / scenery / selfies were sometimes treated as crop photos and diagnosed.
- **Root cause**: The vision flow was optimized for “always return an agronomy answer,” so non-agri images could slip through without a strict eligibility gate.
- **Fix**:
  - Added a **2-stage image eligibility gate** in the WhatsApp pipeline:
    - Classify image as `AGRI_PHOTO | NON_AGRI | EXPLICIT | UNKNOWN`
    - Only run crop diagnosis for `AGRI_PHOTO`
  - Do not save non-agri/explicit images to S3.
- **Verification**:
  - Unit tests around the gating behavior.
  - Redeploy `MessageProcessor` and re-test with non-agri examples (screenshots, logos, scenery).

## 2026-04-xx — Deployment reported “no changes to deploy” for vision fix

- **Symptom**: A deployed fix did not take effect even though code was changed.
- **Root cause**: The initial change was applied in a module that was not used by the deployed Lambda handler.
- **Fix**: Move the fix into the module actually packaged for the `MessageProcessor` Lambda, redeploy.

## 2026-04-xx — Web demo: abuse envelope and rate limiting tuning

- **Symptom**: Risk of public endpoint abuse / unbounded cost.
- **Fix**:
  - Per-IP + per-client-id DynamoDB caps
  - API Gateway throttling
  - WAF rules on the `/chat` endpoint

---

## Adding a new entry

When adding a new entry:

- Include **date**, **symptom**, **root cause**, **fix**, **verification**
- Do not include secrets, tokens, or real phone numbers

