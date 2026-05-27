# Implementation Plan: Reporting and Internationalization

## Overview

This plan implements the Reporting and Internationalization (i18n) module for TalentKru.ai Server. It covers:

1. **Three Alembic migrations** in sequence: cross-module schema changes → new tables → idempotent English seed
2. **New `app/modules/reporting/` module** with five pure-SQL aggregation endpoints
3. **New `app/modules/i18n/` module** with locale resolution, message catalog, and job posting locale content
4. **Cross-module modifications** to `notifications/service.py`, `organizations/models.py`, `users/models.py`, and their Pydantic schemas
5. **Router registration** wiring both new modules into the FastAPI application

All code is Python (FastAPI + SQLAlchemy async). Property-based tests use Hypothesis. Tasks marked `*` are optional and can be skipped for a faster MVP.

---

## Tasks

- [ ] 1. Apply cross-module schema migrations and update existing models
  - [ ] 1.1 Write Alembic migration `xxxx_ri_cross_module_schema.py`
    - Add `default_locale VARCHAR(10) NOT NULL DEFAULT 'en'` to `organizations` table
    - Alter `users.locale` from `VARCHAR(10) NOT NULL DEFAULT 'en-US'` to `VARCHAR(10) NULL` (drop NOT NULL and default)
    - Backfill `notification_templates.locale = 'en'` where `locale IS NULL`
    - Alter `notification_templates.locale` to `NOT NULL`
    - Drop old `uq_notification_templates_org_event` unique constraint and add `uq_notification_templates_org_event_locale (organization_id, event_type, locale)`
    - Set `down_revision` to the last identity-and-access migration
    - _Requirements: 3.1_

  - [ ] 1.2 Update `app/modules/organizations/models.py` and schemas
    - Add `default_locale = Column(String(10), nullable=False, server_default="en")` to the `Organization` SQLAlchemy model
    - Add `default_locale: str = Field(default="en", description="...", max_length=10)` to `OrganizationCreate`, `OrganizationUpdate`, and `OrganizationResponse` Pydantic schemas
    - _Requirements: 2.2, 3.1_

  - [ ] 1.3 Update `app/modules/users/models.py`
    - Change `locale` column from `nullable=False, default="en-US"` to `nullable=True, default=None`
    - _Requirements: 2.1, 3.1_

  - [ ]* 1.4 Write integration test for migration 1
    - Verify `organizations.default_locale` column exists with `NOT NULL DEFAULT 'en'`
    - Verify `users.locale` column is nullable with no database default
    - Verify `notification_templates` unique constraint is `(organization_id, event_type, locale)` after migration
    - _Requirements: 3.1_

- [ ] 2. Create new tables migration and i18n data models
  - [ ] 2.1 Write Alembic migration `xxxx_ri_new_tables.py`
    - Create `localized_messages` table with all columns, indexes, and `uq_localized_messages_key_locale` unique constraint
    - Create `job_posting_locale_content` table with all columns, indexes, and `uq_job_posting_locale_content` unique constraint
    - Set `down_revision` to the cross-module schema migration from task 1.1
    - _Requirements: 2.7, 2.9, 3.2_

  - [ ] 2.2 Implement `app/modules/i18n/models.py`
    - Write `LocalizedMessage` SQLAlchemy model (`localized_message_id`, `message_key`, `locale`, `content`, `AuditMixin`)
    - Write `JobPostingLocaleContent` SQLAlchemy model (`job_posting_locale_content_id`, `job_posting_id` FK, `locale`, `localized_title`, `localized_description`, `AuditMixin`)
    - _Requirements: 2.7, 2.9_

  - [ ]* 2.3 Write integration test for migration 2
    - Verify both tables are created with correct columns, constraints, and indexes
    - Verify FK from `job_posting_locale_content.job_posting_id` to `job_postings`
    - _Requirements: 3.2_

