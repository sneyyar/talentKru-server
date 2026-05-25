# Requirements Document

## Introduction

TalentKru.ai Server is an enterprise-grade recruiting application backend built with Python FastAPI. It provides multi-tenant identity management, candidate lifecycle tracking, interview journey orchestration, AI-assisted matching and feedback, and a candidate self-service portal. The system is designed for incremental delivery across six phases, starting with authentication and RBAC foundations and progressing through candidate management, interview workflows, questionnaires, AI agents, and reporting.

Key architectural decisions:
- PostgreSQL with pgvector extension for data persistence and semantic search.
- JWT-based local authentication as the primary auth mechanism (SSO/OAuth2 deferred).
- FastAPI background tasks for async processing (resume ingestion, matching, AI feedback).
- Docker Compose as the deployment target.
- Horizontal sharding modeled at the organization level with a default shard 0 placeholder.
- Soft delete only for data retention; interview artifacts attached to InterviewJourney with an encrypted join table for hired candidates.
- Manual fallback paths for all AI features.

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **User**: An internal user (recruiter, hiring manager, administrator, interviewer) belonging to an organization.
- **Candidate**: A job applicant tracked within an organization's recruiting pipeline.
- **InterviewJourney**: The end-to-end lifecycle of a candidate's application for a specific requisition.
- **InterviewSlot**: A scheduled interview event within a journey, assigned to an interviewer.
- **JobRequisition**: An open position within an organization that candidates are matched against.
- **JobProfile**: A job category representing a set of required or desired skills.
- **JobPosting**: The public-facing details of a job including description, location, and salary range.
- **Questionnaire**: A set of questions associated with requisitions that candidates must complete.
- **CandidatePortalToken**: A URL-safe token granting candidates access to the self-service portal.
- **ResumeIngestionAgent**: An AI agent that parses resumes, extracts skills, and generates embeddings.
- **MatchingAgent**: An AI agent that computes semantic similarity between candidates and requisitions.
- **BehavioralFeedbackAgent**: An AI agent that generates structured behavioral interview feedback from transcripts.
- **QuestionnaireOrchestratorAgent**: An AI agent that manages questionnaire assignment for candidates.
- **NotificationAgent**: An AI agent that orchestrates email and notification delivery.
- **RBAC**: Role-Based Access Control governing endpoint authorization.
- **Shard**: A database partition; organizations include a shard_id for future horizontal scaling.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.

## Requirements

### Requirement 1: Project Foundation and Configuration

**User Story:** As a developer, I want a well-structured FastAPI project with environment-based configuration, so that the application is portable and follows 12-factor principles.

#### Acceptance Criteria

1. THE Server SHALL use a `.env` file for all environment-specific configuration including STORAGE_BACKEND (local or s3), STORAGE_LOCAL_PATH (filesystem directory for local storage), RESUME_BUCKET_NAME (S3 bucket for cloud storage), ENCRYPTION_KEY, PORTAL_TOKEN_TTL_DAYS, AI model identifiers, INTERVIEW_LEADERBOARD_DEFAULT_PERIOD_DAYS, DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, AGENT_API_KEY, METRICS_USERNAME, and METRICS_PASSWORD.
2. IF any required environment variable (ENCRYPTION_KEY, STORAGE_BACKEND, DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, AGENT_API_KEY, METRICS_USERNAME, or METRICS_PASSWORD) is missing or empty at startup, THEN THE Server SHALL fail to start and log an error message indicating which variable is missing.
3. THE Server SHALL expose a health check endpoint at GET /health that returns a JSON response containing a status field (value "healthy" when the application and database connection are operational, "unhealthy" otherwise) and a version field (the application semantic version string).
4. THE Server SHALL use PostgreSQL with the pgvector extension as the primary data store.
5. THE Server SHALL use SQLAlchemy as the ORM layer with async session support.
6. THE Server SHALL use Alembic for database schema migrations.
7. THE Server SHALL organize code into logical modules: auth, rbac, users, organizations, candidates, resumes, requisitions, job_profile, job_posting, skills, matching, journeys, interviews, questionnaires, portal, agents, reporting, and observability.
8. WHEN a database entity is created, THE Server SHALL auto-populate CreatedAt with the current UTC timestamp and CreatedBy with the authenticated user's UserID.
9. WHEN a database entity is updated, THE Server SHALL auto-populate UpdatedAt with the current UTC timestamp and UpdatedBy with the authenticated user's UserID, without modifying CreatedAt or CreatedBy.
10. WHEN a database entity is soft-deleted, THE Server SHALL set DeletedAt to the current UTC timestamp and DeletedBy to the authenticated user's UserID, without modifying CreatedAt, CreatedBy, UpdatedAt, or UpdatedBy.

### Requirement 2: Multi-Tenant Organization Management

**User Story:** As a platform administrator, I want to manage multiple client organizations, so that each tenant's data is isolated and branded independently.

#### Acceptance Criteria

