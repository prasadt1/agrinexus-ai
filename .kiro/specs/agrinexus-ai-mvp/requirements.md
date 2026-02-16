# Requirements Document: AgriNexus AI MVP

## Introduction

AgriNexus AI is a behavioral AI extension agent designed to solve the "Last Mile" failure in agricultural extension services. The system provides dialect-native agricultural guidance, behavioral nudges timed to weather windows, and visual pest diagnosis to smallholder farmers through WhatsApp. Built on AWS Free Tier infrastructure, the system leverages Amazon Bedrock for conversational AI, AWS Step Functions for behavioral nudge orchestration, and integrates with weather APIs to deliver timely, actionable agricultural advice.

## Glossary

- **AgriNexus_System**: The complete behavioral AI extension agent including all components
- **Bedrock_Agent**: Amazon Bedrock conversational AI component handling dialect-native interactions
- **Knowledge_Base**: S3-stored agricultural manuals and FAO data indexed by Bedrock
- **Nudge_Engine**: AWS Step Functions workflow orchestrating behavioral reminders
- **User_State_Store**: DynamoDB table tracking user context (location, crop, language, conversation history)
- **WhatsApp_Gateway**: API Gateway + Lambda handling WhatsApp webhook integration
- **Weather_Poller**: EventBridge-triggered Lambda polling weather APIs
- **Alert_Dispatcher**: SNS-based system sending urgent notifications
- **Vision_Analyzer**: Claude 3 Vision integration for pest/disease image analysis
- **Voice_Synthesizer**: Amazon Polly generating audio responses
- **Guardrails**: Bedrock safety mechanisms preventing harmful advice
- **Dialect**: Local language variant - MVP supports three Indian dialects: Hindi (North India), Marathi (Maharashtra), Telugu (Andhra Pradesh/Telangana)
- **Behavioral_Nudge**: Timed reminder aligned with agricultural windows
- **Weather_Window**: Time-sensitive period for agricultural activities
- **User_Session**: Multi-turn conversation state maintained in DynamoDB
- **Closed_Loop**: Confirmation workflow tracking task completion
- **Onboarding**: Initial registration process capturing user preferences
- **Message_Template**: Pre-approved WhatsApp template for business-initiated messages
- **Completion_Rate**: Percentage of nudges resulting in confirmed task completion
- **Rate_Limiting**: Throttling mechanism preventing spam and abuse

## Requirements

### Requirement 1 (REQ-ONBOARD-001): User Onboarding and Registration

**User Story:** As a new farmer user, I want to easily register with the system, so that I can start receiving personalized agricultural guidance.

#### Acceptance Criteria

1. WHEN a user sends their first message, THE AgriNexus_System SHALL initiate an onboarding conversation
2. WHEN onboarding begins, THE Bedrock_Agent SHALL prompt the user to select their preferred dialect from supported options (Hindi, Marathi, Telugu)
3. WHEN the user selects a dialect, THE Bedrock_Agent SHALL prompt for their location using district or village name
4. WHEN the user provides a location name, THE system SHALL validate it against a district lookup table covering Maharashtra, Andhra Pradesh, Telangana, and Hindi-belt states (Uttar Pradesh, Madhya Pradesh, Rajasthan, Bihar)
5. IF location validation fails, THEN THE system SHALL ask the user to clarify or select from nearby districts
6. WHEN the user confirms location, THE Bedrock_Agent SHALL prompt for their primary crop type
7. WHEN all onboarding information is collected, THE User_State_Store SHALL create a user profile and confirm registration
8. WHEN onboarding is incomplete after 7 days, THE system SHALL send a reminder message

### Requirement 2 (REQ-CONV-001): Dialect-Native Conversational Interface

**User Story:** As a smallholder farmer, I want to ask agricultural questions in my local dialect, so that I can understand advice without language barriers.

#### Acceptance Criteria

1. WHEN a registered user sends a WhatsApp message in their configured dialect, THE Bedrock_Agent SHALL respond in the same dialect
2. WHEN a user asks an agricultural question, THE Bedrock_Agent SHALL retrieve relevant information from the Knowledge_Base
3. WHEN the Knowledge_Base contains no relevant information, THE Bedrock_Agent SHALL acknowledge the limitation and suggest contacting local extension services
4. WHERE voice output is requested, THE Voice_Synthesizer SHALL generate audio responses in the user's dialect
5. WHEN dialect detection confidence is below 80%, THE system SHALL ask the user to confirm their language preference

### Requirement 3 (REQ-KB-001): Knowledge Base Management

