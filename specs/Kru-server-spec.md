# TalentKru.ai Server Specification (FastAPI Backend)

This document refines the product-level **TalentKru.ai – Functional & Technical Requirements Specification** into an implementation-focused view for the **Python FastAPI backend**. It is intended as input to Kiro Feature Specs (requirements/design/tasks) and as the canonical reference for API contracts and backend responsibilities.

The backend is responsible for:

- Multi-tenant identity, authorization, and RBAC.
- Core data model and persistence (candidates, requisitions, skills, interviews, questionnaires, etc.).
- Interview journeys, slots, feedback, and AI-assisted behavioral summaries.
- Candidate portal backend (token auth, questionnaire ledger, availability & schedule data).
- AI matching and agent orchestration (resume ingestion, matching, feedback drafts, notifications).
- Reporting, analytics, and observability.

This spec deliberately excludes client-side concerns (navigation, layout, local UI state) which are captured in `client-spec.md`.

---

## 1. Backend Architecture Overview

### 1.1 Core Stack

- **Framework**: Python FastAPI REST API.
- **Data Store**: PostgreSQL (or compatible RDBMS) with `pgvector` extension for semantic search and embeddings.
- **Object Storage**: S3-compatible service for resumes and other binary artifacts.
- **Agentic Layer**: Google ADT + SKILLs, exposed via internal APIs or SDK for:
  - Resume parsing and skill extraction.
  - Embedding generation and vector search.
  - Matching explanations.
  - Behavioral interview feedback summarization.
- **Messaging/Email**: SMTP or transactional provider (SES, SendGrid) orchestrated via NotificationAgent.
- **Configuration**: `.env` (12-factor style) for environment-specific settings (storage backend, AI providers, encryption keys, feature flags).

### 1.2 Services and Modules

The backend is a monolithic FastAPI app logically organized into modules:

- `auth` – authentication, JWT/session management, SSO/OAuth2 integration for internal users; token-based candidate sessions Also support simple login via one-way hash encrypted passwords.
- `rbac` – roles, permissions, organization scoping, route guards.
- `users` – user CRUD, org hierarchy, manager relationships. All users except superAdmin are linked to organizations.
- `organizations` – client organizations, white-label settings.
- `candidates` – candidate profiles, job history, global status. Candidates are always linked to an organization.
- `resumes` – file upload, storage, ingestion, and parsed resume data. resumes are associated with candidates.
- `requisitions` – job requisitions, hiring manager assignment, dashboard queries.
- `job_profile` - represents a job category. requisitions have a job_profile. It represents a set of required or desired skills candidates need to possess.
- `job_posting` - represents the details of job description and , work locations and salary ranged posted for a job. job_posting could linked to a sourcing channel such as 'LinkedIn'
- `skills` – domain/skill taxonomy and candidate/requisition skill mappings.
- `matching` – AI semantic matching engine and CandidateRequisitionMatch.
- `journeys` – InterviewJourney lifecycle and stage history.
- `interviews` – InterviewSlot scheduling, interviewer responses, attendance tracking, interview feedback entities.
- `questionnaires` – questionnaire definitions, questions, and candidate response ledger.This is represented in YAML format in database.
- `portal` – candidate portal token issuance, validation, and data feeds.
- `agents` – integration with ResumeIngestionAgent, MatchingAgent, QuestionnaireOrchestratorAgent, BehavioralFeedbackAgent, NotificationAgent.
- `reporting` – reporting endpoints (funnel, questionnaire completion, interviewer stats and leaderboards).
- `observability` – logging, metrics, traces.

All modules share a common database layer (SQLAlchemy/ORM or similar) and common audit/logging utilities.

---

## 2. Multi-Tenancy, Identity, and RBAC

### 2.1 Organization and User Model

**Organization**

- `OrganizationID` (PK).
- Name, slug, branding settings (logo URL, primary/secondary colors, terms & conditions URL).
- Feature flags (enabled modules, AI features, notification policies).
- Audit fields.

**User**

- `UserID` (PK, UUID or numeric).
- `OrganizationID` (FK) – user belongs to exactly one organization.
- Email (unique within organization, required).
- GivenName, LastName.
- Status (Active, Inactive, Locked).
- `ManagerUserID` (FK to User) – org hierarchy.
- Authentication metadata (SSO subject ID, last login, MFA status).
- Audit fields.

