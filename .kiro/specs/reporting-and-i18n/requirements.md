# Requirements Document

## Introduction

This is the Reporting and Internationalization module of TalentKru.ai Server. It covers analytics/reporting dashboards for monitoring hiring pipeline health and interviewer performance, as well as internationalization and localization support enabling multi-language content delivery and locale-aware formatting across the platform.

Key architectural decisions relevant to this module:
- PostgreSQL for aggregation queries powering reporting dashboards and funnel analytics.
- Locale-aware message catalogs keyed by locale code for rendering API error messages, validation messages, and notification content in the user's preferred language.
- Per-organization notification template variants supporting multiple locales with cascading fallback (recipient locale → organization default locale → English).

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **User**: An internal user (recruiter, hiring manager, administrator, interviewer) belonging to an organization.
- **Candidate**: A job applicant tracked within an organization's recruiting pipeline.
- **InterviewJourney**: The end-to-end lifecycle of a candidate's application for a specific requisition.
- **InterviewSlot**: A scheduled interview event within a journey, assigned to an interviewer.
- **JobRequisition**: An open position within an organization that candidates are matched against.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.

## Requirements

### Requirement 1: Reporting and Analytics

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

### Requirement 2: Internationalization and Localization

**User Story:** As a global recruiter, I want the system to support multiple languages and locale-aware formatting, so that users and candidates across different regions receive content in their preferred language and format.

#### Acceptance Criteria

1. THE Server SHALL store a Locale preference per User (language code and region, e.g., en-US, fr-FR, ja-JP, maximum 10 characters) with a default value inherited from the Organization's DefaultLocale setting.
2. THE Server SHALL store a DefaultLocale field on the Organization entity (maximum 10 characters, default "en") that serves as the fallback locale for all users and candidates within that organization.
3. WHEN processing any API request, THE Server SHALL determine the response locale by checking (in priority order): the Accept-Language header value, the authenticated user's Locale preference, and the organization's DefaultLocale, selecting the first supported locale found.
4. THE Server SHALL render all API error messages, validation messages, and notification template content using locale-aware message catalogs keyed by locale code, with English (en) as the required fallback when a translation is not available for the determined locale.
5. THE Server SHALL format all date, time, number, and currency values in API responses according to the determined locale using standard locale formatting rules (ISO 8601 for dates in JSON, locale-specific display formats in notification templates).
6. THE Server SHALL support per-locale variants of NotificationTemplate entities, where multiple templates can exist for the same OrganizationID and EventType with different Locale values; WHEN rendering a notification, THE Server SHALL select the template matching the recipient's locale with fallback to the organization's default locale template, then to the English (en) template.
7. THE Server SHALL store locale-specific content on JobPosting entities via a JobPostingLocaleContent join table with fields: JobPostingLocaleContentID (UUID), JobPostingID (FK), Locale (string, max 10 characters), LocalizedDescription (max 10000 characters), LocalizedTitle (max 200 characters), and AuditFields, allowing job postings to have descriptions in multiple languages.
8. WHEN a candidate accesses the portal, THE Server SHALL determine the candidate's locale from the Accept-Language header with fallback to the organization's DefaultLocale, and render all portal content (questionnaire instructions, notification emails, error messages) in the determined locale.
9. THE Server SHALL store all user-facing string content with locale keys in a LocalizedMessage table with fields: LocalizedMessageID (UUID), MessageKey (string, max 200 characters), Locale (string, max 10 characters), Content (text, max 5000 characters), and AuditFields, with a unique constraint on (MessageKey, Locale).
10. THE Server SHALL treat all InterviewSlot scheduling as timezone-aware, storing ScheduledStart and ScheduledEnd in UTC with the Timezone field indicating the display timezone for locale-appropriate rendering in notifications and portal views.
