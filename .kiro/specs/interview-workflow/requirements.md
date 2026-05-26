# Requirements Document

## Introduction

This is the Interview Workflow module of TalentKru.ai Server, covering the interview journey lifecycle, slot scheduling, interviewer feedback, questionnaire management, candidate self-service portal, email notification configuration, candidate availability, and the notification agent. This module orchestrates the end-to-end interview process from scheduling through feedback collection and candidate communication.

Key architectural decisions relevant to this module:
- FastAPI background tasks for async processing (AI feedback generation, notification delivery, questionnaire orchestration).
- Soft delete only for data retention; interview artifacts attached to InterviewJourney with an encrypted join table for hired candidates.
- Manual fallback paths for all AI features (behavioral feedback, questionnaire assignment, notification delivery).

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **Candidate**: A job applicant tracked within an organization's recruiting pipeline.
- **InterviewJourney**: The end-to-end lifecycle of a candidate's application for a specific requisition.
- **InterviewSlot**: A scheduled interview event within a journey, assigned to an interviewer.
- **Questionnaire**: A set of questions associated with requisitions that candidates must complete.
- **CandidatePortalToken**: A URL-safe token granting candidates access to the self-service portal.
- **NotificationAgent**: An AI agent that orchestrates email and notification delivery.
- **BehavioralFeedbackAgent**: An AI agent that generates structured behavioral interview feedback from transcripts.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.
- **ENCRYPTION_KEY**: The secret key used exclusively for field-level encryption of PII data at rest.

## Requirements

### Requirement 1: Interview Journey Lifecycle

**User Story:** As a recruiter, I want to track a candidate's progress through interview stages, so that the hiring pipeline is transparent and auditable.

#### Acceptance Criteria

1. THE Server SHALL store InterviewJourney entities with fields: InterviewJourneyID (UUID), OrganizationID (FK), JourneyPublicID (URL-safe random string of at least 22 characters), CandidateID (FK), JobRequisitionID (FK), CurrentStage, CurrentStageStatus, OverallStatus (Active, OnHold, Completed, Cancelled), OfferExtendedAt (nullable timestamp), OfferRespondedAt (nullable timestamp), StartDate, and AuditFields.
2. THE Server SHALL support the following stages in order: Sourced, RecruiterScreen, ManagerScreen, LoopInterview, PanelReview, Rejected, OfferPending, OfferExtended, OfferDeclined, OfferAccepted, and Withdrawn, where forward transitions follow the listed order and lateral transitions to Rejected or Withdrawn are permitted from any non-terminal stage.
3. THE Server SHALL support stage sub-statuses (Scheduled, InProgress, Complete) on non-terminal stages only; terminal stages (Rejected, OfferDeclined, OfferAccepted, Withdrawn) SHALL have no sub-status.
4. WHEN a stage transition occurs, THE Server SHALL create an InterviewJourneyStageHistory record with FromStage, ToStage, ChangedByUserID, ChangedAt, and optional comments (maximum 2000 characters).
5. THE Server SHALL link interview artifacts (transcripts, behavioral feedback, interview feedback) to the InterviewJourney rather than directly to the Candidate. Interview feedback entities are defined in Requirement 3.
6. THE Server SHALL store CandidateInterviewJourney join table entities with fields: CandidateInterviewJourneyID (UUID), CandidateID (FK, encrypted when journey reaches OfferAccepted and OverallStatus is Completed), InterviewJourneyID (FK, encrypted when journey reaches OfferAccepted and OverallStatus is Completed), AssociatedAt (timestamp), and AuditFields, to track the many-to-many relationship between candidates and their interview journeys.
7. WHEN a candidate's InterviewJourney stage transitions to OfferAccepted, THE Server SHALL immediately set OverallStatus to Completed and encrypt both the CandidateID and InterviewJourneyID columns in the CandidateInterviewJourney record at the moment of that stage transition, so that the hired candidate's interview data cannot be looked up after onboarding.
8. IF a user attempts a stage transition that violates the allowed transition rules, THEN THE Server SHALL reject the request with a 400 response indicating the transition is not permitted from the current stage.

