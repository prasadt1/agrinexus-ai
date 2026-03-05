# Code Review Instructions for Claude Code

## Overview

This document provides detailed instructions for conducting a thorough code review of the AgriNexus AI system implementation. Your task is to validate that the codebase correctly implements the core features: WhatsApp messaging, behavioral nudge engine, voice processing, image analysis, and local dialect support.

## Context

AgriNexus AI is a serverless AWS application that provides agricultural advisory services to smallholder farmers via WhatsApp. The system combines:
- **WhatsApp Integration:** Message handling, media processing, conversation management
- **Behavioral Nudge Engine:** Timed interventions, reminder sequences, practice adoption tracking
- **Voice Processing:** Local dialect speech-to-text and text-to-speech via Amazon Bedrock
- **Image Analysis:** Pest/disease identification and photo verification using Bedrock Vision
- **Hyperlocal Data:** Weather and pest outbreak alerts at sub-district level

## Files to Review

### Core Application Code (Primary Focus)
1. **WhatsApp Integration:**
   - `src/webhook/handler.py` - WhatsApp webhook handler, message routing
   - `template.yaml` / `template-week2.yaml` - API Gateway and Lambda configuration

2. **Message Processing:**
   - `src/processor/handler.py` - Main message processing logic
   - `src/processor/analyzer.py` - RAG query processing with Bedrock Knowledge Base
   - `src/processor/output.py` - Response formatting and delivery

3. **Voice Processing:**
   - `src/voice/processor.py` - Voice message transcription (Transcribe)
   - `src/voice/output.py` - Text-to-speech conversion (Polly)

4. **Image Analysis:**
   - `src/vision/analyzer.py` - Pest identification and photo verification (Bedrock Vision)

5. **Behavioral Nudge Engine:**
   - `src/nudge/detector.py` - Nudge trigger detection and scheduling
   - `src/nudge/sender.py` - Nudge message delivery
   - `src/nudge/reminder.py` - Reminder sequence management
   - `statemachine/nudge-workflow.asl.json` - Step Functions workflow

6. **Weather Integration:**
   - `src/weather/handler.py` - Weather data fetching and alerts

7. **Infrastructure:**
   - `template.yaml` - Main SAM template (DynamoDB, S3, Bedrock KB)
   - `template-week2.yaml` - Application SAM template (Lambdas, SQS, Step Functions)

### Test Files (Validation Focus)
8. `tests/test_voice_pipeline.py` - Voice processing tests
9. `tests/test_vision.py` - Image analysis tests
10. `tests/test_nudge_flow.py` - Nudge engine tests
11. `tests/test_golden_questions.py` - RAG query tests

## Review Objectives

### 1. WhatsApp Integration Validation
**Goal:** Ensure WhatsApp webhook handling, message routing, and media processing work correctly.

**Review Checklist:**
- [ ] Webhook verification is implemented correctly (VERIFY_TOKEN)
- [ ] Message signature validation is secure (VERIFY_SIGNATURE)
- [ ] Text messages are routed to processor queue
- [ ] Voice messages are routed to voice queue
- [ ] Image messages are routed to vision analyzer
- [ ] Media download from WhatsApp works correctly
- [ ] Response messages are sent back to WhatsApp API
- [ ] Error handling for failed message delivery
- [ ] Rate limiting and retry logic for WhatsApp API

**Specific Validations:**
- **Webhook Handler:** Does `src/webhook/handler.py` validate signatures and route messages correctly?
- **Queue Integration:** Are SQS queues configured correctly in `template-week2.yaml`?
- **Media Handling:** Does the system download and process voice/image files from WhatsApp?
- **Response Delivery:** Are responses sent back to the correct WhatsApp conversation?

### 2. Behavioral Nudge Engine Validation
**Goal:** Ensure the nudge system detects triggers, schedules interventions, and tracks responses.

