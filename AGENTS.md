# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

AgriNexus AI is a 100% serverless AWS application (WhatsApp agricultural advisory chatbot). There is no local web server, no Docker, and no database to run. All compute runs on AWS Lambda; all data lives in DynamoDB/S3/Bedrock.

### AWS credentials

The secrets `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are injected as environment variables. The default region is `us-east-1`. When these env vars are set, boto3 picks them up automatically for both unit tests (with `TABLE_NAME=agrinexus-data`) and integration tests.

### Environment variables for local module loading

Source modules under `src/` read environment variables at import time. For **unit tests** (`test_nudge_flow.py`), only `TABLE_NAME=agrinexus-data` is needed (the AWS secrets handle auth). For **direct module imports** of specific handlers, additional env vars are required:
- `src/webhook/handler.py` → `QUEUE_URL`, `VOICE_QUEUE_URL`, `VERIFY_TOKEN`, `VERIFY_SIGNATURE`
- `src/processor/handler.py` → `KNOWLEDGE_BASE_ID`, `GUARDRAIL_ID`, `GUARDRAIL_VERSION`

### Running tests

- **Local unit tests (no AWS required):** `TABLE_NAME=agrinexus-data python3 -m pytest tests/test_nudge_flow.py -v` — uses mocks/monkeypatch, runs fully offline with dummy AWS credentials.
- **Integration tests (require real AWS credentials):** `python3 -m pytest tests/test_golden_questions.py -v` and `tests/test_golden_questions_realistic.py` call live AWS Bedrock Knowledge Base (KB ID `H81XLD3YWY`). `test_voice_*.py` and `test_vision.py` also call live AWS services (Transcribe, Polly, Bedrock Vision).
- **Expected integration test failures:** Some golden question tests may fail due to RAG response quality (keyword matching), not environment issues. If a test connects to Bedrock and gets a response, the environment is working correctly.

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