1. THE Server SHALL store Organization entities with fields: OrganizationID (UUID), Name (maximum 128 characters), slug (lowercase alphanumeric and hyphens only, maximum 64 characters, unique across all organizations), branding settings (logo URL, primary color, secondary color, terms and conditions URL), feature flags (stored as a JSON object of string keys to boolean values), shard_id, and AuditFields.
2. THE Server SHALL assign shard_id of 0 to all organizations by default and route all database queries to shard 0.
3. THE Server SHALL include a thin shard routing placeholder that always resolves to shard 0 for future horizontal scaling.
4. THE Server SHALL scope all data queries by OrganizationID derived from the authenticated principal.
5. IF a request attempts to access data belonging to a different organization, THEN THE Server SHALL reject the request with a 403 Forbidden response.
6. THE Server SHALL support creating, updating, listing, and retrieving organizations via REST endpoints restricted to the SuperAdministrator role.
7. IF a user attempts to create or update an organization with a slug that is already in use by another organization, THEN THE Server SHALL reject the request with an error response indicating the slug must be unique.

### Requirement 3: User Management

**User Story:** As an administrator, I want to manage users within my organization, so that the right people have access to the recruiting system.

#### Acceptance Criteria

1. THE Server SHALL store User entities with fields: UserID (UUID), OrganizationID (FK), Email (unique within organization, maximum 254 characters), GivenName (maximum 100 characters), LastName (maximum 100 characters), Status (Active, Inactive, Locked), ManagerUserID (FK to User), hashed_password, and AuditFields.
2. WHEN an administrator creates a user, THE Server SHALL validate that the email is unique within the organization, that the password is between 8 and 72 characters in length, and store the password using bcrypt hashing.
3. IF an administrator attempts to create a user with an email that already exists within the organization, THEN THE Server SHALL reject the request with a 409 Conflict response indicating the email is already in use.
4. WHEN an administrator updates a user status to Locked, THE Server SHALL prevent that user from authenticating on subsequent authentication attempts.
5. THE Server SHALL enforce that all users except SuperAdministrator are linked to exactly one organization.
6. THE Server SHALL support listing, creating, and updating users via REST endpoints restricted to Administrator and SuperAdministrator roles, with listing supporting pagination with a default page size of 20 and a maximum page size of 100.
7. IF a user creation or update request contains an invalid email format or is missing required fields (Email, GivenName, LastName, password on creation), THEN THE Server SHALL reject the request with a 422 response indicating which fields failed validation.

### Requirement 4: JWT Local Authentication

**User Story:** As a user, I want to authenticate with username and password, so that I can access the system without external SSO dependencies.

#### Acceptance Criteria

1. WHEN a user submits valid credentials to the POST /token endpoint using application/x-www-form-urlencoded format, THE Server SHALL verify the password against the stored bcrypt hash and return a signed JWT containing the user's identity and organization.
2. WHEN a user submits invalid credentials to the POST /token endpoint, THE Server SHALL return a 401 Unauthorized response without revealing whether the username or password was incorrect.
3. THE Server SHALL sign JWTs using HMAC-SHA256 with a secret key loaded from the ENCRYPTION_KEY environment variable.
4. THE Server SHALL include the following claims in issued JWTs: sub (username), org_id (OrganizationID), roles (list of role names), and exp (expiration timestamp set to 60 minutes from the time of issuance).
5. WHEN a request includes an expired JWT, THE Server SHALL return a 401 Unauthorized response.
6. WHEN a request to a protected endpoint lacks a valid Authorization Bearer token, THE Server SHALL return a 401 Unauthorized response.
7. THE Server SHALL implement authentication as a stateless mechanism with no server-side session storage.
8. IF the user account has a Status of Locked or Inactive, THEN THE Server SHALL reject the authentication attempt with a 401 Unauthorized response regardless of whether the credentials are valid.
9. IF the POST /token request body is missing required fields (username or password), THEN THE Server SHALL return a 422 Unprocessable Entity response indicating which fields are missing.
10. IF the ENCRYPTION_KEY environment variable is not set or is empty at application startup, THEN THE Server SHALL fail to start and log an error message indicating the missing configuration.

### Requirement 5: Role-Based Access Control

**User Story:** As an administrator, I want to assign roles to users, so that access to system features is governed by organizational responsibilities.

#### Acceptance Criteria

