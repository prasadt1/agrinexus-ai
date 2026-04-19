# Private (superset) vs public (subset) — workflow B

**Canonical repo (full IP, internal notes, experiments):**  
[github.com/prasadt1/agrinexus-ai-private](https://github.com/prasadt1/agrinexus-ai-private)

**Public repo (subset safe for judges / portfolio / stars):**  
[github.com/prasadt1/agrinexus-ai](https://github.com/prasadt1/agrinexus-ai)

Treat **private as the source of truth**. The public repo should **never** receive commits you have not consciously chosen to expose.

---

## Recommended layout

| Where you work day to day | `origin` points to | Other remote |
|---------------------------|---------------------|--------------|
| Laptop clone A (recommended) | **private** | `public` → public URL |
| Or one clone | **private** | `public` → public URL |

Avoid having **`origin`** = public on the machine where you also commit proprietary material—easy to push to the wrong place.

### Remotes (example)

```bash
git remote -v
# origin    git@github.com:prasadt1/agrinexus-ai-private.git (fetch/push)
# public    git@github.com:prasadt1/agrinexus-ai.git (fetch/push)
```

If your `origin` is still the public URL, repoint it once (example):

```bash
git remote rename origin public
git remote add origin git@github.com:prasadt1/agrinexus-ai-private.git
git fetch origin
git branch -u origin/main main   # if your main should track private
```

Adjust SSH vs HTTPS URLs to match how you authenticate.

---

## What “superset” means in practice

- **Private** may contain **everything** the public repo has, **plus** extra tracked content, e.g.:
  - Internal ADRs, customer pilots, unreleased features
  - Heavier prompt packs, evaluation logs, benchmark data
  - Anything you do **not** want copied or debated in the open
- **Public** receives only commits (or only paths) you are willing to stand behind for **competition / hiring / community**.

Private-only files can live in paths you **never** push to public (e.g. `internal/`, `docs/private/`) **if** your publish step omits them (see below). If you push the same `main` to both remotes without filtering, **both repos get the same tree** — that is no longer a subset.

---

## Ways to publish a subset to public

### 1. Same branch, manual discipline (simplest)

- Develop on `main` in **private** only.
- When `main` is entirely “public-safe”, run:  
  `git push public main:main`
- While building sensitive work, use **feature branches** that merge to `main` only after review, or keep sensitive commits off `main` until squashed/rebased into a clean public-safe history.

**Limitation:** One mistake (`git push public`) exposes everything on that branch.

### 2. Two clones (safest for B)

- **Clone 1:** private only — all work, including `internal/` etc.
- **Clone 2:** public — you **copy or cherry-pick** only what should be public (or run a small sync script with an explicit allowlist).

No accidental push of private-only paths from a unified remote setup.

### 3. Publish branch + allowlist (medium effort)

- On **private**, maintain `main` (full) and a branch `publish/main` that is **only** public-safe changes (merge or cherry-pick).
- `git push public publish/main:main`

Automate with CI on private if you want checks before allowing merge to `publish/main`.

---

## Before every `git push public …`

- [ ] No secrets, API keys, phone numbers, or `samconfig` secrets in the commits you are pushing.
- [ ] No paths you meant to keep private-only (if you use an allowlist sync, re-run the diff).
- [ ] LICENSE / README on public still match your intent.

Optional: run `./scripts/push-to-public.sh` from this repo for a confirmation gate (see script header).

---

## Related

- Public [LICENSE](../LICENSE) — portfolio / evaluation framing; not a substitute for keeping trade secrets off the public remote.
- [README.md](../README.md) — product-facing links and scope.
