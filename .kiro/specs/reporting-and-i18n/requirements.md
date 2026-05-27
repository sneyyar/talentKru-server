# Requirements Document

## Introduction

This is the Reporting and Internationalization module of TalentKru.ai Server. It covers analytics/reporting dashboards for monitoring hiring pipeline health and interviewer performance, as well as internationalization and localization support enabling multi-language content delivery and locale-aware formatting across the platform.

Key architectural decisions relevant to this module:
- PostgreSQL for aggregation queries powering reporting dashboards and funnel analytics.
- Locale-aware message catalogs keyed by locale code for rendering API error messages, validation messages, and notification content in the user's preferred language.
- Per-organization notification template variants supporting multiple locales with a three-step cascading fallback: recipient locale → organization default locale → English ("en").
- This module introduces schema additions to the Organization entity (DefaultLocale) and the User entity (Locale default behavior), which are owned by the platform-foundation and identity-and-access modules respectively. Alembic migrations for those additions are coordinated here.

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **User**: An internal user (recruiter, hiring manager, administrator, interviewer) belonging to an organization.
- **Candidate**: A job applicant tracked within an organization's recruiting pipeline.
- **InterviewJourney**: The end-to-end lifecycle of a candidate's application for a specific requisition.
- **InterviewSlot**: A scheduled interview event within a journey, assigned to an interviewer.
- **JobRequisition**: An open position within an organization that candidates are matched against.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.
- **Locale**: A BCP 47 language tag (e.g., en-US, fr-FR, ja-JP) identifying a language and optional region. Maximum 10 characters.
- **Supported Locale**: A locale for which at least one `LocalizedMessage` entry exists in the database with that locale code. English ("en") is always a supported locale because it is the required fallback and must have entries for all message keys.
- **MessageKey**: A dot-separated snake_case identifier (e.g., `error.not_found`, `validation.required_field`) used to look up user-facing strings in the `LocalizedMessage` catalog.
- **DefaultLocale**: The locale configured on an Organization entity that serves as the fallback for all users and candidates within that organization when no more specific locale is available.

## Requirements

### Requirement 1: Reporting and Analytics

**User Story:** As an HR manager, I want reporting dashboards, so that I can monitor hiring pipeline health and interviewer performance.

#### Acceptance Criteria

1. THE Server SHALL expose a candidate funnel report endpoint that returns the count of InterviewJourneys at each stage (Sourced, RecruiterScreen, ManagerScreen, LoopInterview, PanelReview, Rejected, OfferPending, OfferExtended, OfferDeclined, OfferAccepted, Withdrawn) scoped to the authenticated user's organization, with optional filters by:
   - **domain**: the DomainID of a skill Domain entity; filters to journeys whose associated JobRequisition has at least one RequisitionRequiredSkill whose Skill belongs to the specified Domain (join path: InterviewJourney → JobRequisition → RequisitionRequiredSkill → Skill → Domain);
   - **skill**: the SkillID of a Skill entity; filters to journeys whose associated JobRequisition has a RequisitionRequiredSkill for that Skill;
   - **requisition**: the JobRequisitionID; filters to journeys for that specific requisition;
   - **date range** (start_date and end_date, inclusive): filters on the InterviewJourney.StartDate field.
