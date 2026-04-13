## ADR 0001 — Public web demo abuse protection (API throttling + WAF rate limiting)

### Status
Accepted (2026-04-13)

### Context
The AgriNexus AI web demo exposes a **public** API endpoint (`/chat`) without login. Application-layer rate limiting is implemented (per-IP + anonymous `client_id`), but it is **not sufficient** to prevent:

- Bursts that spike Lambda/API Gateway concurrency
- Automated scripts sending high QPS from a single IP
- Cost/risk from sustained probing before the app-layer limiter engages

We want a low-friction demo (no auth) while reducing abuse risk and protecting Bedrock spend.

### Decision
Add **edge-layer controls** in infrastructure:

- **API Gateway stage throttling** on `WebChatApi`:
  - `ThrottlingRateLimit`: `2` req/sec
  - `ThrottlingBurstLimit`: `5`
- **AWS WAFv2 WebACL** associated with the `WebChatApi` stage:
  - **Rate-based rule** (aggregate by IP) as a backstop
  - Limit: **300 requests / 5 minutes**
  - Scoped down to requests whose `UriPath` ends with `/chat`

These controls are implemented in `template-week2.yaml` and deployed with the existing SAM stack.

### Consequences
- **Pros**
  - Reduces impact of single-IP abuse/bursts immediately at the edge
  - Provides CloudWatch WAF metrics + sampled requests for visibility
  - Keeps the demo publicly accessible (no login)
- **Cons / Caveats**
  - Distributed abuse (many IPs) is still possible without stronger identity (captcha/auth)
  - WAF rate rules are evaluated over a fixed **5-minute** window (not hourly/daily)
  - Throttling settings may need tuning if legitimate traffic grows

### Follow-ups (optional)
- Add a “kill switch” flag to temporarily pause the demo without redeploy
- Consider adding a lightweight human check (e.g., Turnstile) if abuse appears