**User Story:** As a system administrator, I want to maintain a validated agricultural knowledge base, so that farmers receive accurate, evidence-based guidance.

#### Acceptance Criteria

1. WHEN agricultural PDF manuals are uploaded to S3, THE AgriNexus_System SHALL index them in the Bedrock Knowledge_Base
2. WHEN the Bedrock_Agent retrieves information, THE system SHALL cite source documents from the Knowledge_Base
3. THE Knowledge_Base SHALL contain FAO-validated agricultural guidance documents in English, with Bedrock_Agent providing responses in the user's selected dialect (Hindi, Marathi, Telugu)
4. WHEN knowledge base content is updated, THE Bedrock_Agent SHALL use the latest indexed version within 24 hours
5. THE AgriNexus_System SHALL support PDF documents up to 50MB per file

### Requirement 4 (REQ-VIS-001): Visual Pest and Disease Diagnosis

**User Story:** As a farmer, I want to send photos of crop problems, so that I can identify pests or diseases affecting my plants.

#### Acceptance Criteria

1. WHEN a user sends an image via WhatsApp, THE Vision_Analyzer SHALL process the image using Claude 3 Vision via a dedicated Bedrock model invocation
2. WHEN the Vision_Analyzer identifies a pest or disease, THE Bedrock_Agent SHALL provide treatment recommendations from the Knowledge_Base
3. WHEN the Vision_Analyzer cannot confidently identify the problem, THE system SHALL request additional images or information
4. THE Vision_Analyzer SHALL support common image formats (JPEG, PNG, WebP)
5. WHEN image analysis completes, THE system SHALL respond within 15 seconds (separate from the 1-second Lambda optimization target for text processing)

### Requirement 5 (REQ-NUDGE-001): Weather-Triggered Behavioral Nudges

**User Story:** As a farmer, I want to receive timely reminders for agricultural activities based on weather conditions, so that I can optimize my farming operations.

#### Acceptance Criteria

1. WHEN the Weather_Poller detects favorable conditions for a user's registered crop activity, THE Nudge_Engine SHALL trigger a behavioral nudge using WhatsApp approved message templates
2. WHEN a behavioral nudge is triggered, THE Alert_Dispatcher SHALL send a WhatsApp message to the affected user
3. THE Weather_Poller SHALL check weather conditions every 6 hours
4. WHEN a user registers their location and crop type, THE User_State_Store SHALL persist this information for weather monitoring
5. WHERE urgent weather alerts occur (frost, heavy rain, drought), THE Alert_Dispatcher SHALL send immediate notifications using pre-approved WhatsApp templates

### Requirement 6 (REQ-STATE-001): User State and Context Management

**User Story:** As a farmer, I want the system to remember my previous conversations and preferences, so that I don't have to repeat information.

#### Acceptance Criteria

1. WHEN a user initiates a conversation, THE WhatsApp_Gateway SHALL retrieve the User_Session from the User_State_Store
2. WHEN a user provides location information, THE User_State_Store SHALL persist the location for future weather monitoring
3. WHEN a user specifies their crop type, THE User_State_Store SHALL associate it with their profile
4. WHEN a multi-turn conversation occurs, THE User_State_Store SHALL maintain conversation history for context
5. THE User_State_Store SHALL retain user state for a minimum of 90 days

### Requirement 7 (REQ-LOOP-001): Closed-Loop Task Confirmation

**User Story:** As an extension coordinator, I want to track whether farmers complete recommended activities, so that I can measure behavioral change and intervention effectiveness.

#### Acceptance Criteria

1. WHEN a behavioral nudge is sent, THE Nudge_Engine SHALL create a pending confirmation task
2. WHEN a user responds with "DONE" or equivalent confirmation, THE Nudge_Engine SHALL mark the task as completed and record completion time
3. WHEN a user responds with "NOT YET" or no response after 24 hours, THE Nudge_Engine SHALL send a first follow-up reminder
4. WHEN no response is received after 48 hours from the first reminder, THE Nudge_Engine SHALL send a second follow-up reminder
5. WHEN no response is received 72 hours after the initial nudge, THE Nudge_Engine SHALL mark the task as abandoned
6. THE system SHALL track nudge completion rate with a target of 30% or higher

### Requirement 8 (REQ-WA-001): WhatsApp Integration

**User Story:** As a farmer, I want to interact with the system through WhatsApp, so that I can use a familiar platform without installing new apps.

#### Acceptance Criteria