**Role** and **UserRole** as in the product spec:

- Roles: `Administrator`, `Recruiter`, `HiringManager`, `CommitteeMember`, `HRManager`, `Interviewer`, `SuperAdministrator`.
- `UserRole` bridges users and roles (many-to-many).

### 2.2 Authentication

**Internal Users**

- Auth via corporate SSO/OAuth2/OpenID Connect.
- Backend validates ID tokens or uses OAuth code flow behind a reverse proxy.
- On first login, user is mapped to an existing User record by email; SuperAdmin/Admin may auto-provision users with default roles.

**Candidates (Portal)**

- No SSO. Access via **token URL + email challenge** (see portal section):
  - Candidate clicks URL containing a `Token` (from `CandidatePortalToken` table).
  - Backend verifies token (exists, active, not expired, belongs to candidate).
  - Candidate enters email; backend verifies it matches `Candidate.Email`.
  - Backend issues a short-lived candidate session (JWT or server-side session cookie) scoped to that candidate and organization.

### 2.3 Authorization & RBAC

RBAC rules enforced via FastAPI dependencies/middleware:

- All internal endpoints require a valid user principal with roles and `OrganizationID`.
- All candidate portal endpoints require a valid candidate session with `CandidateID` and `OrganizationID`.
- Permissions:
  - Only `Administrator`/`SuperAdministrator` can manage users and roles.
  - Only `Recruiter` can create candidates and job requisitions (unless configured otherwise).
  - Only `Recruiter` and `HiringManager` can move InterviewJourneys between stages.
  - Candidate portal endpoints are restricted to the owning candidate and their journeys.
  - Reporting endpoints require `Administrator` or `HRManager`, with possible further scope restrictions (department).

Multi-tenancy:

- Every entity that is logically owned by an organization includes `OrganizationID`.
- All queries must filter by `OrganizationID` derived from the authenticated principal.

---

## 3. Core Domain Model & Persistence

### 3.1 Candidate & Resume

**Candidate**

Fields and rules as in the product spec, implemented as a DB model with:

- `CandidateID` (PK), `OrganizationID` (FK).
- Name, contact info, location.
- `GlobalStatus` enum: `Active`, `Interviewing`, `Expired`, `Ineligible`, `Deleted`.
- Audit fields.

Backend behaviors:

- New candidates default to `Active`.
- A scheduled job sets `Expired` for candidates with no active InterviewJourneys and no profile updates for 90 days.
- `Ineligible` is a manual update requiring `IneligibilityReason`.
- `Deleted` is logical deletion; entity is hidden from default search and matching but kept for audit.

**Resume**

- `ResumeID` (PK), `CandidateID` (FK optional at upload time).
- `OrganizationID` (FK).
- `StorageLocation`, `MimeType`, `FileName`, `UploadedByUserID`.
- Parsed data (optional denormalized fields) and `IsPrimary` flag.
- Audit fields.

Resume ingestion workflow:

- File upload endpoint accepts PDF/DOC/DOCX.
- Backend stores file in configured storage backend.
- Backend enqueues a job to call `ResumeIngestionAgent` with storage URI and metadata.
- Agent extracts contact details, work history, skills, and embeddings, then POSTs structured data back to backend.
- Backend updates/creates Candidate and `CandidateJobHistory` records accordingly and associates resume.

### 3.2 Job Requisitions

**JobRequisition**

- `JobRequisitionID` (PK).
- `OrganizationID` (FK).
- `ExternalRequisitionID` (e.g., Workday ID).
- Title, Department, Location.
- `HiringManagerUserID` (FK to User).
- Status: `Open`, `OnHold`, `Closed`, `Cancelled`.
- Description (markdown/rich text).
- Domain and skill requirements (relationships to `RequisitionRequiredSkill`).
- Audit fields.

Backend behaviors:

- Recruiters create and manage requisitions.
- Optionally ingest requisitions from external HR systems (e.g., Workday) and map by `ExternalRequisitionID`.

### 3.3 Domain & Skills