1. THE Server SHALL support the following roles: Administrator, Recruiter, HiringManager, CommitteeMember, HRManager, Interviewer, and SuperAdministrator.
2. THE Server SHALL implement a UserRole many-to-many relationship allowing users to hold multiple roles simultaneously.
3. IF a user without Administrator or SuperAdministrator role attempts to manage users or roles, THEN THE Server SHALL return a 403 Forbidden response.
4. IF a user without Recruiter role attempts to create candidates or job requisitions, THEN THE Server SHALL return a 403 Forbidden response.
5. IF a user without Recruiter or HiringManager role attempts to transition an InterviewJourney between stages, THEN THE Server SHALL return a 403 Forbidden response.
6. THE Server SHALL enforce role checks via FastAPI dependency injection on all route handlers except the health check endpoint, the POST /token authentication endpoint, and public portal token-validation endpoints.
7. THE Server SHALL include role information in the JWT claims so that authorization decisions do not require additional database lookups for each request.
8. WHEN an Administrator or SuperAdministrator assigns or removes a role for a user, THE Server SHALL persist the change in the UserRole relationship and record the operation in the audit log.
9. IF a role assignment request specifies a role not in the supported roles list or assigns a role the user already holds, THEN THE Server SHALL return a 400 Bad Request response indicating the validation failure.
10. WHEN a user's roles are modified, THE Server SHALL require the user to re-authenticate to obtain a new JWT reflecting the updated roles, and THE Server SHALL continue to honor the previously issued JWT until its expiration.

### Requirement 6: Candidate Management

**User Story:** As a recruiter, I want to create and manage candidate profiles, so that I can track applicants through the hiring process.

#### Acceptance Criteria

1. THE Server SHALL store Candidate entities with fields: CandidateID (UUID), OrganizationID (FK), Name (max 200 characters), Email (max 254 characters), Phone (max 50 characters), Location (max 200 characters), GlobalStatus (Active, Interviewing, Expired, Ineligible, Deleted), IneligibilityReason (nullable, max 1000 characters), and AuditFields.
2. WHEN a recruiter creates a candidate, THE Server SHALL validate that the Email is unique within the organization, that Name and Email are provided, and set GlobalStatus to Active by default.
3. WHEN a candidate with GlobalStatus of Active has no active InterviewJourneys and no changes to Name, Email, Phone, Location, or associated resume records for 90 days, THE Server SHALL set GlobalStatus to Expired via a scheduled background task.
4. IF a user sets a candidate to Ineligible status without providing an IneligibilityReason value of at least 1 non-whitespace character, THEN THE Server SHALL reject the request with a 400 Bad Request response indicating that IneligibilityReason is required.
5. WHEN a candidate is set to Deleted status, THE Server SHALL perform a logical deletion by populating the DeletedAt and DeletedBy AuditFields and excluding the candidate from search and matching results while retaining the record for audit purposes.
6. THE Server SHALL support searching candidates by name (partial, case-insensitive match), email (partial, case-insensitive match), and status (exact match), scoped to the authenticated user's organization, with paginated results returning a maximum of 50 records per page by default.
7. THE Server SHALL restrict GlobalStatus transitions to the following valid paths: Active to Interviewing, Active to Ineligible, Active to Deleted, Interviewing to Active, Interviewing to Ineligible, Interviewing to Deleted, Expired to Active, and Expired to Deleted.
8. IF a user attempts an invalid GlobalStatus transition, THEN THE Server SHALL reject the request with a 400 Bad Request response indicating the transition is not permitted.

### Requirement 7: Resume Management and Ingestion

**User Story:** As a recruiter, I want to upload and parse resumes, so that candidate skills and experience are automatically extracted and searchable.

#### Acceptance Criteria

1. THE Server SHALL store Resume entities with fields: ResumeID (UUID), CandidateID (FK, nullable at upload), OrganizationID (FK), StorageLocation, MimeType, FileName, FileSizeBytes, UploadedByUserID, IsPrimary flag, ParseStatus (Pending, Completed, Failed), parsed data fields (extracted name, email, phone, summary, job history, skills), and AuditFields.
2. WHEN a user uploads a resume file, THE Server SHALL accept only PDF, DOC, and DOCX formats with a maximum file size of 10 MB and store the file in the configured storage backend.
3. IF a user uploads a file with an unsupported format or exceeding 10 MB, THEN THE Server SHALL reject the upload with a 422 response indicating the validation failure reason.
4. THE Server SHALL support two storage backends configurable via the STORAGE_BACKEND environment variable: a local filesystem directory (for development) and an S3-compatible bucket (for cloud deployment).
5. WHEN a resume is uploaded, THE Server SHALL enqueue a background task to invoke the ResumeIngestionAgent with the storage URI and metadata.
6. WHEN the ResumeIngestionAgent returns parsed results, THE Server SHALL update or create Candidate, CandidateJobHistory, and CandidateSkill records, associate the resume, and set ParseStatus to Completed.
7. IF the ResumeIngestionAgent fails to parse a resume, THEN THE Server SHALL set ParseStatus to Failed, log the error with a correlation ID, and expose the resume record with Failed status so the uploading recruiter can provide candidate data via manual entry endpoints.
8. THE Server SHALL support listing resumes for a candidate with pagination and retrieving resume metadata and parsed fields.
9. THE Server SHALL restrict resume upload and listing endpoints to users with Recruiter or Administrator roles within the same organization.

### Requirement 8: Skills and Domain Taxonomy

**User Story:** As a recruiter, I want a standardized skill taxonomy, so that candidate skills and requisition requirements can be consistently compared.

#### Acceptance Criteria