- [ ] 3. Apply seed migration for English LocalizedMessage entries
  - [ ] 3.1 Write Alembic migration `xxxx_ri_seed_en_messages.py`
    - Insert all 12 system-defined English `LocalizedMessage` entries using `INSERT ... ON CONFLICT (message_key, locale) DO NOTHING`
    - Include keys: `error.not_found`, `error.forbidden`, `error.unauthorized`, `error.conflict`, `error.validation_failed`, `error.internal`, `validation.required_field`, `validation.max_length`, `validation.invalid_locale`, `notification.interview_reminder`, `notification.invitation_sent`, `notification.offer_extended`
    - Set `down_revision` to the new-tables migration from task 2.1
    - _Requirements: 2.9, 3.3_

  - [ ]* 3.2 Write unit test for seed migration idempotency
    - Verify the seed migration can be run twice on the same database without error or duplicate rows
    - _Requirements: 3.3_

- [ ] 4. Checkpoint — Verify all three migrations apply cleanly in sequence
  - Run `alembic upgrade head` on a fresh test database and confirm all three migrations succeed without errors.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Reporting Pydantic schemas
  - [ ] 5.1 Write `app/modules/reporting/schemas.py`
    - Implement `StageFunnelItem`, `DateRangeFilters`, `CandidateFunnelResponse`
    - Implement `StatusSummaryItem`, `RequisitionSummaryResponse`
    - Implement `QuestionnaireCompletionItem`, `QuestionnaireCompletionResponse`
    - Implement `InterviewTypeBreakdown`, `InterviewerStatItem`, `InterviewerStatsResponse`
    - Implement `LeaderboardEntry`, `InterviewerLeaderboardResponse`
    - All `Field(description="...")` annotations must be ≥ 10 characters
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 6. Implement ReportingService with pure-SQL aggregation queries
  - [ ] 6.1 Implement `_apply_default_date_range` helper and `ReportingService.__init__` in `app/modules/reporting/service.py`
    - Write `_apply_default_date_range(start_date, end_date) -> tuple[date, date]` returning last 90 days when both are `None`
    - Define `DEFAULT_DATE_RANGE_DAYS = 90`, `MAX_LEADERBOARD_N = 100`, `DEFAULT_LEADERBOARD_N = 10`
    - _Requirements: 1.8_

  - [ ]* 6.2 Write property test for `_apply_default_date_range` (Property 7)
    - **Property 7: Default date range is exactly 90 days**
    - For any mocked `today`, assert `start == today - timedelta(days=90)` and `end == today`
    - Use `@given(today=st.dates(...))` with `patch("app.modules.reporting.service.datetime")`
    - **Validates: Requirements 1.8**

  - [ ] 6.3 Implement `ReportingService.get_candidate_funnel`
    - Single `GROUP BY current_stage` aggregation query scoped to `org_id`
    - Apply optional filters: `domain_id` (join path: Journey → Requisition → RequisitionRequiredSkill → Skill → Domain), `skill_id`, `requisition_id`, `start_date`/`end_date` on `InterviewJourney.start_date`
    - Initialize all `JourneyStage` values to 0 before populating from query results
    - _Requirements: 1.1, 1.7, 1.8_

  - [ ]* 6.4 Write property test for candidate funnel org-scoping and count correctness (Properties 5 & 8)
    - **Property 5: Reporting endpoints are always org-scoped**
    - **Property 8: Funnel counts match the underlying data**
    - For any list of `InterviewJourney` records with varying stages and org IDs, assert all returned counts belong to `org_id` and each stage count equals the number of records at that stage
    - **Validates: Requirements 1.1**

  - [ ] 6.5 Implement `ReportingService.get_requisition_summary`
    - Single `GROUP BY status` aggregation query scoped to `org_id`
    - Apply optional filters: `department` (exact match), `hiring_manager_id`, `start_date`/`end_date` on `JobRequisition.created_at`
    - Initialize all `RequisitionStatus` values to 0 before populating
    - _Requirements: 1.2, 1.7, 1.8_

  - [ ] 6.6 Implement `ReportingService.get_questionnaire_completion`
    - Single `GROUP BY questionnaire_id` aggregation with `COUNT(*)` total and `SUM(CASE WHEN status=SUBMITTED THEN 1 ELSE 0)` submitted
    - Apply optional filter: `requisition_id` (join through `JobRequisitionQuestionnaire`), `start_date`/`end_date` on `CandidateQuestionnaireResponse.updated_at` for submitted records
    - Compute `completion_rate = submitted / total` (0.0 when total is 0)
    - _Requirements: 1.3, 1.7, 1.8_

  - [ ] 6.7 Implement `ReportingService.get_interviewer_stats`
    - Single `GROUP BY interviewer_user_id` aggregation with filtered counts for `total_interviews`, `no_show_count`, `attendance_denominator`, and per-type counts
    - Apply optional filters: `interviewer_id`, `start_date`/`end_date` on `InterviewSlot.scheduled_start`
    - Compute `no_show_rate = no_show_count / attendance_denominator` (0.0 when denominator is 0)
    - _Requirements: 1.4, 1.7, 1.8_

  - [ ]* 6.8 Write property test for no-show rate formula correctness (Property 9)
    - **Property 9: No-show rate formula is correct for all inputs**
    - For any `attended` and `no_show` integers ≥ 0, assert computed rate equals `no_show / (attended + no_show)` when denominator > 0, else 0.0
    - **Validates: Requirements 1.4**

  - [ ] 6.9 Implement `ReportingService.get_interviewer_leaderboard`
    - Single `GROUP BY interviewer_user_id ORDER BY COUNT(*) DESC LIMIT top_n` query scoped to `org_id` and `SlotStatus.COMPLETE`
    - Cap `top_n` at `MAX_LEADERBOARD_N = 100`; default `period_days` from `settings.INTERVIEW_LEADERBOARD_DEFAULT_PERIOD_DAYS`
    - Compute `cutoff = datetime.now(UTC) - timedelta(days=period_days)` and filter on `scheduled_start >= cutoff`
    - _Requirements: 1.5, 1.7, 1.8_

