# Code Review Action Plan

## Critical Issues (Must Fix Before Production)

### 1. VoiceProcessor Lambda Timeout ⚠️ CRITICAL
**Issue:** 60-second polling loop vs 30-second Lambda timeout
**Location:** `src/voice/processor.py:142-188`, `template-week2.yaml`
**Fix:** Increase VoiceProcessor timeout to 90 seconds in template-week2.yaml
**Status:** TODO

### 2. MOCK_WEATHER Default ⚠️ CRITICAL
**Issue:** Defaults to 'true', will send fake weather to real farmers
**Location:** `src/weather/handler.py:22`
**Fix:** Change default from 'true' to 'false'
**Status:** TODO

### 3. Telugu Language Button Missing ⚠️ CRITICAL
**Issue:** Telugu speakers cannot select their language during onboarding
**Location:** `src/processor/handler.py:196, 230-242`
**Fix:** Add Telugu button to onboarding flow
**Status:** TODO

### 4. Polly Engine Parameter Missing ⚠️ CRITICAL
**Issue:** `src/processor/output.py` missing Engine parameter, will fail for neural voices
**Location:** `src/processor/output.py:61-67`
**Fix:** Update to return 3-tuple (voice_id, language_code, engine)
**Status:** TODO

### 5. Image Format Hardcoded to JPEG ⚠️ CRITICAL
**Issue:** PNG and WebP images will fail
**Location:** `src/vision/analyzer.py:108-111`
**Fix:** Detect actual image format before Bedrock call
**Status:** TODO

### 6. PII Logging ⚠️ CRITICAL (GDPR/Privacy)
**Issue:** Phone numbers and message content logged at INFO level
**Location:** `src/webhook/handler.py:97, 146`
**Fix:** Redact PII from logs
**Status:** TODO

## High Priority Issues (Should Fix)

### 7. Duplicate send_whatsapp_message Function
**Issue:** Copy-pasted in 6 files
**Location:** Multiple files
**Fix:** Extract to `src/common/whatsapp.py`
**Status:** TODO

### 8. Duplicate Vision Analyzer
**Issue:** `src/processor/analyzer.py` is identical to `src/vision/analyzer.py`
**Location:** Both files
**Fix:** Remove duplicate, use single source
**Status:** TODO

### 9. Secrets Manager Called on Every Invocation
**Issue:** Adds 100-200ms latency and cost
**Location:** All `send_whatsapp_message` calls
**Fix:** Cache secrets with 5-minute TTL
**Status:** TODO

### 10. No Conversation Context
**Issue:** Multi-turn conversations don't work
**Location:** `src/processor/handler.py:query_bedrock()`
**Fix:** Add sessionId support
**Status:** TODO

### 11. Step Functions No Error Handling
**Issue:** Silent failures with no notification
**Location:** `statemachine/nudge-workflow.asl.json`
**Fix:** Add Retry and Catch blocks
**Status:** TODO

### 12. Model ARN Hardcoded
**Issue:** Must update manually in multiple files
**Location:** `src/processor/handler.py:464`, test files
**Fix:** Move to MODEL_ARN environment variable
**Status:** TODO

## Medium Priority Issues

### 13. Image Messages Block Main Processor
**Issue:** 10-15 second Bedrock Vision calls block SQS queue
**Location:** `src/webhook/handler.py:211-235`
**Fix:** Route to separate vision queue like voice
**Status:** TODO

### 14. Nudge Content Hardcoded to Spray Only
**Issue:** No planting, irrigation, harvest nudges
**Location:** `src/nudge/sender.py:23-36`
**Fix:** Expand template dict for 3-4 activity types
**Status:** TODO

### 15. Weak Behavioral Nudge Content
**Issue:** No social proof, loss aversion, identity framing
**Location:** `src/nudge/sender.py:23-36`
**Fix:** Add behavioral science variants
**Status:** TODO

### 16. Full Table Scan for Locations
**Issue:** Expensive at scale
**Location:** `src/weather/handler.py:36-58`
**Fix:** Use GSI or maintain LOCATIONS registry
**Status:** TODO

## Missing Features (Spec vs Implementation)

### 17. Sub-District Targeting
**Issue:** Only district-level, not sub-district
**Location:** `src/weather/handler.py`, `src/processor/handler.py`
**Status:** MISSING FEATURE

### 18. Pest Outbreak Aggregation
**Issue:** No farmer pest report aggregation
**Location:** Entirely missing
**Status:** MISSING FEATURE

### 19. Photo Verification of Practices
**Issue:** No spraying/planting verification
**Location:** `src/vision/analyzer.py`
**Status:** MISSING FEATURE

### 20. Fraud Detection for Stock Photos
**Issue:** No fraud detection implemented
**Location:** `src/vision/analyzer.py`
**Status:** MISSING FEATURE

### 21. Swahili/Kikuyu Dialect Support
**Issue:** India-only, no Africa dialects
**Location:** Entire codebase
**Status:** MISSING FEATURE

## Test Coverage Issues

### 22. Vision Tests Not Pytest Compatible
**Issue:** CLI script, not pytest test
**Location:** `tests/test_vision.py`
**Status:** TODO

### 23. Missing Unit Tests
**Issue:** No tests for webhook, processor onboarding
**Location:** Multiple files
**Status:** TODO

## Execution Plan

### Phase 1: Critical Fixes (Day 1-2)
- [ ] Fix 1: VoiceProcessor timeout
- [ ] Fix 2: MOCK_WEATHER default
- [ ] Fix 3: Telugu button
- [ ] Fix 4: Polly Engine parameter
- [ ] Fix 5: Image format detection
- [ ] Fix 6: PII logging redaction

### Phase 2: High Priority (Day 3-5)
- [ ] Fix 7: Consolidate send_whatsapp_message
- [ ] Fix 8: Remove duplicate analyzer
- [ ] Fix 9: Cache Secrets Manager
- [ ] Fix 10: Add conversation context
- [ ] Fix 11: Step Functions error handling
- [ ] Fix 12: Model ARN to env var

### Phase 3: Medium Priority (Week 2)
- [ ] Fix 13-16: Performance and content improvements

### Phase 4: Missing Features (Future Sprints)
- [ ] Features 17-21: Spec alignment

### Phase 5: Test Coverage (Ongoing)
- [ ] Fixes 22-23: Improve test suite

## Notes

- **Production Readiness:** After Phase 1 (6 critical fixes), system is viable for controlled pilot
- **Estimated Effort:** Phase 1 = 1-2 days, Phase 2 = 3-4 days
- **Risk Level:** HIGH until Phase 1 complete, MEDIUM after Phase 1
- **Deployment Strategy:** Fix, test, deploy incrementally - don't batch all fixes

## Success Criteria

- [ ] All voice messages process successfully (no timeouts)
- [ ] Real weather data used in production
- [ ] Telugu farmers can onboard
- [ ] Neural voices work correctly
- [ ] PNG/WebP images process correctly
- [ ] No PII in CloudWatch logs
- [ ] System ready for 100-farmer pilot