1. THE Server SHALL store Domain entities with fields: DomainID (UUID), Name (unique, max 100 characters), Description (nullable), and AuditFields; and Skill entities with fields: SkillID (UUID), DomainID (FK), Name (unique within domain, max 100 characters), and AuditFields.
2. THE Server SHALL store CandidateSkill entities with fields: CandidateSkillID (UUID), CandidateID (FK), SkillID (FK), ProficiencyRank (integer 1 to 5), YearsOfExperience (integer 0 to 50), Source (enum: manual, parsed, inferred), and AuditFields.
3. THE Server SHALL store RequisitionRequiredSkill entities with fields: RequisitionRequiredSkillID (UUID), JobRequisitionID (FK), SkillID (FK), RequiredProficiencyRank (integer 1 to 5), Weight (integer 1 to 10 indicating relative priority among required skills for the requisition), and AuditFields.
4. WHEN the ResumeIngestionAgent extracts skills, THE Server SHALL match each extracted skill name against existing Skill entity names using case-insensitive comparison and link the matching Skill to the CandidateSkill record.
5. IF the ResumeIngestionAgent extracts a skill that does not match any existing Skill entity name, THEN THE Server SHALL create the CandidateSkill record with Source set to parsed and flag the skill for manual taxonomy review without blocking the ingestion process.

### Requirement 9: Job Profile and Job Posting Management

**User Story:** As a recruiter, I want to define job profiles and create job postings, so that open positions are clearly described with required skills and compensation details.

#### Acceptance Criteria

1. THE Server SHALL store JobProfile entities with fields: JobProfileID (UUID), OrganizationID (FK), Name, and AuditFields, with associated required and desired skills linked via the Skill taxonomy using a proficiency designation (required or desired) for each skill.
2. THE Server SHALL store JobPosting entities with fields: JobPostingID (UUID), OrganizationID (FK), job description, work locations (list of location strings), salary range minimum, salary range maximum, salary currency, sourcing channel, linked JobProfileID (FK), and AuditFields.
3. WHEN a recruiter creates a job posting without a linked JobProfile, THE Server SHALL reject the request with a 400 Bad Request response indicating that a JobProfile is required.
4. WHEN a recruiter creates a job posting with a valid linked JobProfile, THE Server SHALL store the job posting and associate it with the specified JobProfile.
5. THE Server SHALL support listing and filtering job postings by location, salary range (returning postings whose salary range overlaps with the requested min/max filter values), and sourcing channel, scoped to the authenticated user's organization.
6. IF a user without the Recruiter role attempts to create, update, or delete a JobProfile or JobPosting, THEN THE Server SHALL return a 403 Forbidden response.

### Requirement 10: Job Requisition Management

**User Story:** As a recruiter, I want to create and manage job requisitions, so that I can track open positions and their hiring pipeline.

#### Acceptance Criteria

1. THE Server SHALL store JobRequisition entities with fields: JobRequisitionID (UUID), OrganizationID (FK), ExternalRequisitionID (nullable, for future ATS integration), Title (max 200 characters), Department (max 100 characters), Location (max 200 characters), HiringManagerUserID (FK), Status (Open, OnHold, Closed, Cancelled), Description (max 5000 characters), linked JobProfile, and AuditFields.
2. WHEN a recruiter creates a requisition, THE Server SHALL set Status to Open by default and permit only the following status transitions: Open to OnHold, Open to Closed, Open to Cancelled, OnHold to Open, and OnHold to Cancelled.
3. WHEN a recruiter associates a candidate with a requisition, THE Server SHALL validate that the requisition Status is Open, that the candidate GlobalStatus is Active or Interviewing, and that the candidate is not already associated with the same requisition, before creating the association.
4. THE Server SHALL support configuring required skills on a requisition with proficiency levels (integer 1 to 5) and priority weights (decimal value between 0.0 and 1.0 inclusive).
5. THE Server SHALL support listing and filtering requisitions by hiring manager, status, department, and domain with pagination.
6. IF a recruiter attempts a status transition not in the permitted set, THEN THE Server SHALL reject the request with a 400 response indicating the invalid transition.

### Requirement 11: Interview Journey Lifecycle

**User Story:** As a recruiter, I want to track a candidate's progress through interview stages, so that the hiring pipeline is transparent and auditable.

#### Acceptance Criteria