- [ ] 7. Implement Reporting Router
  - [ ] 7.1 Write `app/modules/reporting/router.py`
    - Define `router = APIRouter(prefix="/reports", tags=["reporting"])`
    - Implement all five GET endpoints: `/candidate-funnel`, `/requisition-summary`, `/questionnaire-completion`, `/interviewer-stats`, `/interviewer-leaderboard`
    - Apply `require_role("Administrator", "HRManager")` dependency to all five routes
    - Include full OpenAPI metadata (`operation_id`, `summary`, `description`) on every route
    - Wire `Query` parameters with `ge`/`le` constraints: `offset >= 0`, `limit` in `[1, 100]`, `top_n` in `[1, 100]`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 7.2 Write unit tests for reporting router authorization
    - Verify each of the five endpoints returns 403 for Candidate, Interviewer, and Recruiter roles
    - Verify each endpoint returns 200 for Administrator and HRManager roles
    - **Validates: Requirements 1.6**

- [ ] 8. Checkpoint — Verify all reporting endpoints pass tests
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement I18n Pydantic schemas
  - [ ] 9.1 Write `app/modules/i18n/schemas.py`
    - Implement `LocalizedMessageCreate`, `LocalizedMessageUpdate`, `LocalizedMessageResponse`
    - Implement `JobPostingLocaleContentCreate`, `JobPostingLocaleContentResponse`
    - All `Field(description="...")` annotations must be ≥ 10 characters; enforce `max_length` constraints
    - _Requirements: 2.7, 2.9_