**Domain**, **Skill**, **CandidateSkill**, **RequisitionRequiredSkill** implemented as relational tables:

- Standardized proficiency scale (1–5) stored as integers.
- Each `CandidateSkill` may track `ProficiencyRank`, `YearsOfExperience`, and source metadata (manual, parsed, inferred).
- Each `RequisitionRequiredSkill` may track `RequiredProficiencyRank` and weight/priority.

### 3.4 Interview Journeys & Slots

**InterviewJourney**

- `InterviewJourneyID` (PK).
- `OrganizationID` (FK).
- `JourneyPublicID` (random non-guessable string).
- `CandidateID` (FK), `JobRequisitionID` (FK).
- `CurrentStage` enum (Sourced, RecruiterScreen, ManagerScreen, LoopInterview, PanelReview, Rejected, OfferPending, OfferExtended, OfferDeclined, OfferAccepted, Withdrawn).
- `CurrentStageStatus` for stages with sub-status (Scheduled, InProgress, Complete).
- `OverallStatus` (may mirror stage or provide high-level state).
- Offer decision timestamps and `StartDate` if applicable.
- Audit fields.

**InterviewJourneyStageHistory**

- Records each stage and sub-status transition with `ChangedByUserID`, `ChangedAt`, and optional comments.

**InterviewSlot**

- `InterviewSlotID` (PK).
- `OrganizationID` (FK).
- `InterviewJourneyID` (FK).
- Type: `Manager`, `Technical`, `Behavioral`, `Panel`, etc.
- `ScheduledStart`, `ScheduledEnd`, `Timezone`.
- `Status`: `Scheduled`, `InProgress`, `Complete`, `Cancelled`.
- `InvitationStatus`: `Pending`, `Accepted`, `Declined`.
- `AttendanceStatus`: `Unknown`, `Attended`, `NoShow`.
- `InterviewerUserID`.
- `FeedbackID` (FK to feedback table).
- Audit fields.

Business rules enforced by backend:

- Only interviewers under their capacity (`MaxInterviewsPerDay/Week`) may be assigned or sign up.
- `InvitationStatus` transitions are triggered by interviewer responses.
- `AttendanceStatus` updated after the interview either programmatically (calendar integration) or via manual update.

### 3.5 Questionnaires & Responses

**Questionnaire**, **Question**, **JobRequisitionQuestionnaire**, **CandidateQuestionnaireResponse**, **CandidateQuestionnaireAnswer** as in the product spec:

- `CandidateQuestionnaireResponse` tracks per-candidate, per-questionnaire status: `Incomplete`, `Draft`, `Submitted`.
- `CandidateQuestionnaireAnswer` stores answers as JSON, keyed by `QuestionID`.

Backend behaviors:

- Creating a new requisition associates questionnaires via `JobRequisitionQuestionnaire`.
- `QuestionnaireOrchestratorAgent` may create missing `CandidateQuestionnaireResponse` records when a candidate is attached to new requisitions.

### 3.6 Candidate Portal Tokens

**CandidatePortalToken**

- `CandidatePortalTokenID` (PK).
- `CandidateID` (FK).
- `OrganizationID` (FK).
- `Token` (random URL-safe string).
- `ExpiresAt`, `IsActive`.
- Audit fields.

Backend responsibilities:

- Generate tokens on demand (per invitation) with configurable TTL from `.env`.
- Validate tokens on portal access; rotate or revoke when required.

### 3.7 Availability & Interviewer Preferences

**CandidateAvailabilitySlot**

- `CandidateAvailabilitySlotID` (PK).
- `CandidateID` (FK).
- `OrganizationID` (FK).
- Interview type: `RecruiterScreen`, `ManagerScreen`, `LoopInterview`.
- `StartTime`, `EndTime`, `Timezone`.
- Status: `Active`, `Cancelled`.
- Audit fields.

**InterviewerPreference**

- `InterviewerPreferenceID` (PK).
- `InterviewerUserID` (FK), `OrganizationID`.
- Allowed interview types.
- `MaxInterviewsPerDay`, `MaxInterviewsPerWeek`.
- Preferred working hours per weekday.
- Audit fields.

