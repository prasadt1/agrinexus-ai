# ADR 0002: Common Layer Dependency Management

**Date:** 2026-04-15  
**Status:** Accepted  
**Deciders:** Development Team  

## Context

The Common Layer (`src/common-layer/`) provides shared utilities for WhatsApp integration, including the `requests` library for HTTP calls to the WhatsApp Graph API. During deployment, we encountered `Runtime.ImportModuleError: No module named 'requests'` because SAM build was not installing dependencies.

## Problem

Lambda Layers need external dependencies (like `requests`) to be installed in the `python/` directory. Without a `requirements.txt` file, SAM build does not automatically install these dependencies, leading to:

1. Manual `pip install` commands that aren't documented
2. Dependencies that work locally but fail in deployed Lambdas
3. Inconsistent layer builds across deployments

## Decision

**Use `requirements.txt` for all Lambda Layer dependencies and let SAM handle installation automatically.**

### Implementation

1. Created `src/common-layer/requirements.txt`:
   ```
   requests>=2.31.0
   boto3>=1.34.0
   ```

2. SAM automatically installs dependencies during `sam build` when `requirements.txt` exists

3. Layer structure:
   ```
   src/common-layer/
   ├── requirements.txt          # Dependencies
   └── python/
       ├── common/               # Custom modules
       │   ├── whatsapp.py
       │   └── district_helplines.py
       └── [installed packages]  # Auto-installed by SAM
   ```

## Consequences

### Positive
- ✅ Reproducible builds - `sam build` installs dependencies consistently
- ✅ Documented dependencies - `requirements.txt` is the source of truth
- ✅ No manual installation steps required
- ✅ Works in CI/CD pipelines without special setup

### Negative
- ⚠️ Layer size increases with dependencies (requests + dependencies = ~2MB)
- ⚠️ Must rebuild layer when dependencies change

### Neutral
- Layer version increments when dependencies are updated
- All Lambda functions using the layer must be updated to new version

## Alternatives Considered

### 1. Manual pip install (Rejected)
- **Pros:** Quick for local development
- **Cons:** Not reproducible, fails in CI/CD, undocumented

### 2. Vendor dependencies in git (Rejected)
- **Pros:** No build step needed
- **Cons:** Large git repo, version control bloat, security issues

### 3. Separate layer per dependency (Rejected)
- **Pros:** Granular control
- **Cons:** Layer limit (5 per Lambda), management overhead

## Related Decisions
- ADR 0003: WhatsApp Integration via Common Layer
- ADR 0006: AWS X-Ray Tracing

## Notes
- Layer version 13 was the first with proper `requirements.txt`
- Previous versions (1-12) had manually installed dependencies
- This issue surfaced after a `sam build` that didn't preserve manual installs