2. THE Server SHALL expose a requisition summary report endpoint showing the count of JobRequisitions in each status (Open, OnHold, Closed, Cancelled) scoped to the authenticated user's organization, with optional filters by department (exact match on JobRequisition.Department), hiring manager (HiringManagerUserID), and date range (start_date and end_date, inclusive, filtering on JobRequisition.CreatedAt).
3. THE Server SHALL expose a questionnaire completion report endpoint showing, for each linked questionnaire on a requisition, the count of CandidateQuestionnaireResponse records with Status=Submitted and the total count of assigned records (all statuses), with optional filters by requisition (JobRequisitionID) and date range (start_date and end_date, inclusive, filtering on CandidateQuestionnaireResponse.UpdatedAt for the submitted date). IF a CandidateQuestionnaireResponse has Status=Submitted, THE Server SHALL use its UpdatedAt timestamp as the submission date for date range filtering purposes.
4. THE Server SHALL expose an interviewer statistics endpoint showing, for each interviewer within the authenticated user's organization: total interview count (count of InterviewSlots with Status=Complete or AttendanceStatus=Attended), no-show rate (count of InterviewSlots with AttendanceStatus=NoShow divided by the sum of InterviewSlots with AttendanceStatus=Attended plus AttendanceStatus=NoShow), and a breakdown of interview counts by slot Type (Manager, Technical, Behavioral, Panel), with optional filters by date range (filtering on InterviewSlot.ScheduledStart) and interviewer (InterviewerUserID).
5. THE Server SHALL expose an interviewer leaderboard endpoint that ranks interviewers within the authenticated user's organization by completed interview count (count of InterviewSlots with Status=Complete) and returns the top N results, where N is specified by the caller with a default of 10 and a maximum of 100, over a configurable period defaulting to INTERVIEW_LEADERBOARD_DEFAULT_PERIOD_DAYS (measured from the current date backward, filtering on InterviewSlot.ScheduledStart).
6. THE Server SHALL restrict all reporting endpoints to users with Administrator or HRManager roles; IF a user without these roles calls a reporting endpoint, THE Server SHALL return a 403 Forbidden response.
7. THE Server SHALL support pagination on all reporting endpoints with a default page size of 20 and a maximum page size of 100.
8. IF a reporting endpoint is called without a date range filter, THEN THE Server SHALL default to the most recent 90 days (from the current UTC date backward).

### Requirement 2: Internationalization and Localization

**User Story:** As a global recruiter, I want the system to support multiple languages and locale-aware formatting, so that users and candidates across different regions receive content in their preferred language and format.

#### Acceptance Criteria

1. THE Server SHALL store a Locale preference per User (a Supported Locale code, maximum 10 characters) with a nullable database column; WHEN a User's Locale column is NULL, THE Server SHALL treat the user's effective locale as the Organization's DefaultLocale. Administrators and SuperAdministrators SHALL be able to set a User's Locale via the user update endpoint. The identity-and-access module's User.locale column SHALL be changed from a hardcoded default of "en-US" to a nullable column with no database-level default, so that the application layer can apply the Organization's DefaultLocale as the fallback.

2. THE Server SHALL add a DefaultLocale column to the Organization entity (VARCHAR 10, NOT NULL, default "en") via an Alembic migration owned by this module. The platform-foundation module's Organization model and DDL SHALL be updated to include this column. The column SHALL be exposed in the OrganizationCreate, OrganizationUpdate, and OrganizationResponse schemas.

3. WHEN processing any API request, THE Server SHALL determine the response locale by evaluating the following priority chain in order, selecting the first Supported Locale found:
   a. The value of the `Accept-Language` HTTP request header, parsed according to RFC 5646 (taking the highest-quality tag that matches a Supported Locale);
   b. The authenticated user's Locale preference (if the user is authenticated and their Locale column is non-NULL);
   c. The Organization's DefaultLocale (if an organization context is available);
   d. English ("en") as the unconditional final fallback.
   For unauthenticated requests (e.g., portal token-only access, password reset, invitation accept), steps (b) and (c) SHALL use the organization derived from the request context (e.g., the organization associated with the portal token or invitation token); IF no organization context is available, THE Server SHALL fall back directly to step (d).

4. THE Server SHALL render all API error messages and validation messages using locale-aware message catalogs: for each user-facing string, THE Server SHALL look up the MessageKey in the LocalizedMessage table using the determined locale; IF no entry exists for that locale, THE Server SHALL fall back to the "en" locale entry; IF no "en" entry exists for the key, THE Server SHALL use the MessageKey itself as the displayed string and log a WARNING indicating a missing translation.