1. WHEN a user sends a WhatsApp message, THE WhatsApp_Gateway SHALL receive the webhook event within 2 seconds
2. WHEN the WhatsApp_Gateway receives a message, THE system SHALL process it and respond within 15 seconds for 95% of requests
3. THE WhatsApp_Gateway SHALL support text messages, images, and voice notes
4. WHEN the system sends a response, THE WhatsApp_Gateway SHALL deliver it via the WhatsApp Business API
5. THE WhatsApp_Gateway SHALL handle webhook verification for Meta/Twilio integration
6. THE system SHALL use pre-approved WhatsApp message templates for all business-initiated messages (nudges and alerts)

### Requirement 9 (REQ-SAFE-001): Safety and Guardrails

**User Story:** As a system administrator, I want to prevent the AI from providing harmful agricultural advice, so that farmers are protected from dangerous recommendations.

#### Acceptance Criteria

1. WHEN the Bedrock_Agent generates a response, THE Guardrails SHALL validate it against safety policies
2. IF a response contains potentially harmful advice, THEN THE Guardrails SHALL block the response and generate a safe alternative
3. THE Guardrails SHALL prevent recommendations for unregistered pesticides or chemicals
4. THE Guardrails SHALL refuse to provide medical advice for humans or animals
5. WHEN a guardrail violation is detected, THE system SHALL log the incident for review
6. THE system SHALL maintain a test suite of at least 20 guardrail scenarios organized as: 5 banned pesticide tests, 5 medical advice attempts, 5 unsafe practice recommendations, 5 edge cases

### Requirement 10 (REQ-COST-001): AWS Free Tier Optimization

**User Story:** As a project maintainer, I want the system to operate within AWS Free Tier limits, so that we can deliver the MVP without infrastructure costs.

#### Acceptance Criteria

1. THE AgriNexus_System SHALL use serverless architecture (Lambda, DynamoDB, S3, API Gateway)
2. WHEN Lambda functions execute, THE system SHALL optimize for execution time under 1 second per invocation
3. THE User_State_Store SHALL use DynamoDB on-demand pricing mode
4. THE Knowledge_Base SHALL store documents in S3 Standard storage class
5. THE system SHALL implement request throttling to stay within Free Tier limits
6. THE system SHALL support up to 1,000 concurrent users within Free Tier constraints (with scaling to 10,000 users requiring paid tier)

### Requirement 11 (REQ-DEV-001): Development Workflow Integration

**User Story:** As a developer, I want automated code quality checks, so that we maintain high standards and catch issues early.

#### Acceptance Criteria

1. WHEN code is committed, THE pre-commit hook SHALL run linting checks
2. WHEN code is pushed, THE pre-push hook SHALL run security scans
3. IF linting or security checks fail, THEN THE system SHALL block the commit or push
4. THE hooks SHALL execute within 30 seconds
5. THE hooks SHALL provide clear error messages indicating what needs to be fixed

### Requirement 12 (REQ-CONV-002): Multi-Turn Conversation Support

**User Story:** As a farmer, I want to have back-and-forth conversations with the system, so that I can ask follow-up questions and clarify advice.

#### Acceptance Criteria

1. WHEN a user sends a follow-up message, THE Bedrock_Agent SHALL use previous conversation context from the User_Session
2. THE User_Session SHALL maintain conversation history for the current topic
3. WHEN a conversation topic changes, THE system SHALL recognize the context shift
4. THE Bedrock_Agent SHALL support at least 10 message turns per conversation session
5. WHEN a conversation is inactive for 24 hours, THE system SHALL archive the session but retain user state

### Requirement 13 (REQ-WEATHER-001): Weather Data Integration

**User Story:** As a farmer, I want the system to use accurate local weather data, so that recommendations are relevant to my specific conditions.

#### Acceptance Criteria

1. WHEN the Weather_Poller executes, THE system SHALL query weather APIs for registered user locations
2. THE Weather_Poller SHALL retrieve forecast data for the next 7 days
3. WHEN weather data is unavailable for a location, THE system SHALL log the error and retry after 1 hour
4. THE system SHALL use weather data to determine optimal timing for planting, irrigation, and harvesting activities
5. THE Weather_Poller SHALL cache weather data for 6 hours to minimize API calls

### Requirement 14 (REQ-VOICE-001): Voice Message Support

**User Story:** As a farmer with limited literacy, I want to send voice messages and receive audio responses, so that I can use the system without reading or writing.

#### Acceptance Criteria