Backend uses these entities to filter candidate-available and interviewer-eligible slots when creating `InterviewSlot` records.

Note:
 * All entities in the database has following  Audit fields: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.  This fields are autopopulated by the services.
 * Database supports horizontal sharding at organization level. Organization entity  includes shard_id. DB Service needs to identify shard associated with the organization. All superAdmin tables are stored in shard 0, which is the default shard.



---

## 4. Agentic Workflows & AI Integration

### 4.1 ResumeIngestionAgent

Responsibilities:

- Retrieve resume file from storage.
- Parse contact details, job history, and skill mentions.
- Normalize skills against the Skill taxonomy.
- Generate embeddings for resume segments.
- POST results to backend ingestion endpoint.

Backend responsibilities:

- Define a secure ingestion endpoint (e.g., `/internal/agents/resume-ingestion-callback`).
- Map agent payload to Candidate, CandidateJobHistory, CandidateSkill, and Resume entities.
- Handle failures (e.g., log, notify recruiter, provide manual entry path).

### 4.2 MatchingAgent

Responsibilities:

- Compute embeddings for JobRequisitions using description, skills, and domain.
- Run vector search over candidate embeddings (respecting filters: not Ineligible, not Expired, not Deleted).
- Combine semantic similarity with structured skill matching to compute `MatchScore`.
- Generate human-readable `MatchExplanation`.
- Persist `CandidateRequisitionMatch` records.

Backend responsibilities:

- Expose endpoints to trigger matching (`POST /requisitions/{id}/matches/recompute`).
- Serve ranked matches (`GET /requisitions/{id}/matches`).

### 4.3 QuestionnaireOrchestratorAgent

Responsibilities:

- When a candidate is associated with new requisitions, determine required questionnaires.
- Check existing `CandidateQuestionnaireResponse` ledger.
- Create missing responses with `Status = Draft`.

Backend responsibilities:

- Provide APIs for the agent to query requisitions and questionnaires and to create responses.

### 4.4 NotificationAgent

Responsibilities:

- Send:
  - Candidate questionnaire invitations (portal URL).
  - Questionnaire submission confirmations.
  - Internal notifications on stage transitions.
  - Interview invitations and reminders.
  - Notifications to interviewers when: candidate moves to `OfferAccepted` and when `StartDate` is reached.

Backend responsibilities:

- Publish domain events (e.g., `journey.stage_changed`, `questionnaire.submitted`, `interview.created`, `offer.accepted`) to which NotificationAgent subscribes.
- Provide templates and org-level configuration for notifications.

### 4.5 BehavioralFeedbackAgent

Responsibilities:

- Accept transcript text and contextual metadata for an InterviewSlot.
- Generate structured behavioral feedback draft (competency ratings + narrative summary).
- Return payload for storage as `BehavioralFeedbackDraft`.

Backend responsibilities:

- Expose a secure endpoint for BehavioralFeedbackAgent.
- Persist drafts and final submitted feedback.
- Enforce that only assigned interviewers can generate/edit drafts for their slots.

---

## 5. API Surface (High-Level)

The backend exposes REST endpoints broadly matching the product spec. This section groups them by module; exact OpenAPI definitions will be maintained in `openapi.yaml` and generated from FastAPI.

To ensure an AI agent can dynamically read and understand the REST APIs, you must enforce the following coding standards across all routes and models:

Pydantic Models: Every field must use Field(description="...") to explicitly tell the AI what the data represents.

FastAPI Routes: Every @app.get/post/put decorator must include:

operation_id: A clear, snake_case function name (e.g., get_user_profile). The AI uses this as the "Tool Name".

summary: A short, one-sentence action (e.g., "Retrieve User Profile").

description: A detailed prompt for the AI explaining exactly when to use this tool and what it returns.

**Security Bridge**
Since the main application requires OAuth/JWT (as defined in previous specs), the MCP endpoints (/mcp/sse and /mcp/message) must either:

Be protected by the same Depends(get_current_user) JWT logic.

Require a dedicated X-Agent-API-Key header so only your authorized AI orchestrator can access the MCP tool list.

### 5.1 Auth & Users