1. THE Server SHALL store InterviewJourney entities with fields: InterviewJourneyID (UUID), OrganizationID (FK), JourneyPublicID (URL-safe random string of at least 22 characters), CandidateID (FK), JobRequisitionID (FK), CurrentStage, CurrentStageStatus, OverallStatus (Active, OnHold, Completed, Cancelled), OfferExtendedAt (nullable timestamp), OfferRespondedAt (nullable timestamp), StartDate, and AuditFields.
2. THE Server SHALL support the following stages in order: Sourced, RecruiterScreen, ManagerScreen, LoopInterview, PanelReview, Rejected, OfferPending, OfferExtended, OfferDeclined, OfferAccepted, and Withdrawn, where forward transitions follow the listed order and lateral transitions to Rejected or Withdrawn are permitted from any non-terminal stage.
3. THE Server SHALL support stage sub-statuses (Scheduled, InProgress, Complete) on non-terminal stages only; terminal stages (Rejected, OfferDeclined, OfferAccepted, Withdrawn) SHALL have no sub-status.
4. WHEN a stage transition occurs, THE Server SHALL create an InterviewJourneyStageHistory record with FromStage, ToStage, ChangedByUserID, ChangedAt, and optional comments (maximum 2000 characters).
5. THE Server SHALL link interview artifacts (transcripts, behavioral feedback, interview feedback) to the InterviewJourney rather than directly to the Candidate.
6. WHEN a candidate reaches OfferAccepted status and the OverallStatus is set to Completed, THE Server SHALL encrypt both keys in the Candidate-InterviewJourney join table so that the hired candidate's interview data cannot be looked up after onboarding.
7. IF a user attempts a stage transition that violates the allowed transition rules, THEN THE Server SHALL reject the request with a 400 response indicating the transition is not permitted from the current stage.

### Requirement 12: Interview Slot Scheduling

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

### Requirement 13: Interview Feedback

**User Story:** As an interviewer, I want to submit structured feedback after interviews, so that hiring decisions are informed by documented assessments.

#### Acceptance Criteria

1. WHEN an interviewer submits feedback for an InterviewSlot, THE Server SHALL store the structured feedback containing competency ratings (integer scale 1 to 5), a narrative summary (maximum 5000 characters), a hiring recommendation (StrongYes, Yes, Neutral, No, StrongNo), and link it to the slot via FeedbackID.
2. WHEN an interviewer submits a transcript (maximum 50000 characters) for behavioral feedback, THE Server SHALL invoke the BehavioralFeedbackAgent as a background task and persist the generated draft with a status of Draft.
3. IF the BehavioralFeedbackAgent fails, THEN THE Server SHALL log the error and return a response indicating the failure so that the interviewer can submit feedback manually without AI assistance.
4. WHEN a user who is not the assigned interviewer for a slot attempts to create or edit feedback for that slot, THE Server SHALL return a 403 Forbidden response.
5. WHEN a user who is not the assigned interviewer, the hiring manager for the requisition, or an administrator attempts to retrieve feedback for a slot, THE Server SHALL return a 403 Forbidden response.
6. THE Server SHALL track feedback status as Draft or Submitted, and IF feedback status is Submitted, THEN THE Server SHALL reject further edits with a 409 Conflict response.
7. WHEN an interviewer submits feedback, THE Server SHALL transition the feedback status from Draft to Submitted and prevent further modifications to that feedback record.

### Requirement 14: Questionnaire Management

**User Story:** As a recruiter, I want to define questionnaires and link them to requisitions, so that candidates complete relevant assessments during the hiring process.

#### Acceptance Criteria

1. THE Server SHALL store Questionnaire entities with fields: QuestionnaireID (UUID), OrganizationID (FK), Title, questions defined in YAML format, and AuditFields.
2. THE Server SHALL support linking questionnaires to requisitions via a JobRequisitionQuestionnaire relationship.
3. WHEN a candidate is associated with a requisition that has linked questionnaires, THE Server SHALL create CandidateQuestionnaireResponse records with Status set to Draft, provided a response record does not already exist for that candidate-questionnaire combination.
4. THE Server SHALL store CandidateQuestionnaireResponse entities with fields: CandidateQuestionnaireResponseID (UUID), CandidateID (FK), QuestionnaireID (FK), OrganizationID (FK), Status (Draft, Incomplete, Submitted), and AuditFields.
5. THE Server SHALL store CandidateQuestionnaireAnswer as JSON keyed by QuestionID, linked to a CandidateQuestionnaireResponse record.
6. WHEN a candidate saves partial answers without completing all required questions, THE Server SHALL set the CandidateQuestionnaireResponse Status to Incomplete.
7. WHEN a candidate submits a completed questionnaire, THE Server SHALL set the CandidateQuestionnaireResponse Status to Submitted, and THE Server SHALL not allow further modifications to that response.
8. IF a candidate attempts to modify a CandidateQuestionnaireResponse with Status of Submitted, THEN THE Server SHALL reject the request with a 403 Forbidden response.

### Requirement 15: Candidate Portal

**User Story:** As a candidate, I want to access a self-service portal, so that I can complete questionnaires, provide availability, and view my interview schedule.

#### Acceptance Criteria