1. WHEN a user sends a voice note via WhatsApp, THE system SHALL transcribe it using Amazon Transcribe for Hindi (with Marathi and Telugu support contingent on Transcribe availability)
2. WHEN transcription completes, THE Bedrock_Agent SHALL process the text as a standard message
3. WHERE the user has voice preference enabled, THE Voice_Synthesizer SHALL generate audio responses
4. THE Voice_Synthesizer SHALL support Hindi using appropriate Polly voices, with Marathi and Telugu support added when Polly voices become available
5. WHEN audio generation completes, THE WhatsApp_Gateway SHALL send the audio file via WhatsApp
6. WHERE Transcribe or Polly support is unavailable for a dialect, THE system SHALL inform the user that voice features are limited to Hindi for MVP

### Requirement 15 (REQ-RESIL-001): Error Handling and Resilience

**User Story:** As a system administrator, I want the system to handle failures gracefully, so that users receive helpful feedback even when errors occur.

#### Acceptance Criteria

1. WHEN a Lambda function fails, THE system SHALL retry up to 3 times with exponential backoff
2. WHEN the Bedrock_Agent is unavailable, THE system SHALL respond with a friendly error message and retry instructions
3. WHEN the Weather_Poller fails, THE system SHALL log the error and continue with cached data
4. WHEN DynamoDB throttling occurs, THE system SHALL implement exponential backoff retry logic
5. THE system SHALL maintain 99% uptime during business hours (6 AM - 10 PM local time)
6. WHEN WhatsApp message delivery fails due to connectivity issues, THE system SHALL queue the message and retry for up to 24 hours

### Requirement 16 (REQ-ANALYTICS-001): Analytics and Monitoring

**User Story:** As a project coordinator, I want to track system usage and effectiveness, so that I can demonstrate impact for the competition and future funding.

#### Acceptance Criteria

1. WHEN a user interaction occurs, THE system SHALL log metrics to CloudWatch
2. THE system SHALL track: total users, messages per day, nudge completion rates, and response times
3. WHEN a behavioral nudge is completed, THE system SHALL record the completion time and outcome
4. THE system SHALL generate weekly summary reports of key metrics
5. THE system SHALL protect user privacy by anonymizing personal data in analytics
6. THE system SHALL track dialect detection accuracy with a target of 90% or higher

### Requirement 17 (REQ-PRIVACY-001): User Privacy and Consent

**User Story:** As a farmer, I want control over my data and notifications, so that I can use the service on my own terms.

#### Acceptance Criteria

1. WHEN a user completes onboarding, THE system SHALL explain data usage and request consent
2. WHEN a user sends "STOP" or "UNSUBSCRIBE", THE system SHALL disable all behavioral nudges for that user
3. WHEN a user requests data deletion, THE system SHALL remove all personal information within 7 days
4. THE system SHALL allow users to opt back in by sending "START" or "SUBSCRIBE"
5. WHEN a user opts out, THE system SHALL retain only anonymized analytics data

### Requirement 18 (REQ-RATE-001): Rate Limiting and Abuse Prevention

**User Story:** As a system administrator, I want to prevent spam and abuse, so that the system remains available for legitimate users.

#### Acceptance Criteria

1. WHEN a user sends more than 20 messages in 1 hour, THE system SHALL throttle responses and send a rate limit warning
2. WHEN a phone number is flagged for abuse, THE system SHALL block further interactions and log the incident
3. WHEN suspicious activity is detected, THE system SHALL send a verification code in the user's dialect and require confirmation before resuming service
4. WHEN rate limiting is triggered, THE system SHALL allow emergency weather alerts to bypass the limit
5. THE system SHALL monitor for automated bot behavior and block suspicious patterns

### Requirement 19 (REQ-DEMO-001): Competition Demo and Evaluation

**User Story:** As a competition judge, I want to see a complete end-to-end demonstration, so that I can evaluate the system's social impact and technical implementation.

#### Acceptance Criteria

1. THE system SHALL support a demo scenario where a farmer in Maharashtra growing cotton receives a weather-triggered nudge for irrigation
2. WHEN the demo farmer responds with "DONE" in Marathi, THE system SHALL log the behavioral outcome and completion time
3. THE system SHALL demonstrate visual pest diagnosis by processing a sample cotton pest image and providing treatment recommendations
4. THE system SHALL demonstrate multi-turn conversation by answering follow-up questions about fertilizer application
5. THE system SHALL generate a demo report showing: user onboarding, nudge delivery, task completion, and behavioral change metrics
6. THE demo scenario SHALL complete within 5 minutes and showcase all core features (dialect conversation, weather nudges, vision analysis, closed-loop confirmation)