- `POST /auth/login` – internal login (if not fully SSO-driven; may be stubbed when fronted by SSO).
- `GET /users` – list users (Admin only).
- `POST /users` – create user (Admin only).
- `PATCH /users/{id}` – update user (Admin only).
- `GET /roles` – list roles.
- `POST /users/{id}/roles` – assign/remove roles.

### 5.2 Candidates & Resumes

- `POST /candidates` – create candidate.
- `GET /candidates` – search candidates (name/email/status, org-scoped).
- `GET /candidates/{id}` – get candidate details.
- `PATCH /candidates/{id}` – update candidate fields.
- `POST /candidates/{id}/resumes` or `POST /resumes/import` – upload resume, trigger ingestion.
- `GET /candidates/{id}/resumes` – list resumes.
- `GET /resumes/{id}` – resume metadata and parsed fields.
- `PATCH /resumes/{id}` – update parsed segments.

### 5.3 Requisitions & Matching

- `POST /requisitions` – create requisition.
- `GET /requisitions` – list/filter requisitions (by manager, status, domain).
- `GET /requisitions/{id}` – requisition details.
- `PATCH /requisitions/{id}` – update requisition.
- `POST /requisitions/{id}/candidates/{candidateId}` – associate candidate.
- `POST /requisitions/{id}/required-skills` – configure required skills.
- `GET /requisitions/{id}/matches` – get ranked candidate matches.
- `POST /requisitions/{id}/matches/recompute` – trigger matching.

### 5.4 Interview Journeys & Interviews

- `POST /journeys` – create InterviewJourney for candidate+requisition.
- `GET /journeys` – list journeys (filters by candidate/requisition/stage).
- `GET /journeys/{id}` – journey details.
- `POST /journeys/{id}/stage-transitions` – move journey between stages.
- `GET /journeys/{id}/stage-history` – history of transitions.
- `POST /journeys/{id}/interviews` – create InterviewSlot.
- `PATCH /interviews/{id}` – update interview (time, status, invitationStatus, attendanceStatus).
- `POST /interviews/{id}/invite` – send invite to interviewer.
- `POST /interviews/{id}/respond` – interviewer Accept/Decline.
- `POST /interviews/{id}/feedback` – submit structured feedback.
- `POST /interviews/{id}/behavioral-feedback-draft` – submit transcript, trigger BehavioralFeedbackAgent, persist draft.
- `GET /interviews/{id}/feedback` – retrieve feedback (role-restricted).

### 5.5 Questionnaires & Candidate Portal

- `GET /questionnaires` – list questionnaires.
- `POST /questionnaires` – create questionnaire.
- `GET /questionnaires/{id}` – questionnaire details.
- `POST /questionnaires/{id}/questions` – add questions.
- `POST /requisitions/{id}/questionnaires` – link questionnaire to requisition.

Candidate portal endpoints:

- `GET /portal/{token}` – validate portal token, return portal metadata.
- `POST /portal/{token}/verify-email` – verify candidate email, establish session.
- `GET /portal/questionnaires` – list questionnaires and status for current candidate.
- `GET /portal/questionnaires/{questionnaireId}` – get questions and existing answers.
- `POST /portal/questionnaires/{questionnaireId}/save-draft` – save draft answers.
- `POST /portal/questionnaires/{questionnaireId}/submit` – submit answers.
- `GET /portal/availability` – list candidate availability slots.
- `POST /portal/availability` – create/update availability.
- `GET /portal/schedule` – list upcoming and past interviews for candidate.

### 5.6 Reporting

- `GET /reports/candidate-funnel` – funnel metrics by domain/skill/requisition.
- `GET /reports/requisition-summary` – summary of requisition pipeline.
- `GET /reports/questionnaire-completion` – questionnaire completion rates.
- `GET /reports/interviewer-stats` – interview counts, no-shows, breakdown by type.
- `GET /reports/interviewer-leaderboard` – top N interviewers over last 30/60 days with filters.

---

## 6. Non-Functional Requirements

### 6.1 Security & Privacy

- All internal APIs require authenticated requests (JWT/OAuth2).
- All PII stored with encryption at rest for sensitive fields.
- `CandidateJourneyLink` uses column-level or blob encryption with key from `.env`.
- Candidate portal tokens:
  - Long, random, single-use or revocable tokens.
  - Strict validation and rate limiting on token verification.