1. THE Server SHALL generate CandidatePortalTokens as URL-safe strings with a minimum of 32 bytes of cryptographic randomness and a configurable TTL loaded from the PORTAL_TOKEN_TTL_DAYS environment variable.
2. WHEN a candidate accesses the portal with a valid token, THE Server SHALL validate that the token exists, is active, and has not expired.
3. IF a candidate accesses the portal with a token that does not exist, is inactive, or has expired, THEN THE Server SHALL reject the request with a 401 response without revealing whether the token was invalid or expired.
4. WHEN a candidate verifies their email against the token, THE Server SHALL issue a JWT session with a TTL of 60 minutes, scoped to that candidate and organization, containing claims: sub (candidate email), candidate_id, org_id, and exp.
5. IF a candidate provides an email that does not match the token's associated candidate, THEN THE Server SHALL reject the verification with a 401 response.
6. THE Server SHALL expose portal endpoints for: listing questionnaires and their status, retrieving questions and existing answers, saving draft answers, and submitting final answers.
7. WHEN a candidate submits final answers for a questionnaire, THE Server SHALL validate that all required questions have answers provided before transitioning the status to Submitted.
8. THE Server SHALL expose portal endpoints for: listing candidate availability slots, creating and updating availability, and viewing upcoming and past interviews.
9. THE Server SHALL restrict all portal endpoints to the authenticated candidate's own data within their organization.

### Requirement 16: Candidate Availability

**User Story:** As a candidate, I want to provide my availability for interviews, so that recruiters can schedule interviews at convenient times.

#### Acceptance Criteria

1. THE Server SHALL store CandidateAvailabilitySlot entities with fields: CandidateAvailabilitySlotID (UUID), CandidateID (FK), OrganizationID (FK), interview type (RecruiterScreen, ManagerScreen, LoopInterview), StartTime, EndTime, Timezone, Status (Active, Cancelled), and AuditFields.
2. WHEN a candidate submits availability, THE Server SHALL validate that StartTime is before EndTime, that the slot duration is at least 30 minutes, and that StartTime is at least 1 hour in the future relative to the server's current UTC time.
3. IF a candidate submits an availability slot that fails validation, THEN THE Server SHALL reject the request with a 422 response and an error message indicating which validation rule was violated.
4. WHEN creating InterviewSlot records, THE Server SHALL use candidate availability slots with Status Active and interviewer preferences to filter eligible scheduling options, including only slots whose time range fully contains the proposed interview duration.
5. WHEN a candidate cancels an availability slot that has an InterviewSlot in Scheduled status within its time range, THE Server SHALL set the slot Status to Cancelled and leave the existing InterviewSlot unchanged.
6. THE Server SHALL allow a candidate to have a maximum of 50 Active availability slots per organization at any time.

### Requirement 17: AI Resume Ingestion Agent

**User Story:** As a recruiter, I want resumes to be automatically parsed and skills extracted, so that candidate profiles are populated without manual data entry.

#### Acceptance Criteria

1. THE Server SHALL expose an internal endpoint (POST /internal/agents/resume-ingestion-callback) for the ResumeIngestionAgent to post parsed results, authenticated via the X-Agent-API-Key header.
2. WHEN the ResumeIngestionAgent is invoked, THE Server SHALL provide the resume storage URI and associated metadata including CandidateID, OrganizationID, ResumeID, MimeType, and FileName.
3. WHEN the ResumeIngestionAgent returns results, THE Server SHALL validate that the payload contains at least one of CandidateJobHistory or CandidateSkill entries and map the payload to Candidate, CandidateJobHistory, CandidateSkill, and Resume entities.
4. IF the ResumeIngestionAgent callback payload fails validation, THEN THE Server SHALL reject the request with a 422 response and log the validation failure with the correlation ID.
5. WHEN the ResumeIngestionAgent results are successfully mapped to entities, THE Server SHALL generate vector embeddings for the parsed resume text and store them using pgvector for semantic search.
6. IF the ResumeIngestionAgent encounters an error, THEN THE Server SHALL log the failure with correlation ID and notify the uploading recruiter, and the Server SHALL allow the recruiter to manually create or update candidate data via standard candidate endpoints.

### Requirement 18: AI Matching Agent

**User Story:** As a recruiter, I want candidates to be automatically ranked against requisitions, so that the best-fit candidates surface quickly.

#### Acceptance Criteria

1. WHEN a user triggers matching for a requisition, THE Server SHALL invoke the MatchingAgent as a background task scoped to the requisition's organization.
2. THE MatchingAgent SHALL compute embeddings for the requisition using description, skills, and domain.
3. THE MatchingAgent SHALL run vector search over candidate embeddings within the same organization, excluding candidates with GlobalStatus of Ineligible, Expired, or Deleted, and return a maximum of 100 candidate matches.
4. THE MatchingAgent SHALL combine semantic similarity with structured skill matching to compute a MatchScore on a numeric scale of 0.00 to 100.00.
5. THE MatchingAgent SHALL generate a MatchExplanation in natural language text of no more than 1000 characters for each match.
6. THE Server SHALL persist CandidateRequisitionMatch records with MatchScore, MatchExplanation, and a timestamp indicating when the match was computed.
7. THE Server SHALL expose a paginated endpoint to retrieve matches for a requisition sorted by MatchScore in descending order.
8. IF the MatchingAgent fails, THEN THE Server SHALL log the error with a correlation ID and allow recruiters to manually associate candidates with requisitions.

