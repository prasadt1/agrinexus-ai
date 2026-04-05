# WhatsApp production number cutover

Use this checklist when moving from a **Meta test number** to a **production WhatsApp Business number** (e.g. new eSIM, new country code). The application does **not** hardcode the business phone number; it uses **Secrets Manager** plus Meta’s **Phone number ID** and **access token**.

---

## 1. Before you start

- [ ] **eSIM activated** and the number can receive **SMS or voice OTP** (required for Meta / carrier verification).
- [ ] You have access to **[Meta Business Suite](https://business.facebook.com/)** and the **WhatsApp** section for your app.
- [ ] You know your **AWS account** and can edit **Secrets Manager** and (if needed) redeploy Lambdas.

---

## 2. Meta / WhatsApp Business registration (high level)

Steps vary slightly by region; follow Meta’s current wizard. In general:

1. Create or select a **Business portfolio** and **WhatsApp Business Account (WABA)**.
2. Add the **new phone number** and complete **business verification** if Meta asks for it.
3. In **Meta for Developers**, open your **app** → **WhatsApp** → link the **same** app to this WABA and the new number.
4. Copy for later:
   - **Phone number ID** (numeric string, used in Graph API paths — not the same as the display number).
   - **Temporary** or **long-lived** system user **access token** with `whatsapp_business_messaging` (and any other scopes your integration uses).
5. **Webhook** (see section 4): subscribe `messages` (and other fields you already use) to your **existing** API Gateway webhook URL unless you intentionally change endpoints.

**Template reuse:** Approved templates (Hindi, English, Telugu, Marathi) are tied to the **WABA**. If the new number is on the **same** WABA as the test line, you can **reuse** the same template **names** — no new submission. If you create a **new** WABA, you must **recreate** templates there and wait for approval again.

---

## 3. AWS Secrets Manager — update these values

Secret names are fixed in SAM (`template-week2.yaml`) and in [`src/common-layer/python/common/whatsapp.py`](../src/common-layer/python/common/whatsapp.py).

| Secret name | What to put | When it changes |
|-------------|-------------|-----------------|
| `agrinexus/whatsapp/phone-number-id` | **New** Phone number ID from Meta | **Always** when switching sender number |
| `agrinexus/whatsapp/access-token` | Current long-lived (or rotating) access token | When Meta rotates token or you switch app/WABA |
| `agrinexus/whatsapp/app-secret` | App secret for **HMAC** verification of incoming webhooks | Usually **unchanged** if using the **same** Meta app |
| `agrinexus/whatsapp/verify-token` | String you configure for webhook verification GET | Only if you **change** the verify token in Meta’s webhook settings |

**How to update (CLI example):**

```bash
aws secretsmanager put-secret-value \
  --secret-id agrinexus/whatsapp/phone-number-id \
  --secret-string "YOUR_NEW_PHONE_NUMBER_ID"

aws secretsmanager put-secret-value \
  --secret-id agrinexus/whatsapp/access-token \
  --secret-string "YOUR_NEW_ACCESS_TOKEN"
```

Repeat for `app-secret` and `verify-token` only if those values changed.

**Credential cache:** Lambdas cache WhatsApp credentials for **5 minutes** ([`CACHE_TTL_SECONDS`](../src/common-layer/python/common/whatsapp.py)). After updating secrets, wait up to ~5 minutes **or** trigger new Lambda invocations so fresh secrets load.

---

## 4. Webhook URL

- [ ] In Meta Developer → **WhatsApp** → **Configuration**, set the **Callback URL** to your **existing** API Gateway webhook (same as today unless you deploy a new stack).
- [ ] Set **Verify token** to match **`agrinexus/whatsapp/verify-token`** exactly.
- [ ] Click **Verify and save**. Fix DNS/API Gateway permissions if verification fails.

Webhook handler: [`src/webhook/handler.py`](../src/webhook/handler.py) (`VERIFY_TOKEN_SECRET`, `APP_SECRET_NAME`).

---

## 5. Code and configuration (usually no code change)

| Item | Action |
|------|--------|
| Lambda / SAM | **No change** required for “new number” if secret **names** stay the same. |
| Nudge **template name** | Default in SAM: `weather_nudge_spray` (`NUDGE_TEMPLATE_NAME`). Must match an **approved** template name in the **same** WABA. |
| `USE_NUDGE_TEMPLATE` | If templates are not ready in a new WABA, you can set `false` and rely on session messages where policy allows (only for development windows — check Meta rules). |

Optional: update [`scripts/demo.env`](../scripts/demo.env) (gitignored) **`PHONE_NUMBER`** to the **recipient** phone you use for manual tests — that is the **farmer/test handset**, not the business number.

---

## 6. Verification checklist (after cutover)

- [ ] **GET** webhook verification succeeds in Meta (green check).
- [ ] Send a **text** message to the business number from a test phone → **200** from webhook → message appears in **CloudWatch** for `agrinexus-webhook-*` / processor.
- [ ] **Outbound** reply works (processor sends via Graph `/{phone-number-id}/messages`).
- [ ] **Voice note** (optional): confirm media download + Transcribe path.
- [ ] **Nudge template** (if enabled): trigger a test nudge or use a sandbox flow; confirm template sends in **hi / mr / te / en** as configured.

**Useful logs:**

```bash
aws logs tail /aws/lambda/agrinexus-webhook-dev --follow
aws logs tail /aws/lambda/agrinexus-processor-dev --follow
```

(Replace `dev` with your `Environment`.)

---

## 7. Troubleshooting

| Symptom | Things to check |
|---------|------------------|
| `401` / `OAuth` errors on send | Access token expired or wrong; **Phone number ID** does not belong to token’s WABA. |
| Webhook never fires | Wrong callback URL; app not in **Live** mode if required; signature secret mismatch (`app-secret`). |
| Template send fails | Template name / language mismatch; template not approved on **this** WABA; sending outside allowed window for marketing templates. |
| Old number still “used” after secret update | Wait for **credential cache** TTL or new cold starts. |

---

## 8. References

- [README — WhatsApp secrets](../README.md) (search “Secrets Manager”).
- [CLAUDE.md](../CLAUDE.md) — webhook, secrets names, test scripts.
- Graph API base used in code: `https://graph.facebook.com/v22.0/{phone_number_id}/messages`

---

## 9. Rollback

If you must revert to the previous number:

1. Restore previous values in **`phone-number-id`** and **`access-token`** (from a secure backup).
2. In Meta, ensure the webhook and app still point at the intended WABA/number.

Keep old secret values only in a **password manager** or **encrypted** backup — not in git.