**Review Checklist:**
- [ ] Nudge triggers are detected from farmer messages (pest alerts, weather events)
- [ ] Nudge sequences are scheduled correctly (initial, reminder_1, reminder_2)
- [ ] Nudges are sent at optimal times based on crop calendar
- [ ] Farmer responses to nudges are tracked in DynamoDB
- [ ] Photo verification requests are sent after nudges
- [ ] Practice adoption is measured through photo submissions
- [ ] Step Functions workflow orchestrates nudge sequences
- [ ] Nudge content uses behavioral science principles (social proof, loss aversion)
- [ ] Nudges are personalized to farmer context (crops, location, language)

**Specific Validations:**
- **Nudge Detector:** Does `src/nudge/detector.py` identify when to send nudges?
- **Nudge Sender:** Does `src/nudge/sender.py` deliver messages via WhatsApp?
- **Reminder Logic:** Does `src/nudge/reminder.py` schedule follow-up messages?
- **Step Functions:** Does `statemachine/nudge-workflow.asl.json` orchestrate sequences correctly?
- **Data Tracking:** Are nudge responses and photo verifications stored in DynamoDB?

### 3. Voice Processing Validation
**Goal:** Ensure voice messages are transcribed and responses are converted to speech in local dialects.

**Review Checklist:**
- [ ] Voice messages are downloaded from WhatsApp
- [ ] Audio files are transcribed using Amazon Transcribe
- [ ] Local dialect support is configured (language codes)
- [ ] Transcribed text is processed by RAG system
- [ ] Response text is converted to speech using Amazon Polly
- [ ] Voice responses are sent back via WhatsApp
- [ ] Conversation context is maintained across voice interactions
- [ ] Error handling for transcription failures
- [ ] Audio format conversion if needed (WhatsApp formats)

**Specific Validations:**
- **Voice Processor:** Does `src/voice/processor.py` transcribe voice messages correctly?
- **Voice Output:** Does `src/voice/output.py` generate speech in local dialects?
- **Dialect Support:** Are language codes configured for target dialects (Swahili, Kikuyu, Hindi, etc.)?
- **Integration:** Does voice processing integrate with the main message processor?
- **Quality:** Are transcription and speech quality acceptable for farmer use?

### 4. Image Analysis Validation
**Goal:** Ensure pest identification and photo verification work correctly using Bedrock Vision.

**Review Checklist:**
- [ ] Image messages are downloaded from WhatsApp
- [ ] Images are analyzed using Amazon Bedrock Vision
- [ ] Pest/disease identification returns accurate results
- [ ] Photo verification validates farmer practices (spraying, planting, etc.)
- [ ] Confidence scores are calculated for identifications
- [ ] Fraud detection identifies stock photos or incorrect submissions
- [ ] Verification results are stored with timestamps and GPS metadata
- [ ] Corrective guidance is provided for incorrect practices
- [ ] Image analysis results are sent back to farmer via WhatsApp

**Specific Validations:**
- **Vision Analyzer:** Does `src/vision/analyzer.py` use Bedrock Vision correctly?
- **Pest Identification:** Can the system identify common pests (fall armyworm, etc.)?
- **Photo Verification:** Can the system validate farming practices from photos?
- **Fraud Detection:** Does the system detect stock photos or old images?
- **Response Quality:** Are identification results clear and actionable for farmers?

### 5. RAG Query Processing Validation
**Goal:** Ensure agricultural queries are answered correctly using Bedrock Knowledge Base.

**Review Checklist:**
- [ ] Farmer queries are processed by Bedrock Knowledge Base
- [ ] RAG retrieves relevant information from agricultural documents
- [ ] Responses are accurate and contextually appropriate
- [ ] Responses are formatted for WhatsApp delivery
- [ ] Guardrails prevent harmful or incorrect advice
- [ ] Knowledge base includes pest management, crop advisory, weather guidance
- [ ] Query processing handles local dialect variations
- [ ] Response quality is validated with golden question tests
- [ ] Conversation context is maintained across multiple queries