5. THE Server SHALL format date and time values in notification template output according to the determined locale using the Python `babel` library's locale-aware formatting. Dates in JSON API responses SHALL always use ISO 8601 format (YYYY-MM-DD for dates, RFC 3339 for timestamps) regardless of locale. Currency values in notification templates SHALL be formatted using `babel.numbers.format_currency` with the locale's default currency symbol position and decimal separator.

6. THE Server SHALL support per-locale variants of NotificationTemplate entities, where multiple templates can exist for the same OrganizationID and EventType with different Locale values. WHEN rendering a notification, THE Server SHALL resolve the template using the following three-step fallback chain:
   a. Query for a NotificationTemplate matching (OrganizationID, EventType, recipient's locale);
   b. IF not found, query for a NotificationTemplate matching (OrganizationID, EventType, Organization's DefaultLocale);
   c. IF not found, query for a NotificationTemplate matching (OrganizationID, EventType, locale='en').
   IF no template is found after all three steps, THE Server SHALL skip delivery and log an informational message. This three-step chain supersedes the two-step fallback currently implemented in the interview-workflow NotificationService._resolve_template method, which SHALL be updated accordingly.

7. THE Server SHALL store locale-specific content on JobPosting entities via a JobPostingLocaleContent join table with fields: JobPostingLocaleContentID (UUID), JobPostingID (FK to job_postings), Locale (VARCHAR 10, a Supported Locale code), LocalizedDescription (TEXT, max 10000 characters), LocalizedTitle (VARCHAR 200), and AuditFields; with a unique constraint on (JobPostingID, Locale). THE Server SHALL expose sub-resource endpoints for managing locale content on a job posting:
   - `POST /api/v1/job-postings/{job_posting_id}/locale-content` — creates or replaces locale content for a specific locale; restricted to the Recruiter role;
   - `GET /api/v1/job-postings/{job_posting_id}/locale-content` — lists all locale variants for a posting; restricted to Recruiter, Administrator, and HiringManager roles;
   - `DELETE /api/v1/job-postings/{job_posting_id}/locale-content/{locale}` — removes a specific locale variant; restricted to the Recruiter role.
   The original JobPosting.Description field SHALL remain required and serves as the canonical (non-localized) description. Locale content is additive and does not replace the canonical description.

8. WHEN a candidate accesses the portal, THE Server SHALL determine the candidate's locale using the same priority chain defined in Requirement 2.3, with the organization derived from the portal token's associated organization. THE Server SHALL render all portal content (questionnaire instructions, notification emails, error messages) in the determined locale by looking up MessageKeys in the LocalizedMessage catalog with the same fallback behavior defined in Requirement 2.4.

9. THE Server SHALL store all user-facing string content with locale keys in a LocalizedMessage table with fields: LocalizedMessageID (UUID), MessageKey (VARCHAR 200, dot-separated snake_case identifier), Locale (VARCHAR 10), Content (TEXT, max 5000 characters), and AuditFields; with a unique constraint on (MessageKey, Locale). THE Server SHALL expose the following endpoints for managing the message catalog, restricted to the SuperAdministrator role:
   - `GET /api/v1/localized-messages` — lists all entries, with optional filters by MessageKey prefix and Locale;
   - `POST /api/v1/localized-messages` — creates a new entry; rejects duplicate (MessageKey, Locale) pairs with 409;
   - `PATCH /api/v1/localized-messages/{localized_message_id}` — updates the Content of an existing entry;
   - `DELETE /api/v1/localized-messages/{localized_message_id}` — soft-deletes an entry.
   THE Server SHALL ship with a seed data migration that populates English ("en") entries for all system-defined MessageKeys (error messages, validation messages, and notification-related strings) so that the English fallback is always available at deployment time.

10. THE Server SHALL treat all InterviewSlot scheduling as timezone-aware, storing ScheduledStart and ScheduledEnd in UTC. WHEN rendering an InterviewSlot time in a notification template or portal view, THE Server SHALL convert the UTC timestamp to the display timezone specified by the InterviewSlot.Timezone field using the Python `zoneinfo` module, and then format the result using the recipient's determined locale per Requirement 2.5. The InterviewSlot.Timezone field SHALL contain a valid IANA timezone identifier (e.g., "America/New_York", "Europe/Paris").

### Requirement 3: Cross-Module Schema Migrations

**User Story:** As a developer, I want the schema changes required by this module to be clearly owned and sequenced, so that migrations do not conflict with existing module migrations.

#### Acceptance Criteria

1. THE Server SHALL apply the following Alembic migration as part of this module's migration sequence, after all platform-foundation and identity-and-access migrations have been applied:
   - Add `default_locale VARCHAR(10) NOT NULL DEFAULT 'en'` column to the `organizations` table;
   - Alter the `users.locale` column from `VARCHAR(10) NOT NULL DEFAULT 'en-US'` to `VARCHAR(10) NULL` (removing the hardcoded default so the application layer applies the organization's DefaultLocale as the fallback).

2. THE Server SHALL apply a second migration that creates the following new tables: `localized_messages` (per Requirement 2.9), `job_posting_locale_content` (per Requirement 2.7).

3. THE Server SHALL apply a seed data migration that inserts English ("en") LocalizedMessage entries for all system-defined MessageKeys. This migration SHALL run after the `localized_messages` table is created and SHALL be idempotent (using INSERT ... ON CONFLICT DO NOTHING).

4. IF the `users.locale` column is NULL for an existing user after the migration, THE Server SHALL treat that user's locale as their organization's DefaultLocale at the application layer; no backfill of the column is required.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Locale resolution priority order is always respected

*For any* API request carrying an Accept-Language header with a Supported Locale, the determined locale must equal the Accept-Language value, regardless of the authenticated user's Locale preference or the organization's DefaultLocale.

**Validates: Requirements 2.3**

### Property 2: English fallback is always available for any MessageKey

*For any* MessageKey defined in the system, a LocalizedMessage entry with Locale="en" must exist in the database. *For any* locale resolution that produces a non-English locale, if no entry exists for that locale, the English entry must be returned without error.

**Validates: Requirements 2.4, 2.9**

### Property 3: Notification template three-step fallback produces at most one result

*For any* combination of (OrganizationID, EventType, recipient locale), the three-step template resolution must return exactly one template (the first match found in the chain) or null (if no match exists at any step). It must never return more than one template.

**Validates: Requirements 2.6**

### Property 4: Reporting endpoints are always org-scoped

*For any* reporting endpoint request, all returned records must belong to the authenticated user's organization. No records from a different organization must appear in any reporting response, regardless of filter parameters.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

### Property 5: Reporting endpoints reject non-authorized roles

*For any* user who does not hold the Administrator or HRManager role, requests to any reporting endpoint must return a 403 Forbidden response.

**Validates: Requirements 1.6**

### Property 6: Default date range is exactly 90 days

*For any* reporting endpoint called without a date range filter, the effective start date must equal the current UTC date minus 90 days (inclusive) and the effective end date must equal the current UTC date (inclusive).

**Validates: Requirements 1.8**

### Property 7: Locale resolution for unauthenticated requests never errors

*For any* unauthenticated request (portal token-only, password reset, invitation accept), the locale resolution must always produce a valid locale without raising an exception, falling back to "en" if no organization context or Accept-Language header is available.

**Validates: Requirements 2.3**

### Property 8: JobPostingLocaleContent uniqueness per posting and locale

*For any* two JobPostingLocaleContent creation requests with the same JobPostingID and the same Locale targeting the same organization, the second request must be rejected with a 409 Conflict response.

**Validates: Requirements 2.7**
