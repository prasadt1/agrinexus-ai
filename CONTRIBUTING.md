# Contributing

Thanks for your interest in AgriNexus AI.

This repository is **source-available** (see [LICENSE](LICENSE)). We welcome improvements that help reliability, safety, and documentation for reviewers and builders.

## What we welcome

- **Bug reports** (clear repro steps + expected vs actual)
- **Documentation fixes** (typos, broken links, clearer setup steps)
- **Tests** (fast unit tests, mock-based end-to-end tests)
- **Small reliability improvements** (timeouts, retries, guardrails) that don’t change product behavior

## What requires a licensing conversation

- Commercial deployments for end users
- White-labeling / partner distributions
- Integrations sold as a service (NGO / enterprise / government rollouts)

If that’s your use-case, email **prasad@prasadtilloo.com**.

## How to contribute

1. **Open an issue** describing the change.
2. **Fork** the repo and create a branch.
3. Run fast checks locally:

```bash
python3 -m pytest tests/test_nudge_flow.py tests/test_district_helplines.py tests/test_e2e_happy_path_mocked.py -q
sam validate --template-file template-week2.yaml --lint
```

4. Submit a PR with:
   - **What / why** (1–2 paragraphs)
   - **Test evidence** (what you ran)

## Security / privacy

- Do **not** include real phone numbers, tokens, or secrets in issues or PRs.
- Use placeholders (e.g. `1555123456789`) in docs and tests.
- Keep `scripts/demo.env` and AWS credentials out of git.