### Requirement 19: AI Questionnaire Orchestrator Agent

**User Story:** As a recruiter, I want questionnaires to be automatically assigned when candidates join requisitions, so that no assessment steps are missed.

#### Acceptance Criteria

1. WHEN a candidate is associated with a requisition, THE Server SHALL invoke the QuestionnaireOrchestratorAgent as a background task to retrieve the questionnaires linked to that requisition via JobRequisitionQuestionnaire records.
2. WHEN the QuestionnaireOrchestratorAgent processes a candidate-requisition association, THE QuestionnaireOrchestratorAgent SHALL query existing CandidateQuestionnaireResponse records matching the same CandidateID and QuestionnaireID and create a new CandidateQuestionnaireResponse record with Status set to Draft only for questionnaires that have no existing response record for that candidate.
3. IF the requisition has no linked questionnaires, THEN THE QuestionnaireOrchestratorAgent SHALL complete without creating any records and log an informational message.
4. IF the QuestionnaireOrchestratorAgent fails, THEN THE Server SHALL log the error with a correlation ID and expose a manual questionnaire assignment endpoint accessible to users with the Recruiter role.
5. WHEN the QuestionnaireOrchestratorAgent completes successfully, THE Server SHALL record the assignment event in the audit log with the CandidateID, JobRequisitionID, and the count of newly created CandidateQuestionnaireResponse records.

### Requirement 20: AI Behavioral Feedback Agent

**User Story:** As an interviewer, I want AI-generated behavioral feedback drafts from interview transcripts, so that I can provide structured assessments more efficiently.

#### Acceptance Criteria

1. WHEN an interviewer submits a transcript for an InterviewSlot, THE Server SHALL invoke the BehavioralFeedbackAgent as a background task with the transcript text and contextual metadata including the interview type, job requisition title, and required competencies from the linked JobProfile.
2. THE BehavioralFeedbackAgent SHALL generate structured behavioral feedback including competency ratings on the integer scale of 1 to 5 and a narrative summary of no more than 2000 characters.
3. WHEN the BehavioralFeedbackAgent returns results, THE Server SHALL persist the generated feedback as a BehavioralFeedbackDraft linked to the InterviewSlot, replacing any previously generated draft for that slot.
4. WHEN a user who is not the assigned interviewer for the slot attempts to trigger draft generation, THE Server SHALL reject the request with a 403 Forbidden response.
5. IF the BehavioralFeedbackAgent fails, THEN THE Server SHALL log the error with the correlation ID and InterviewSlotID, and retain the ability for the interviewer to submit feedback manually without AI assistance.
6. THE Server SHALL reject transcript submissions that exceed 50,000 characters with a validation error response.

### Requirement 21: Notification Agent

**User Story:** As a system administrator, I want automated notifications for key events, so that candidates and internal users are kept informed throughout the hiring process.

#### Acceptance Criteria

1. THE Server SHALL publish domain events for: journey stage changes, questionnaire submissions, interview creation, and offer acceptance.
2. WHEN a journey stage changes, THE NotificationAgent SHALL send an email notification to the candidate associated with the journey and to the recruiter and hiring manager assigned to the requisition.
3. WHEN a CandidateQuestionnaireResponse record is created with Status Draft, THE NotificationAgent SHALL send the candidate an email invitation containing the portal URL for questionnaire completion.
4. WHEN an InterviewSlot is created with Status Scheduled, THE NotificationAgent SHALL send an interview invitation email to the assigned interviewer.
5. WHILE an InterviewSlot has Status Scheduled and InvitationStatus Pending or Accepted, THE NotificationAgent SHALL send a reminder email to the assigned interviewer 24 hours before the ScheduledStart time.
6. WHEN a candidate reaches OfferAccepted status, THE NotificationAgent SHALL notify all interviewers who were assigned to InterviewSlots on that InterviewJourney.
7. THE Server SHALL support organization-level notification templates and per-event-type enable/disable configuration.
8. IF the NotificationAgent fails to deliver a notification, THEN THE Server SHALL log the failure and retry with exponential backoff up to a maximum of 5 attempts.
9. IF the NotificationAgent exhausts all retry attempts for a notification, THEN THE Server SHALL log the final failure and mark the notification as permanently failed.

### Requirement 22: Reporting and Analytics

**User Story:** As an HR manager, I want reporting dashboards, so that I can monitor hiring pipeline health and interviewer performance.

#### Acceptance Criteria