**Specific Validations:**
- **Processor Handler:** Does `src/processor/handler.py` route queries to Bedrock KB?
- **Analyzer:** Does `src/processor/analyzer.py` retrieve relevant information?
- **Output Formatter:** Does `src/processor/output.py` format responses correctly?
- **Knowledge Base:** Is the KB populated with agricultural documents (FAO PDFs, etc.)?
- **Test Coverage:** Do `tests/test_golden_questions.py` validate response quality?

### 6. Hyperlocal Data Integration Validation
**Goal:** Ensure weather and pest data are integrated at sub-district level.

**Review Checklist:**
- [ ] Weather data is fetched from external API
- [ ] Weather alerts are sent to farmers in affected sub-districts
- [ ] Pest outbreak data is aggregated from farmer reports
- [ ] Pest alerts are sent to farmers in affected areas within 24 hours
- [ ] Geographic resolution is sub-district level (not district-wide)
- [ ] Weather data correlates with optimal planting/treatment timing
- [ ] Proactive alerts are sent when conditions favor pest outbreaks
- [ ] Farmer location data is stored and used for targeting
- [ ] Alert relevance is higher than district-level generic advice

**Specific Validations:**
- **Weather Handler:** Does `src/weather/handler.py` fetch and process weather data?
- **Geographic Targeting:** Are alerts sent to farmers in specific sub-districts?
- **Pest Aggregation:** Does the system aggregate pest reports by location?
- **Alert Timeliness:** Are alerts sent within 24 hours of detection?
- **Data Quality:** Is weather/pest data accurate and up-to-date?

### 7. Local Dialect Support Validation
**Goal:** Ensure the system supports multiple local dialects for voice and text.

**Review Checklist:**
- [ ] Dialect configuration is defined (language codes, voice IDs)
- [ ] Transcribe supports target dialects (Swahili, Kikuyu, Hindi, etc.)
- [ ] Polly supports target dialects for speech synthesis
- [ ] Bedrock Knowledge Base handles dialect variations in queries
- [ ] Responses are generated in the farmer's preferred dialect
- [ ] Dialect preference is stored per farmer in DynamoDB
- [ ] Voice quality is acceptable for each supported dialect
- [ ] Text responses use appropriate dialect-specific terminology
- [ ] Onboarding flow allows farmers to select their dialect

**Specific Validations:**
- **Configuration:** Are dialect settings in environment variables or config files?
- **Voice Processing:** Do Transcribe and Polly support all target dialects?
- **RAG Processing:** Does Bedrock KB handle dialect variations correctly?
- **User Preference:** Is dialect preference stored and respected?
- **Test Coverage:** Are dialect-specific tests included?

## Critical Issues to Identify

### High Priority (Must Fix)
1. **Security Vulnerabilities:** Webhook signature validation, API key exposure, data encryption
2. **Functional Bugs:** Message routing failures, voice/image processing errors, nudge delivery issues
3. **Data Loss:** Missing error handling, failed message retries, incomplete data storage
4. **Integration Failures:** WhatsApp API errors, Bedrock service failures, SQS queue issues
5. **Performance Issues:** Slow response times, Lambda timeouts, memory limits

### Medium Priority (Should Fix)
1. **Code Quality:** Duplicate code, unclear variable names, missing comments
2. **Error Handling:** Incomplete try-catch blocks, generic error messages, no logging
3. **Test Coverage:** Missing tests for core features, no integration tests, outdated test data
4. **Configuration Issues:** Hard-coded values, missing environment variables, unclear settings
5. **Scalability Concerns:** Inefficient database queries, unbounded loops, resource leaks

### Low Priority (Nice to Have)
1. **Code Organization:** Better file structure, separation of concerns, modular design
2. **Documentation:** Missing docstrings, unclear README, no architecture diagrams
3. **Optimization:** Faster algorithms, reduced API calls, caching strategies
4. **Monitoring:** Better logging, CloudWatch metrics, alerting setup