- Detailed audit logs for:
  - Stage transitions.
  - Candidate and user changes.
  - Role assignments.
  - InterviewSlot changes.
  - AI agent calls.

### 6.2 Performance & Scalability

- Resume parsing, matching, and AI feedback generation are asynchronous operations.
- FastAPI endpoints return quickly and expose polling or webhooks if needed.
- Vector search latency targets: < 500 ms under typical loads.
- Reporting endpoints may support pagination and pre-aggregation where necessary.

### 6.3 Observability

- Structured logging for all key workflows with correlation IDs.
- Metrics:
  - Number of resumes parsed.
  - Match computation duration and counts.
  - Questionnaire completion events.
  - AI error rates.
  - Interview volume by stage, type, org.
  - No-show rates.
- Distributed tracing integrated with Google ADT workflows and major service boundaries.

### 6.4 Configuration & Environment

- `.env` controls:
  - Storage backend (`STORAGE_BACKEND`).
  - `RESUME_BUCKET_NAME`.
  - `ENCRYPTION_KEY`.
  - `INCLUDE_QR_RESPONSES_IN_EMAIL`.
  - `PORTAL_TOKEN_TTL_DAYS`.
  - AI model identifiers and endpoints.
  - `INTERVIEW_LEADERBOARD_DEFAULT_PERIOD_DAYS`.
- No hard-coded config values; everything injectable via environment or config service.

## 7.JWT-Based Local Authentication Bridge to OAuth2

### **7.1. Scope:**

* Creation of a local `/token` generation endpoint.
* Implementation of password hashing and verification.
* Implementation of JWT signing and validation.
* Securing existing API routes using FastAPI dependencies.


### **7.2. System Architecture**

The authentication flow is strictly stateless. No session data will be stored on the server or in the database.

1. **Client Request:** Client sends `username` and `password` via `application/x-www-form-urlencoded` to the `/token` endpoint.
2. **Validation:** The Auth Service retrieves the hashed password from the database and verifies it against the plaintext input using bcrypt.
3. **Token Issuance:** The Auth Service generates a short-lived JWT, signed with a symmetric secret key (HMAC-SHA256).
4. **Resource Access:** Client requests secured resources by passing the JWT in the `Authorization` header. FastAPI intercepts, decodes, and validates the signature and expiration before allowing the request to proceed.

---

### **7.3. Data Models**

*(Note: These represent the logical schema to be implemented via Pydantic and your chosen ORM like SQLAlchemy)*

**7.3.1. Token Models (Pydantic)**

| Model Name | Field | Type | Description |
| --- | --- | --- | --- |
| `Token` | `access_token` | `str` | The encoded JWT string. |
| `Token` | `token_type` | `str` | Strictly set to `"bearer"`. |
| `TokenData` | `username` | `str` | Extracted from the `sub` claim of the JWT payload. |

### **7.4. API Specifications**

#### **POST `/token**`

* **Purpose:** Authenticate user and issue JWT.
* **Content-Type:** `application/x-www-form-urlencoded`
* **Request Body (OAuth2PasswordRequestForm):**
* `username` (string, required)
* `password` (string, required)


* **Success Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}

```


* **Error Responses:**
* `401 Unauthorized` (Incorrect username or password)
* `422 Validation Error` (Malformed request)



#### **Protected Routes (Global Specification)**

* **Requirement:** Must include header `Authorization: Bearer <token>`.
* **Implementation:** Inject `Depends(get_current_user)` into the route parameters.
* **Error Responses:**
* `401 Unauthorized` (Missing token, invalid token, or expired token).




---

## 8. Open Technical Questions (Server)

- Exact vector DB choice (pgvector vs dedicated vector store) and deployment pattern.
- Strategy for Workday/ATS integration (direct REST/SOAP vs RaaS vs EIB) and mapping to `ExternalRequisitionID`.
- Calendar integration depth (full bi-directional sync vs one-way creation + manual corrections).
- Data retention policies for transcripts and behavioral feedback drafts.
- Rollout strategy for AI features, including org-level toggles and safety rails.