1. THE Server SHALL expose a candidate funnel report endpoint that returns the count of InterviewJourneys at each stage (Sourced, RecruiterScreen, ManagerScreen, LoopInterview, PanelReview, Rejected, OfferPending, OfferExtended, OfferDeclined, OfferAccepted, Withdrawn) with filters by domain, skill, requisition, and date range (start date and end date based on journey StartDate).
2. THE Server SHALL expose a requisition summary report endpoint showing the count of JobRequisitions in each status (Open, OnHold, Closed, Cancelled) with filters by department, hiring manager, and date range.
3. THE Server SHALL expose a questionnaire completion report endpoint showing the ratio of CandidateQuestionnaireResponse records with status Submitted to total assigned records, with filters by requisition and date range.
4. THE Server SHALL expose an interviewer statistics endpoint showing total interview count, no-show rate (count of InterviewSlots with AttendanceStatus NoShow divided by total completed and no-show slots), and breakdown by interview type, with filters by date range and interviewer.
5. THE Server SHALL expose an interviewer leaderboard endpoint that ranks interviewers by completed interview count and returns the top N results (where N is specified by the caller with a default of 10 and a maximum of 100) over a configurable period defaulting to INTERVIEW_LEADERBOARD_DEFAULT_PERIOD_DAYS.
6. THE Server SHALL restrict reporting endpoints to users with Administrator or HRManager roles.
7. THE Server SHALL support pagination on all reporting endpoints with a default page size of 20 and a maximum page size of 100.
8. IF a reporting endpoint is called without a date range filter, THEN THE Server SHALL default to the most recent 90 days.

### Requirement 23: Observability

**User Story:** As a platform operator, I want structured logging, metrics, and tracing, so that I can monitor system health and debug issues efficiently.

#### Acceptance Criteria

1. THE Server SHALL emit structured JSON logs with a correlation ID, timestamp, log level, module name, and event description for the following workflows: authentication attempts, candidate creation and status changes, resume uploads and ingestion results, matching invocations, interview scheduling and status updates, questionnaire submissions, AI agent invocations and completions, and portal access events.
2. THE Server SHALL expose a metrics endpoint in Prometheus-compatible format tracking: resumes parsed (counter), match computation duration in milliseconds (histogram), match counts per requisition (counter), questionnaire completion events (counter), AI agent error rates per agent name (counter), interview volume by stage, type, and organization (gauge), and no-show rates per organization (gauge).
3. THE Server SHALL propagate correlation IDs from the originating HTTP request through background tasks and AI agent invocations, and integrate distributed tracing spans across AI agent calls, storage backend operations, and database query execution.
4. WHEN an AI agent call fails, THE Server SHALL log the failure at ERROR level with the correlation ID, agent name, input payload size, resume or requisition identifier if applicable, error type, and error description.
5. WHEN a background task is enqueued, THE Server SHALL include the originating request's correlation ID in the task context so that all log entries and trace spans produced by the task are linked to the original request.

### Requirement 24: API Documentation and AI Agent Compatibility

**User Story:** As a developer integrating AI agents, I want all API endpoints to be fully documented with OpenAPI metadata, so that agents can dynamically discover and use the API.

#### Acceptance Criteria

1. THE Server SHALL include operation_id (snake_case), summary (maximum 80 characters), and description (minimum 20 characters) on every FastAPI route decorator.
2. THE Server SHALL include Field(description="...") with a minimum length of 10 characters on every Pydantic model field used in request or response schemas.
3. THE Server SHALL generate a valid OpenAPI 3.1 specification accessible at the /docs and /openapi.json endpoints, containing entries for every registered route.
4. IF a request targets an internal agent endpoint (any route under the /internal/agents/ path prefix) without a valid X-Agent-API-Key header, THEN THE Server SHALL return a 401 Unauthorized response.
5. THE Server SHALL load the expected agent API key value from an environment variable defined in the .env configuration file.

### Requirement 25: Security and Data Protection

**User Story:** As a security officer, I want sensitive data encrypted and access audited, so that candidate privacy is protected and compliance requirements are met.

#### Acceptance Criteria

1. THE Server SHALL encrypt the following PII fields at rest using the ENCRYPTION_KEY from environment configuration: Candidate Email, Candidate Phone, Candidate Name, and User Email.
2. THE Server SHALL encrypt the CandidateID and InterviewJourneyID columns in the Candidate-InterviewJourney join table using the ENCRYPTION_KEY from environment configuration.
3. THE Server SHALL record an audit log entry for each stage transition, candidate change, user change, role assignment, InterviewSlot change, and AI agent call, where each entry includes the actor identity, timestamp, action type, affected entity identifier, and a summary of changed values.
4. THE Server SHALL use soft deletion for all entities, retaining records with a DeletedAt timestamp for audit purposes.
5. WHEN a candidate's InterviewJourney reaches OfferAccepted stage, THE Server SHALL encrypt the CandidateID and InterviewJourneyID in the Candidate-InterviewJourney join table so that the hired candidate's interview data cannot be retrieved by lookup.
6. THE Server SHALL validate all input data on external-facing endpoints by enforcing type constraints, maximum field lengths, and allowed value ranges defined in the corresponding Pydantic request models, rejecting invalid input with a 422 response.
7. IF a request attempts to read interview artifacts for a candidate whose Candidate-InterviewJourney join table keys are encrypted, THEN THE Server SHALL return a 403 Forbidden response indicating the data is no longer accessible.