## Review Process

### Step 1: Understand System Architecture (30-45 minutes)
1. Read `README.md` and `AGENTS.md` for system overview
2. Review `template.yaml` and `template-week2.yaml` for infrastructure
3. Understand the message flow: WhatsApp → Webhook → Processor → Response
4. Identify key components: webhook, processor, voice, vision, nudge, weather
5. Review DynamoDB schema and data models

### Step 2: Review WhatsApp Integration (20-30 minutes)
1. Check `src/webhook/handler.py` for webhook verification and message routing
2. Verify signature validation and security measures
3. Check message type handling (text, voice, image)
4. Review SQS queue integration for async processing
5. Test error handling for failed message delivery

### Step 3: Review Behavioral Nudge Engine (30-40 minutes)
1. Check `src/nudge/detector.py` for trigger detection logic
2. Review `src/nudge/sender.py` for message delivery
3. Check `src/nudge/reminder.py` for reminder scheduling
4. Review `statemachine/nudge-workflow.asl.json` for workflow orchestration
5. Verify nudge content uses behavioral science principles
6. Check DynamoDB tracking of nudge responses

### Step 4: Review Voice Processing (20-30 minutes)
1. Check `src/voice/processor.py` for transcription logic
2. Review `src/voice/output.py` for speech synthesis
3. Verify dialect support configuration (language codes, voice IDs)
4. Check audio file handling (download, format conversion)
5. Test voice quality with sample audio files

### Step 5: Review Image Analysis (20-30 minutes)
1. Check `src/vision/analyzer.py` for Bedrock Vision integration
2. Review pest identification logic and confidence scoring
3. Check photo verification logic for practice validation
4. Verify fraud detection for stock photos
5. Test with sample pest images

### Step 6: Review RAG Query Processing (20-30 minutes)
1. Check `src/processor/handler.py` for query routing
2. Review `src/processor/analyzer.py` for Bedrock KB integration
3. Check `src/processor/output.py` for response formatting
4. Verify guardrails prevent harmful advice
5. Review golden question tests for response quality

### Step 7: Review Hyperlocal Data Integration (15-20 minutes)
1. Check `src/weather/handler.py` for weather data fetching
2. Verify geographic targeting at sub-district level
3. Check pest outbreak aggregation logic
4. Review alert timeliness (within 24 hours)

### Step 8: Review Test Coverage (20-30 minutes)
1. Check `tests/test_voice_pipeline.py` for voice tests
2. Review `tests/test_vision.py` for image analysis tests
3. Check `tests/test_nudge_flow.py` for nudge engine tests
4. Review `tests/test_golden_questions.py` for RAG tests
5. Identify missing test coverage

### Step 9: Identify Issues and Recommendations (30-40 minutes)
1. Categorize issues by priority (high/medium/low)
2. For each issue, provide specific file/line reference
3. Suggest concrete fixes with code examples if possible
4. Highlight security vulnerabilities and performance issues

## Output Format

Please provide your review in the following format:

```markdown
# AgriNexus Differentiation Strategy Code Review

## Executive Summary
[2-3 paragraphs summarizing overall assessment, key strengths, and critical issues]

## Requirements Validation

### Strengths
- [List what's done well]

### Issues Found
#### High Priority
- **Issue:** [Description]
  - **Location:** [File and section]
  - **Impact:** [Why this matters]
  - **Recommendation:** [Specific fix]

#### Medium Priority
- [Same format]

#### Low Priority
- [Same format]

## Design Document Validation

### Strengths
- [List what's done well]

### Issues Found
[Same format as above]

## Task List Validation

### Strengths
- [List what's done well]

### Issues Found
[Same format as above]

### Task Coverage Analysis
- **Requirements Covered:** [List requirements with corresponding tasks]
- **Requirements Missing Tasks:** [List any requirements without tasks]

## Positioning Document Validation

### B2G Government Positioning Deck
- **Strengths:** [What's done well]
- **Issues:** [What needs improvement]

### B2B2C Partner Positioning Deck
- **Strengths:** [What's done well]
- **Issues:** [What needs improvement]

### Direct Farmer Value Proposition
- **Strengths:** [What's done well]
- **Issues:** [What needs improvement]

## Research Document Validation

### Traditional Extension Agent Economics Baseline
- **Strengths:** [What's done well]
- **Issues:** [What needs improvement]

### Competitor Capability Audit
- **Strengths:** [What's done well]
- **Issues:** [What needs improvement]

## Strategic Consistency Check

### Messaging Consistency
- [Are all documents aligned on key messages?]

### Competitive Claims Validation
- [Are all claims substantiated by research?]

### GTM Prioritization
- [Is B2G clearly positioned as primary revenue channel?]

### Technical Moat Validation
- [Are all 4 moats consistently described?]

## Recommendations Summary

### Must Fix (Before Proceeding)
1. [Specific recommendation with file/section]
2. [Specific recommendation with file/section]

### Should Fix (High Value)
1. [Specific recommendation with file/section]
2. [Specific recommendation with file/section]

### Consider (Nice to Have)
1. [Specific recommendation with file/section]
2. [Specific recommendation with file/section]

## Overall Assessment

**Readiness Score:** [X/10]
- Requirements: [X/10]
- Design: [X/10]
- Tasks: [X/10]
- Positioning: [X/10]
- Research: [X/10]

**Recommendation:** [Proceed / Fix Critical Issues / Major Revision Needed]

**Rationale:** [2-3 sentences explaining the recommendation]
```

## Output Format

Please provide your review in the following format:

```markdown
# AgriNexus AI Code Review

## Executive Summary
[2-3 paragraphs summarizing overall code quality, key strengths, and critical issues]

## WhatsApp Integration Review

### Strengths
- [List what's implemented well]

### Issues Found
#### High Priority
- **Issue:** [Description]
  - **Location:** [File and line number]
  - **Impact:** [Why this matters]
  - **Recommendation:** [Specific fix with code example if possible]

#### Medium Priority
- [Same format]

#### Low Priority
- [Same format]

## Behavioral Nudge Engine Review

### Strengths
- [List what's implemented well]

### Issues Found
[Same format as above]

## Voice Processing Review

### Strengths
- [List what's implemented well]

### Issues Found
[Same format as above]

## Image Analysis Review

### Strengths
- [List what's implemented well]

### Issues Found
[Same format as above]

## RAG Query Processing Review

### Strengths
- [List what's implemented well]

### Issues Found
[Same format as above]

## Hyperlocal Data Integration Review

### Strengths
- [List what's implemented well]

### Issues Found
[Same format as above]

## Local Dialect Support Review

### Strengths
- [List what's implemented well]

### Issues Found
[Same format as above]

## Test Coverage Analysis

### Current Coverage
- **Voice Processing:** [Coverage percentage or description]
- **Image Analysis:** [Coverage percentage or description]
- **Nudge Engine:** [Coverage percentage or description]
- **RAG Queries:** [Coverage percentage or description]

### Missing Tests
- [List areas without adequate test coverage]

### Test Quality Issues
- [List issues with existing tests]

## Security Review

### Vulnerabilities Found
- [List security issues with severity]

### Recommendations
- [Specific security improvements]

## Performance Review

### Performance Issues
- [List slow operations, timeouts, resource limits]

### Optimization Opportunities
- [Specific performance improvements]

## Recommendations Summary

### Must Fix (Before Production)
1. [Specific recommendation with file/line reference]
2. [Specific recommendation with file/line reference]

### Should Fix (High Value)
1. [Specific recommendation with file/line reference]
2. [Specific recommendation with file/line reference]

### Consider (Nice to Have)
1. [Specific recommendation with file/line reference]
2. [Specific recommendation with file/line reference]

## Overall Assessment

**Code Quality Score:** [X/10]
- WhatsApp Integration: [X/10]
- Nudge Engine: [X/10]
- Voice Processing: [X/10]
- Image Analysis: [X/10]
- RAG Processing: [X/10]
- Test Coverage: [X/10]
- Security: [X/10]

**Production Readiness:** [Ready / Needs Fixes / Major Issues]

**Rationale:** [2-3 sentences explaining the assessment]
```