- [ ] 10. Implement I18nService — locale resolution and message catalog
  - [ ] 10.1 Implement `parse_accept_language` and `resolve_locale` pure functions in `app/modules/i18n/service.py`
    - Write `parse_accept_language(header: str) -> list[str]` using the `_ACCEPT_LANGUAGE_RE` regex, returning tags sorted by quality descending
    - Write `resolve_locale(accept_language, user_locale, org_default_locale, supported_locales) -> str` implementing the four-step priority chain; never raises; returns `"en"` as unconditional fallback
    - _Requirements: 2.3_

  - [ ]* 10.2 Write property tests for `resolve_locale` (Properties 1 & 2)
    - **Property 1: Locale resolution priority order is always respected**
    - **Property 2: Locale resolution always produces a valid locale without error**
    - Test 1: For any `accept_language` containing a supported locale, assert result equals that locale regardless of `user_locale` or `org_default`
    - Test 2: For any combination of inputs (including `None`, empty, malformed), assert result is a non-empty string and no exception is raised
    - Use `@given` with `st.one_of(st.none(), st.text(max_size=100))` for `accept_language`
    - **Validates: Requirements 2.3**

  - [ ] 10.3 Implement `I18nService.get_supported_locales`, `get_message`, `list_messages`, `create_message`, `update_message`, `delete_message`
    - `get_supported_locales`: `SELECT DISTINCT locale FROM localized_messages WHERE deleted_at IS NULL`
    - `get_message(key, locale)`: look up by `(key, locale)`; fall back to `locale='en'`; return key string and log WARNING if no "en" entry exists
    - `list_messages`: filter by optional `key_prefix` (LIKE `prefix%`) and `locale`; apply `offset`/`limit`
    - `create_message`: insert new entry; raise `HTTPException(409)` on `UniqueViolation`
    - `update_message`: update `content` field; raise `HTTPException(404)` if not found
    - `delete_message`: soft-delete by setting `deleted_at`; raise `HTTPException(404)` if not found
    - _Requirements: 2.4, 2.9_

  - [ ]* 10.4 Write property test for English message fallback (Property 3)
    - **Property 3: English fallback is always available for any MessageKey**
    - For any `key` and non-English `locale`, when an "en" entry exists in the DB, assert `get_message` returns the English content without error
    - **Validates: Requirements 2.4, 2.9**

  - [ ] 10.5 Implement `I18nService.format_datetime_for_locale` and `format_datetime_for_locale` static methods
    - `format_datetime_for_locale(dt, locale, timezone_str)`: convert UTC `dt` to `ZoneInfo(timezone_str)` if provided; format with `babel_format_datetime`; catch `ZoneInfoNotFoundError` and fall back to `dt.isoformat()` with WARNING log
    - `format_currency_for_locale(amount, currency, locale)`: format with `babel_format_currency`; fall back to `f"{currency} {amount:.2f}"` on exception
    - _Requirements: 2.5, 2.10_

  - [ ] 10.6 Implement `I18nService.upsert_locale_content`, `list_locale_content`, `delete_locale_content`
    - `upsert_locale_content`: verify `job_posting_id` belongs to `org_id` (404 if not); insert new `JobPostingLocaleContent`; raise `HTTPException(409)` on `UniqueViolation`
    - `list_locale_content`: `SELECT * FROM job_posting_locale_content WHERE job_posting_id=? AND org_id=? AND deleted_at IS NULL`
    - `delete_locale_content`: soft-delete by `(job_posting_id, locale, org_id)`; raise `HTTPException(404)` if not found
    - _Requirements: 2.7_

  - [ ]* 10.7 Write property test for `JobPostingLocaleContent` uniqueness (Property 10)
    - **Property 10: JobPostingLocaleContent uniqueness per posting and locale**
    - For any `locale`, `title`, and `description`, assert the first `upsert_locale_content` call succeeds and the second call with the same `(job_posting_id, locale)` raises `HTTPException(409)`
    - **Validates: Requirements 2.7**

- [ ] 11. Implement I18n Router
  - [ ] 11.1 Write `app/modules/i18n/router.py` — LocalizedMessage CRUD endpoints
    - Define `router = APIRouter(tags=["i18n"])`
    - Implement `GET /localized-messages` (SuperAdministrator), `POST /localized-messages` (SuperAdministrator, 201), `PATCH /localized-messages/{id}` (SuperAdministrator), `DELETE /localized-messages/{id}` (SuperAdministrator, 204)
    - Include full OpenAPI metadata on every route
    - _Requirements: 2.9_

  - [ ] 11.2 Write `app/modules/i18n/router.py` — JobPostingLocaleContent sub-resource endpoints
    - Implement `POST /job-postings/{job_posting_id}/locale-content` (Recruiter, 201)
    - Implement `GET /job-postings/{job_posting_id}/locale-content` (Recruiter, Administrator, HiringManager)
    - Implement `DELETE /job-postings/{job_posting_id}/locale-content/{locale}` (Recruiter, 204)
    - Include full OpenAPI metadata on every route
    - _Requirements: 2.7_

  - [ ]* 11.3 Write unit tests for i18n router authorization and error cases
    - Verify `POST /localized-messages` returns 409 on duplicate `(message_key, locale)`
    - Verify `PATCH` and `DELETE` return 404 for non-existent `localized_message_id`
    - Verify `POST /job-postings/{id}/locale-content` returns 404 when `job_posting_id` not in org
    - Verify `DELETE /job-postings/{id}/locale-content/{locale}` returns 404 for non-existent locale
    - _Requirements: 2.7, 2.9_