### Requirement 2: Interview Slot Scheduling

**User Story:** As a recruiter, I want to schedule interview slots and manage interviewer assignments, so that interviews are coordinated efficiently.

#### Acceptance Criteria

1. THE Server SHALL store InterviewSlot entities with fields: InterviewSlotID (UUID), OrganizationID (FK), InterviewJourneyID (FK), Type (Manager, Technical, Behavioral, Panel), ScheduledStart, ScheduledEnd, Timezone, Status (Scheduled, InProgress, Complete, Cancelled), InvitationStatus (Pending, Accepted, Declined), AttendanceStatus (Unknown, Attended, NoShow), InterviewerUserID, FeedbackID (FK), and AuditFields.
2. WHEN assigning an interviewer to a slot, THE Server SHALL verify the interviewer has not exceeded MaxInterviewsPerDay and MaxInterviewsPerWeek as defined in InterviewerPreference, and SHALL verify the slot Type is included in the interviewer's allowed interview types.
3. IF an interviewer assignment would exceed MaxInterviewsPerDay or MaxInterviewsPerWeek limits, or the slot Type is not in the interviewer's allowed interview types, THEN THE Server SHALL reject the assignment with a 409 Conflict response indicating the specific constraint violated.
4. WHEN an InterviewSlot is created, THE Server SHALL validate that ScheduledStart is before ScheduledEnd and that the slot duration is at least 15 minutes and at most 480 minutes.
5. WHEN an InterviewSlot is created with an assigned interviewer, THE Server SHALL set InvitationStatus to Pending and publish an event for the NotificationAgent to deliver the interview invitation.
6. WHEN an interviewer responds to an invitation, THE Server SHALL update InvitationStatus to Accepted or Declined accordingly.
7. THE Server SHALL support updating AttendanceStatus to Attended or NoShow only after the slot's ScheduledEnd time has passed, via manual update by a user with Recruiter or Administrator role.
8. THE Server SHALL store InterviewerPreference entities with fields: InterviewerUserID (FK), OrganizationID (FK), allowed interview types (subset of Manager, Technical, Behavioral, Panel), MaxInterviewsPerDay (integer, range 1 to 20), MaxInterviewsPerWeek (integer, range 1 to 100), preferred working hours per weekday (start time and end time per day of week), and AuditFields.
9. THE Server SHALL restrict creation and modification of an InterviewerPreference record to the interviewer who owns the record (identified by InterviewerUserID matching the authenticated user's UserID), and to users with Administrator or SuperAdministrator roles.
10. IF an interviewer has no InterviewerPreference record when an assignment is attempted, THEN THE Server SHALL apply default limits of MaxInterviewsPerDay=5 and MaxInterviewsPerWeek=20 and allow all interview types.

### Requirement 3: Interview Feedback

**User Story:** As an interviewer, I want to submit structured feedback after interviews, so that hiring decisions are informed by documented assessments.

#### Acceptance Criteria

1. THE Server SHALL store InterviewFeedback entities with fields: InterviewFeedbackID (UUID), InterviewSlotID (FK), OrganizationID (FK), FeedbackType (enum: Manual, AIGenerated), Status (Draft, Submitted), competency ratings (JSON object mapping competency names to integer ratings 1-5), narrative summary (max 5000 characters), hiring recommendation (StrongYes, Yes, Neutral, No, StrongNo), and AuditFields.
2. THE Server SHALL store BehavioralFeedbackDraft as a specialized type of InterviewFeedback with FeedbackType set to AIGenerated and Status set to Draft, which can be edited by the interviewer before final submission.
3. WHEN an interviewer submits feedback for an InterviewSlot, THE Server SHALL store the structured feedback containing competency ratings (integer scale 1 to 5), a narrative summary (maximum 5000 characters), a hiring recommendation (StrongYes, Yes, Neutral, No, StrongNo), and link it to the slot via FeedbackID.
4. WHEN an interviewer submits a transcript (maximum 50000 characters) for behavioral feedback, THE Server SHALL invoke the BehavioralFeedbackAgent as a background task and persist the generated draft with a status of Draft.
5. IF the BehavioralFeedbackAgent fails, THEN THE Server SHALL log the error and return a response indicating the failure so that the interviewer can submit feedback manually without AI assistance.
6. WHEN a user who is not the assigned interviewer for a slot attempts to create or edit feedback for that slot, THE Server SHALL return a 403 Forbidden response. THE Server SHALL not block create or edit attempts based on any other criteria beyond the requester not being the assigned interviewer.
7. WHEN a user who is not the assigned interviewer, the hiring manager for the requisition, or an administrator attempts to retrieve feedback for a slot, THE Server SHALL return a 403 Forbidden response.
8. THE Server SHALL track feedback status as Draft or Submitted, and IF feedback status is Submitted, THEN THE Server SHALL reject further edits with a 409 Conflict response.
9. WHEN an interviewer submits feedback, THE Server SHALL transition the feedback status from Draft to Submitted and prevent further modifications to that feedback record.

### Requirement 4: Questionnaire Management

**User Story:** As a recruiter, I want to define questionnaires and link them to requisitions, so that candidates complete relevant assessments during the hiring process.

#### Acceptance Criteria

1. THE Server SHALL store Questionnaire entities with fields: QuestionnaireID (UUID), OrganizationID (FK), Title, questions defined in YAML format, and AuditFields.
2. THE Server SHALL define questionnaire YAML schema with the following structure: a list of question objects, where each question contains id (string), text (string, max 500 characters), type (enum: text, multipleChoice, singleChoice, rating, date), required (boolean), options (array of strings for choice types), minRating and maxRating (integers for rating type), and validation rules (object with pattern, minLength, maxLength for text type).
3. IF a recruiter submits a questionnaire with YAML that does not conform to the defined schema (missing required fields, invalid types, or invalid enum values), THEN THE Server SHALL reject the request with a 422 response indicating which fields failed validation.
4. THE Server SHALL support linking questionnaires to requisitions via a JobRequisitionQuestionnaire relationship.
5. WHEN a candidate is associated with a requisition that has linked questionnaires, THE Server SHALL create CandidateQuestionnaireResponse records with Status set to Draft, provided a response record does not already exist for that candidate-questionnaire combination.
6. THE Server SHALL store CandidateQuestionnaireResponse entities with fields: CandidateQuestionnaireResponseID (UUID), CandidateID (FK), QuestionnaireID (FK), OrganizationID (FK), Status (Draft, Incomplete, Submitted), and AuditFields.
7. THE Server SHALL store CandidateQuestionnaireAnswer as JSON keyed by QuestionID, linked to a CandidateQuestionnaireResponse record.
8. WHEN a candidate saves partial answers without completing all required questions, THE Server SHALL set the CandidateQuestionnaireResponse Status to Incomplete.
9. WHEN a candidate submits a completed questionnaire, THE Server SHALL validate that all required questions have answers provided; IF all required questions are answered, THE Server SHALL set the CandidateQuestionnaireResponse Status to Submitted and THE Server SHALL not allow further modifications to that response; IF any required question is unanswered, THE Server SHALL reject the submission with a 422 response indicating which required questions are missing answers.
10. IF a candidate attempts to modify a CandidateQuestionnaireResponse with Status of Submitted, THEN THE Server SHALL reject the request with a 403 Forbidden response.

### Requirement 5: Candidate Portal

**User Story:** As a candidate, I want to access a self-service portal, so that I can complete questionnaires, provide availability, and view my interview schedule.

#### Acceptance Criteria

1. THE Server SHALL generate CandidatePortalTokens as URL-safe strings with a minimum of 32 bytes of cryptographic randomness and a configurable TTL loaded from the PORTAL_TOKEN_TTL_DAYS environment variable. THE Server SHALL automatically generate a CandidatePortalToken when a CandidateQuestionnaireResponse record is first created for a candidate, if no active (non-expired) token already exists for that candidate within the organization.
2. WHEN a candidate accesses the portal with a valid token, THE Server SHALL validate that the token exists, is active, and has not expired.
3. IF a candidate accesses the portal with a token that does not exist, is inactive, or has expired, THEN THE Server SHALL reject the request with a 401 response without revealing whether the token was invalid or expired.
4. WHEN a candidate verifies their email against the token, THE Server SHALL issue a JWT session with a TTL of 60 minutes, scoped to that candidate and organization, containing claims: sub (candidate email), candidate_id, org_id, and exp. THE Server SHALL also accept a valid, non-expired CandidatePortalToken as an authenticated session without requiring email verification, granting the same scoped access as a JWT session for the duration of the token's validity.
5. IF a candidate provides an email that does not match the token's associated candidate, THEN THE Server SHALL reject the verification with a 401 response.
6. THE Server SHALL expose portal endpoints for: listing questionnaires and their status, retrieving questions and existing answers, saving draft answers, and submitting final answers.
7. WHEN a candidate saves answers without completing all required questions, THE Server SHALL persist the answers and set the CandidateQuestionnaireResponse Status to Incomplete, allowing the candidate to return and continue later. THE Server SHALL reject any attempt to save answers to a CandidateQuestionnaireResponse with Status Submitted with a 403 Forbidden response. WHEN a candidate explicitly submits the questionnaire, THE Server SHALL validate that all required questions have answers provided; IF all required questions are answered, THE Server SHALL transition the status to Submitted and prevent further modifications; IF any required question is unanswered, THE Server SHALL reject the submission with a 422 response indicating which required questions are missing answers.
8. THE Server SHALL expose portal endpoints for: listing candidate availability slots, creating and updating availability, and viewing upcoming and past interviews.
9. THE Server SHALL restrict all portal endpoints to the authenticated candidate's own data within their organization.

### Requirement 6: Email Notification Configuration

**User Story:** As a system administrator, I want to control email notification delivery at both the global and organization level, so that notifications can be disabled for testing or compliance reasons without code changes.

#### Acceptance Criteria

1. THE Server SHALL store a SystemSetting entity with fields: SettingKey (unique string), SettingValue (string), Description (nullable), and AuditFields; and SHALL include a system-level setting with SettingKey `email_notifications_enabled` (boolean string "true" or "false", default "true") that acts as a global master switch for all outbound email delivery.
2. THE Server SHALL store OrganizationEmailConfig entities with fields: OrganizationEmailConfigID (UUID), OrganizationID (FK, unique), EmailNotificationsEnabled (boolean, default true), ProviderType (enum: smtp, sendgrid, ses), SmtpHost (nullable, max 253 characters), SmtpPort (nullable integer), SmtpUsername (nullable, max 254 characters), SmtpPassword (nullable, stored encrypted using ENCRYPTION_KEY), SmtpUseTLS (nullable boolean), ThirdPartyApiKey (nullable, stored encrypted using ENCRYPTION_KEY), ThirdPartyProviderRegion (nullable, max 100 characters), FromAddress (max 254 characters), FromName (max 100 characters), and AuditFields.
3. WHEN the NotificationAgent is about to deliver an email, THE Server SHALL first check the global `email_notifications_enabled` system setting; IF the global setting is "false", THE Server SHALL skip delivery and log an informational message without treating the skip as a failure.
4. WHEN the global setting is "true", THE Server SHALL check the OrganizationEmailConfig for the target organization; IF the OrganizationEmailConfig.EmailNotificationsEnabled is false, THE Server SHALL skip delivery for that organization and log an informational message without treating the skip as a failure. THE Server SHALL continue to perform full validation on OrganizationEmailConfig updates regardless of whether EmailNotificationsEnabled is true or false.
5. WHEN delivering an email, THE Server SHALL use the SMTP or third-party provider credentials from the OrganizationEmailConfig for the target organization; IF no OrganizationEmailConfig exists for the organization, THE Server SHALL fall back to system-level SMTP defaults loaded from environment variables (SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS, EMAIL_FROM_ADDRESS, EMAIL_FROM_NAME).
6. THE Server SHALL expose endpoints for creating, retrieving, and updating OrganizationEmailConfig records, restricted to Administrator and SuperAdministrator roles, scoped to the authenticated user's organization.
7. THE Server SHALL expose endpoints for reading and updating the global `email_notifications_enabled` system setting, restricted to the SuperAdministrator role only.
8. IF an OrganizationEmailConfig update contains an invalid ProviderType value or is missing required fields for the selected provider (SmtpHost, SmtpPort, SmtpUsername, SmtpPassword for smtp; ThirdPartyApiKey for sendgrid or ses), THEN THE Server SHALL reject the request with a 422 response indicating which fields failed validation.

### Requirement 7: Candidate Availability

**User Story:** As a candidate, I want to provide my availability for interviews, so that recruiters can schedule interviews at convenient times.

#### Acceptance Criteria

1. THE Server SHALL store CandidateAvailabilitySlot entities with fields: CandidateAvailabilitySlotID (UUID), CandidateID (FK), OrganizationID (FK), interview type (RecruiterScreen, ManagerScreen, LoopInterview), StartTime, EndTime, Timezone, Status (Active, Cancelled), and AuditFields.
2. WHEN a candidate submits availability, THE Server SHALL validate that StartTime is before EndTime, that the slot duration is at least 30 minutes and at most 480 minutes (8 hours), and that StartTime is at least 1 hour in the future relative to the server's current UTC time.
3. IF a candidate submits an availability slot that fails validation, THEN THE Server SHALL reject the request with a 422 response and an error message indicating which validation rule was violated.
4. WHEN creating InterviewSlot records, THE Server SHALL use candidate availability slots with Status Active and interviewer preferences to filter eligible scheduling options, including only slots whose time range fully contains the proposed interview duration.
5. WHEN a candidate cancels an availability slot that has an InterviewSlot in Scheduled status within its time range, THE Server SHALL set the availability slot Status to Cancelled and SHALL automatically set the affected InterviewSlot Status to Cancelled as well, requiring a recruiter to reschedule the interview manually.
6. THE Server SHALL allow a candidate to have a maximum of 50 Active availability slots per organization at any time.

### Requirement 8: Notification Agent

**User Story:** As a system administrator, I want automated notifications for key events, so that candidates and internal users are kept informed throughout the hiring process.

#### Acceptance Criteria

1. THE Server SHALL publish domain events for: journey stage changes, questionnaire submissions, interview creation, and offer acceptance.
2. WHEN a journey stage changes, THE NotificationAgent SHALL send an email notification to the candidate associated with the journey and to the recruiter and hiring manager assigned to the requisition.
3. WHEN a CandidateQuestionnaireResponse record is created with Status Draft, THE NotificationAgent SHALL send the candidate an email invitation containing the portal URL for questionnaire completion.
4. WHEN an InterviewSlot is created with Status Scheduled, THE NotificationAgent SHALL send an interview invitation email to the assigned interviewer.
5. WHILE an InterviewSlot has Status Scheduled and InvitationStatus Pending or Accepted, THE NotificationAgent SHALL send a reminder email to the assigned interviewer at the point in time that is exactly 24 hours before the ScheduledStart time; IF the scheduled check occurs before the 24-hour window is reached, THE NotificationAgent SHALL wait until the next scheduled check that falls within the 24-hour window before sending the reminder.
6. WHEN a candidate reaches OfferAccepted status, THE NotificationAgent SHALL notify all interviewers who were assigned to InterviewSlots on that InterviewJourney.
7. THE Server SHALL store NotificationTemplate entities with fields: NotificationTemplateID (UUID), OrganizationID (FK), EventType (string matching domain event types), Subject (string, max 200 characters), BodyTemplate (text with placeholder variables in {{variable}} format), IsEnabled (boolean), Locale (language and region code, nullable, for locale-specific template variants), and AuditFields, allowing organization-level customization of notification content.
8. THE Server SHALL support organization-level notification templates and per-event-type enable/disable configuration via the NotificationTemplate entity.
9. IF the NotificationAgent fails to deliver a notification, THEN THE Server SHALL log the failure and retry with exponential backoff up to a maximum of 5 attempts.
10. IF the NotificationAgent exhausts all retry attempts for a notification, THEN THE Server SHALL log the final failure and mark the notification as permanently failed.