## Key Questions to Answer

As you review, explicitly answer these questions:

1. **Does WhatsApp integration work correctly?** Are messages routed properly and responses delivered?
2. **Does the nudge engine function?** Are behavioral interventions triggered and tracked?
3. **Does voice processing work?** Can the system transcribe and synthesize speech in local dialects?
4. **Does image analysis work?** Can the system identify pests and verify practices from photos?
5. **Does RAG processing work?** Are agricultural queries answered accurately?
6. **Is hyperlocal data integrated?** Are weather and pest alerts targeted to sub-districts?
7. **Are dialects supported?** Can farmers interact in their local languages?
8. **Is the code secure?** Are there vulnerabilities in webhook validation, API keys, or data handling?
9. **Is the code tested?** Is there adequate test coverage for core features?
10. **What's broken or missing?** Are there critical bugs or incomplete implementations?

## Success Criteria

Your review is successful if it:
1. Identifies all critical bugs and security vulnerabilities
2. Validates that core features (WhatsApp, nudge, voice, image, RAG) work correctly
3. Confirms test coverage is adequate for production deployment
4. Identifies performance issues and optimization opportunities
5. Provides specific, actionable code fixes with examples
6. Assesses overall code quality and production readiness
7. Highlights missing implementations or incomplete features
8. Recommends improvements for maintainability and scalability

## Additional Context

### AgriNexus AI Architecture
- **Platform:** 100% serverless AWS (Lambda, DynamoDB, S3, Bedrock)
- **Message Flow:** WhatsApp → API Gateway → Lambda → SQS → Processor → Response
- **AI Services:** Amazon Bedrock (KB, Vision), Transcribe, Polly
- **Data Storage:** DynamoDB for user profiles, nudge tracking, verification records
- **Orchestration:** Step Functions for nudge workflows

### Core Features
- **WhatsApp Integration:** Webhook verification, message routing, media handling
- **Behavioral Nudges:** Trigger detection, timed sequences, response tracking
- **Voice Processing:** Speech-to-text (Transcribe), text-to-speech (Polly), dialect support
- **Image Analysis:** Pest identification, photo verification, fraud detection (Bedrock Vision)
- **RAG Processing:** Agricultural queries, knowledge base retrieval, response generation
- **Hyperlocal Data:** Weather alerts, pest outbreak tracking, sub-district targeting

### Known Constraints
- **AWS Costs:** Lambda, Bedrock, and Transcribe/Polly usage must be optimized
- **Response Time:** Farmers expect responses within 60 seconds for pest identification
- **Dialect Support:** Must support multiple local dialects (Swahili, Kikuyu, Hindi, etc.)
- **Scalability:** System must handle 10,000+ farmers with minimal cost increase

## Final Notes

- **Be thorough but practical:** Focus on bugs and security issues that impact production deployment
- **Be specific:** Provide file names, line numbers, and code examples for fixes
- **Be constructive:** Highlight well-implemented features as well as issues
- **Be technical:** Review actual code implementation, not just documentation
- **Be realistic:** Assess whether the code is production-ready or needs significant work

Your review will inform whether the system is ready for pilot deployment or needs critical fixes. Take your time and be comprehensive.

---

**Estimated Review Time:** 3-4 hours for thorough code analysis
**Priority:** High - Code quality determines pilot success
**Deliverable:** Comprehensive code review document following the format above