- [ ] 12. Update NotificationService with three-step template fallback
  - [ ] 12.1 Update `_resolve_template` in `app/modules/notifications/service.py`
    - Replace the existing two-step fallback with the three-step chain: (1) recipient locale, (2) `org.default_locale`, (3) `'en'`
    - Fetch `org.default_locale` from DB in step 2 using `await self.db.get(Organization, org_id)`
    - Skip step 2 if `org_default == locale`; skip step 3 if `locale == 'en'` or `org_default == 'en'`
    - Log `INFO "notification_template_not_found"` when all three steps return `None`
    - _Requirements: 2.6_

  - [ ]* 12.2 Write property test for three-step template fallback (Property 4)
    - **Property 4: Notification template three-step fallback returns at most one result**
    - For any combination of `recipient_locale`, `has_recipient_template`, `has_org_default_template`, `has_en_template` booleans, assert result is `None` or a single `NotificationTemplate` instance, and that it is the first match in the chain
    - **Validates: Requirements 2.6**

  - [ ]* 12.3 Write unit tests for three-step fallback with concrete examples
    - Verify step-1 match is returned when recipient locale template exists
    - Verify step-2 match is returned when only org-default template exists
    - Verify step-3 match is returned when only "en" template exists
    - Verify `None` is returned and INFO is logged when no template exists at any step
    - _Requirements: 2.6_

- [ ] 13. Register new routers in the FastAPI application
  - [ ] 13.1 Register `reporting.router` and `i18n.router` in the main application
    - Import and include `app.modules.reporting.router` under the `/api/v1/` prefix
    - Import and include `app.modules.i18n.router` under the `/api/v1/` prefix
    - Verify all new routes appear in the OpenAPI schema at `/docs`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.7, 2.9_

- [ ] 14. Final checkpoint — Ensure all tests pass
  - Run the full test suite. Ensure all unit tests, property tests, and integration tests pass.
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at migration, reporting, and final integration boundaries
- Property tests validate universal correctness properties using Hypothesis (`@given`, `@settings(max_examples=200)`)
- Unit tests validate specific examples, error conditions, and authorization rules
- All property test files must include the tag comment: `# Feature: reporting-and-i18n, Property {N}: {property_text}`
- The `resolve_locale` function is a pure function (no DB access) — it can be tested without a database fixture
- The `_apply_default_date_range` function is also pure — mock `datetime.now` using `unittest.mock.patch`
- `babel` and `zoneinfo` are standard dependencies; `zoneinfo` is in the Python 3.9+ stdlib
- All JSON API responses use ISO 8601 dates; `babel` formatting is only for notification template output

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "5.1", "9.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["1.4", "2.2", "3.1"] },
    { "id": 3, "tasks": ["2.3", "3.2", "6.1", "10.1"] },
    { "id": 4, "tasks": ["6.2", "6.3", "10.2", "10.3"] },
    { "id": 5, "tasks": ["6.4", "6.5", "6.6", "6.7", "10.4", "10.5"] },
    { "id": 6, "tasks": ["6.8", "6.9", "10.6", "12.1"] },
    { "id": 7, "tasks": ["7.1", "10.7", "11.1", "12.2"] },
    { "id": 8, "tasks": ["7.2", "11.2", "12.3"] },
    { "id": 9, "tasks": ["11.3", "13.1"] }
  ]
}
```
