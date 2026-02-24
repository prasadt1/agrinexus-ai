# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

AgriNexus AI is a 100% serverless AWS application (WhatsApp agricultural advisory chatbot). There is no local web server, no Docker, and no database to run. All compute runs on AWS Lambda; all data lives in DynamoDB/S3/Bedrock.

### Environment variables for local module loading

Source modules under `src/` read environment variables at import time. To import or test any module locally, export these dummy values first:

```bash
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=testing
export AWS_SECRET_ACCESS_KEY=testing
export TABLE_NAME=agrinexus-data
```

Additional env vars needed for specific modules:
- `src/webhook/handler.py` → `QUEUE_URL`, `VOICE_QUEUE_URL`, `VERIFY_TOKEN`, `VERIFY_SIGNATURE`
- `src/processor/handler.py` → `KNOWLEDGE_BASE_ID`, `GUARDRAIL_ID`, `GUARDRAIL_VERSION`

### Running tests

- **Local unit tests (no AWS required):** `python3 -m pytest tests/test_nudge_flow.py -v` — uses mocks/monkeypatch, runs fully offline.
- **Integration tests (require deployed AWS stack + credentials):** `test_golden_questions.py`, `test_golden_questions_realistic.py`, `test_voice_*.py`, `test_vision.py` all call live AWS services (Bedrock, Transcribe, Polly). They will fail without real AWS credentials and a deployed stack.

### Linting

```bash
black --check src/ tests/
flake8 src/ tests/ --max-line-length 120
mypy src/ --ignore-missing-imports --explicit-package-bases --exclude 'src/weather/'
```

**Known issues (pre-existing, do not fix):**
- `src/weather/handler.py` has a syntax error (`\` continuation) that prevents black formatting and mypy analysis. Exclude it with `--exclude`.
- Many flake8 warnings (W293 whitespace, F401 unused imports, F541 f-string issues) exist across the codebase.

### Deployment

Deployment uses AWS SAM CLI. See `README.md` "Quick Start" section for full deployment instructions. Two SAM stacks must be deployed in order:
1. `template.yaml` or `template-simple.yaml` (infrastructure: DynamoDB, S3, Bedrock KB)
2. `template-week2.yaml` (application: Lambda functions, API Gateway, SQS, Step Functions)
