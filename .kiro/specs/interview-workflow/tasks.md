# Implementation Plan: Interview Workflow

## Overview

Implement the Interview Workflow module for TalentKru.ai using FastAPI, async SQLAlchemy, and Python. The module covers eight sub-modules: journey lifecycle FSM with stage history and OfferAccepted encryption, slot scheduling with interviewer preference enforcement, structured feedback with AI-assisted behavioral analysis, questionnaire YAML validation and response lifecycle, candidate self-service portal with dual auth, organization email configuration with a global system switch, candidate availability with cascade cancellation, and a notification agent with two-level switch, template resolution, exponential backoff retry, and 24-hour reminder scheduling. All 22 correctness properties are verified using Hypothesis property-based tests with `max_examples=100`.

All code follows the conventions established in the Platform Foundation and Identity and Access modules: async SQLAlchemy sessions, soft delete, AES-256-GCM PII encryption via `encrypt_field`/`decrypt_field`, structlog structured logging, domain events via `publish_event()` with persist-first pattern, and `require_role()` dependency factories.

---

## Tasks

- [x] 1. Set up module structure, data models, and Alembic migration
  - Create directory tree: `app/modules/{journeys,slots,feedback,questionnaires,portal,email_config,availability,notifications}/` with `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py` stubs; add `notifications/email_delivery.py` stub
  - Add `hypothesis`, `pytest-asyncio`, `httpx`, `pyjwt`, `pyyaml` to `pyproject.toml` test/runtime dependencies if not already present
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 6.2, 7.1, 8.7_

- [x] 2. Implement journey data models and Alembic migration
  - [x] 2.1 Create journey models in `app/modules/journeys/models.py`
    - Define `JourneyStage`, `JourneyStageStatus`, `JourneyOverallStatus` enums
    - Define `InterviewJourney(Base, AuditMixin, VersionMixin)` with all columns from the DDL summary; add partial indexes `idx_journeys_org_stage` and `idx_journeys_candidate`
    - Define `InterviewJourneyStageHistory(Base, AuditMixin)` with `from_stage`, `to_stage`, `changed_by_user_id`, `changed_at`, `comments` (VARCHAR 2000); add index `idx_stage_history_journey`
    - Define `CandidateInterviewJourney(Base, AuditMixin)` with `candidate_id` (VARCHAR 512), `interview_journey_id` (VARCHAR 512), `candidate_id_encrypted` (nullable), `interview_journey_id_encrypted` (nullable), `is_encrypted` (Boolean, default False), `associated_at`
    - _Requirements: 1.1, 1.4, 1.6_

  - [x] 2.2 Create slot, feedback, questionnaire, portal, email config, availability, and notification models
    - `app/modules/slots/models.py`: `SlotType`, `SlotStatus`, `InvitationStatus`, `AttendanceStatus` enums; `InterviewSlot(Base, AuditMixin, VersionMixin)` with all DDL columns and indexes; `InterviewerPreference(Base, AuditMixin, VersionMixin)` with `UniqueConstraint("interviewer_user_id", "organization_id")`, `allowed_interview_types` (ARRAY), `max_interviews_per_day` CHECK (1–20), `max_interviews_per_week` CHECK (1–100), `working_hours` (JSONB)
    - `app/modules/feedback/models.py`: `FeedbackType`, `FeedbackStatus`, `HiringRecommendation` enums; `InterviewFeedback(Base, AuditMixin, VersionMixin)` with `competency_ratings` (JSONB), `narrative` (VARCHAR 5000), `hiring_recommendation`; add index `idx_feedback_slot`
    - `app/modules/questionnaires/models.py`: `ResponseStatus` enum; `Questionnaire(Base, AuditMixin, VersionMixin)`, `JobRequisitionQuestionnaire(Base, AuditMixin)` with `UniqueConstraint`, `CandidateQuestionnaireResponse(Base, AuditMixin, VersionMixin)` with `UniqueConstraint("candidate_id", "questionnaire_id")`, `CandidateQuestionnaireAnswer(Base, AuditMixin)` with unique FK
    - `app/modules/portal/models.py`: `CandidatePortalToken(Base, AuditMixin)` with `token_hash` (VARCHAR 64, unique), `expires_at`, `is_active`; add index `idx_portal_tokens_candidate`
    - `app/modules/email_config/models.py`: `ProviderType` enum; `OrganizationEmailConfig(Base, AuditMixin, VersionMixin)` with encrypted `smtp_password` and `third_party_api_key` columns; `SystemSetting(Base, AuditMixin)` with `setting_key` as primary key
    - `app/modules/availability/models.py`: `AvailabilityInterviewType`, `AvailabilityStatus` enums; `CandidateAvailabilitySlot(Base, AuditMixin)`
    - `app/modules/notifications/models.py`: `NotificationStatus` enum; `NotificationTemplate(Base, AuditMixin, VersionMixin)` with `UniqueConstraint("organization_id", "event_type", "locale")`; `NotificationRecord(Base, AuditMixin)` with `attempt_count`, `delivered_at`
    - _Requirements: 2.1, 2.8, 3.1, 4.1, 4.6, 5.1, 6.1, 6.2, 7.1, 8.7_

  - [x] 2.3 Write Alembic migration for all interview-workflow tables
    - Generate DDL for all 14 tables: `interview_journeys`, `interview_journey_stage_history`, `candidate_interview_journeys`, `interview_slots`, `interviewer_preferences`, `interview_feedback`, `questionnaires`, `job_requisition_questionnaires`, `candidate_questionnaire_responses`, `candidate_questionnaire_answers`, `candidate_portal_tokens`, `organization_email_configs`, `system_settings`, `candidate_availability_slots`, `notification_templates`, `notification_records`
    - Include seed row: `INSERT INTO system_settings (setting_key, setting_value, description) VALUES ('email_notifications_enabled', 'true', 'Global master switch for all outbound email delivery')`
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 6.2, 7.1, 8.7_


- [x] 3. Implement Pydantic schemas for all modules
  - [x] 3.1 Create journey and slot schemas
    - `app/modules/journeys/schemas.py`: `JourneyCreate` (candidate_id, job_requisition_id), `JourneyTransitionRequest` (to_stage, comments optional max 2000 chars), `JourneyResponse` (all fields including journey_public_id, version), `StageHistoryResponse` (from_stage, to_stage, changed_by_user_id, changed_at, comments)
    - `app/modules/slots/schemas.py`: `SlotCreate` (journey_id, type, scheduled_start, scheduled_end, timezone, interviewer_user_id optional), `SlotUpdate` (status, invitation_status, attendance_status), `SlotResponse` (all fields), `InterviewerPreferenceCreate` (allowed_interview_types, max_interviews_per_day 1–20, max_interviews_per_week 1–100, working_hours optional)
    - Every field must include `Field(description="...")` with description ≥10 characters
    - _Requirements: 1.1, 1.4, 2.1, 2.8_

  - [x] 3.2 Create feedback, questionnaire, portal, email config, availability, and notification schemas
    - `app/modules/feedback/schemas.py`: `FeedbackCreate` (slot_id, competency_ratings dict, narrative max 5000, hiring_recommendation), `FeedbackUpdate` (same optional fields), `FeedbackResponse`, `TranscriptRequest` (slot_id, transcript max 50000 chars)
    - `app/modules/questionnaires/schemas.py`: `QuestionnaireCreate` (title, questions_yaml), `QuestionnaireResponse`, `ResponseCreate` (answers dict, is_final_submit bool)
    - `app/modules/portal/schemas.py`: `PortalTokenResponse` (raw_token, expires_at), `PortalVerifyRequest` (token, email), `PortalJWTResponse` (access_token, token_type), `PortalQuestionnaireResponse`
    - `app/modules/email_config/schemas.py`: `EmailConfigCreate` (provider_type, all provider fields, from_address, from_name), `EmailConfigUpdate` (all optional), `EmailConfigResponse` (no plaintext passwords), `SystemSettingResponse`, `SystemSettingUpdate` (setting_value)
    - `app/modules/availability/schemas.py`: `AvailabilityCreate` (interview_type, start_time, end_time, timezone), `AvailabilityResponse`
    - `app/modules/notifications/schemas.py`: `NotificationTemplateCreate` (event_type, subject max 200, body_template, is_enabled, locale optional), `NotificationTemplateResponse`, `NotificationRecordResponse`
    - _Requirements: 3.1, 4.1, 5.1, 6.1, 6.2, 7.1, 8.7_


- [x] 4. Implement InterviewJourneyService and journey router
  - [x] 4.1 Implement `InterviewJourneyService` in `app/modules/journeys/service.py`
    - `create_journey`: generate `journey_public_id = secrets.token_urlsafe(16)` (≥22 URL-safe chars); insert `InterviewJourney(current_stage=SOURCED, overall_status=ACTIVE)`; insert `CandidateInterviewJourney` join record; `await db.flush()`; call `publish_event("journey_created", ...)`
    - `transition_stage`: validate `to_stage in VALID_TRANSITIONS[journey.current_stage]` (400 on invalid); validate `len(comments) <= 2000` (422 if exceeded); set `current_stage_status=None` for terminal stages; on `OFFER_ACCEPTED` set `overall_status=COMPLETED`, `offer_responded_at=now()`, call `_encrypt_join_record`; on `OFFER_EXTENDED` set `offer_extended_at=now()`; insert `InterviewJourneyStageHistory`; `await db.flush()`; call `publish_event("journey_stage_changed", ...)`
    - `_encrypt_join_record`: fetch `CandidateInterviewJourney` by `interview_journey_id`; set `candidate_id_encrypted=encrypt_field(str(candidate_id))`, `interview_journey_id_encrypted=encrypt_field(str(journey_id))`, `is_encrypted=True`; `await db.flush()`; log INFO `join_record_encrypted`
    - `get_journey` / `list_journeys`: org-scoped queries filtering `deleted_at IS NULL`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 4.2 Write property test for journey stage FSM enforcement (Property 1)
    - **Property 1: Journey stage FSM — only valid transitions permitted**
    - **Validates: Requirements 1.2, 1.8**
    - Use `@given(from_stage=st.sampled_from(list(JourneyStage)), to_stage=st.sampled_from(list(JourneyStage)))` with `max_examples=100`
    - Valid transition → `current_stage` updated, `InterviewJourneyStageHistory` record created; invalid transition → HTTPException 400, `current_stage` unchanged

  - [ ]* 4.3 Write property test for terminal stages having no sub-status (Property 2)
    - **Property 2: Terminal stages have no sub-status**
    - **Validates: Requirements 1.3**
    - Use `@given(to_stage=st.sampled_from(list(JourneyStage)))` with `max_examples=100`
    - Transition to terminal stage → `current_stage_status` is None; transition to non-terminal stage → `current_stage_status` is None or a valid `JourneyStageStatus` value

  - [ ]* 4.4 Write property test for OfferAccepted encryption (Property 3)
    - **Property 3: OfferAccepted triggers immediate encryption and status completion**
    - **Validates: Requirements 1.7**
    - Use `@given(candidate_id=st.uuids(), journey_id=st.uuids())` with `max_examples=100`
    - After `OFFER_ACCEPTED` transition: `overall_status=COMPLETED`, `CandidateInterviewJourney.is_encrypted=True`, both encrypted columns populated with ciphertext differing from plaintext UUIDs — all within the same transaction

  - [ ]* 4.5 Write property test for JourneyPublicID uniqueness and minimum length (Property 4)
    - **Property 4: JourneyPublicID uniqueness and minimum length**
    - **Validates: Requirements 1.1**
    - Use `@given(n=st.integers(min_value=2, max_value=20))` with `max_examples=100`
    - Create N journeys; all `journey_public_id` values are distinct; each is a URL-safe string of at least 22 characters

  - [x] 4.6 Implement journey router in `app/modules/journeys/router.py`
    - `POST /api/v1/journeys` — `require_role("Recruiter", "Administrator")`; returns 201
    - `GET /api/v1/journeys`, `GET /api/v1/journeys/{journey_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `POST /api/v1/journeys/{journey_id}/transition` — `require_role("Recruiter", "Administrator")`; returns 200
    - `GET /api/v1/journeys/{journey_id}/history` — `require_role("Recruiter", "Administrator", "HiringManager")`; paginated stage history
    - Include full OpenAPI metadata on every route
    - _Requirements: 1.1, 1.2, 1.4, 1.7, 1.8_


- [x] 5. Implement InterviewSlotService and slot router
  - [x] 5.1 Implement `InterviewSlotService` in `app/modules/slots/service.py`
    - `create_slot`: validate `scheduled_start < scheduled_end` and duration 15–480 minutes (422 on failure); if `interviewer_user_id` provided call `_validate_interviewer_assignment` and set `invitation_status=PENDING`; insert `InterviewSlot`; `await db.flush()`; if interviewer assigned call `publish_event("interview_slot_created", ...)`
    - `_validate_interviewer_assignment`: fetch `InterviewerPreference` for `(interviewer_user_id, org_id)`; apply defaults (MaxPerDay=5, MaxPerWeek=20, all types) if no record; check `slot_type in allowed_types` (409 if not); count non-cancelled slots on same day (409 if >= max_per_day); count non-cancelled slots in same ISO week (409 if >= max_per_week)
    - `update_invitation_status`: set `invitation_status` to Accepted or Declined; `await db.flush()`
    - `update_attendance_status`: validate `slot.scheduled_end <= now()` (409 if future); set `attendance_status`; `await db.flush()`
    - `create_or_update_preference`: validate `max_interviews_per_day` 1–20 and `max_interviews_per_week` 1–100 (422); enforce ownership — only `interviewer_user_id == current_user.user_id` or Administrator/SuperAdministrator (403 otherwise); upsert `InterviewerPreference`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

  - [ ]* 5.2 Write property test for slot duration validation (Property 5)
    - **Property 5: Slot duration validation**
    - **Validates: Requirements 2.4**
    - Use `@given(duration_minutes=st.integers(min_value=-60, max_value=600))` with `max_examples=200`
    - Duration < 15, > 480, or <= 0 → HTTPException 422; duration 15–480 with valid start/end → slot created successfully

  - [ ]* 5.3 Write property test for interviewer preference enforcement (Property 6)
    - **Property 6: Interviewer preference enforcement on slot assignment**
    - **Validates: Requirements 2.2, 2.3**
    - Use `@given(day_count=st.integers(min_value=0, max_value=10), week_count=st.integers(min_value=0, max_value=25), slot_type=st.sampled_from(list(SlotType)), allowed_types=st.frozensets(st.sampled_from(list(SlotType)), min_size=0, max_size=4))` with `max_examples=100`
    - Slot type not in allowed_types → 409; day_count >= max_per_day → 409; week_count >= max_per_week → 409; all constraints satisfied → slot created with `InvitationStatus=Pending`

  - [ ]* 5.4 Write property test for default interviewer limits (Property 7)
    - **Property 7: Default interviewer limits applied when no preference exists**
    - **Validates: Requirements 2.10**
    - Use `@given(slot_type=st.sampled_from(list(SlotType)))` with `max_examples=100`
    - No `InterviewerPreference` record for interviewer → system applies MaxPerDay=5, MaxPerWeek=20, all four types allowed; slot creation succeeds for any valid type within limits

  - [ ]* 5.5 Write property test for AttendanceStatus update timing (Property 8)
    - **Property 8: AttendanceStatus update only after ScheduledEnd**
    - **Validates: Requirements 2.7**
    - Use `@given(minutes_offset=st.integers(min_value=-120, max_value=120))` with `max_examples=100`
    - `scheduled_end` in the future → HTTPException 409; `scheduled_end` in the past → update succeeds

  - [x] 5.6 Implement slot router in `app/modules/slots/router.py`
    - `POST /api/v1/slots` — `require_role("Recruiter", "Administrator")`; returns 201
    - `GET /api/v1/slots`, `GET /api/v1/slots/{slot_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `PATCH /api/v1/slots/{slot_id}` — `require_role("Recruiter", "Administrator")`
    - `PATCH /api/v1/slots/{slot_id}/attendance` — `require_role("Recruiter", "Administrator")`
    - `PATCH /api/v1/slots/{slot_id}/invitation` — authenticated interviewer (self-service)
    - `GET /api/v1/interviewer-preferences/{user_id}`, `PUT /api/v1/interviewer-preferences/{user_id}` — ownership or Administrator/SuperAdministrator
    - _Requirements: 2.1, 2.2, 2.5, 2.6, 2.7, 2.9_


- [x] 6. Checkpoint — journey and slot pipeline working
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement InterviewFeedbackService and feedback router
  - [x] 7.1 Implement `InterviewFeedbackService` in `app/modules/feedback/service.py`
    - `create_feedback`: call `_get_slot_and_authorize_write` (403 if not assigned interviewer); call `_validate_feedback_fields` (422 on invalid ratings or narrative > 5000 chars); insert `InterviewFeedback(type=MANUAL, status=DRAFT)`; set `slot.feedback_id`; `await db.flush()`
    - `submit_feedback`: verify `slot.interviewer_user_id == requesting_user_id` (403 if not); verify `feedback.status != SUBMITTED` (409 if already submitted); set `status=SUBMITTED`; `await db.flush()`
    - `submit_transcript`: call `_get_slot_and_authorize_write`; validate `len(transcript) <= 50000` (422); insert `InterviewFeedback(type=AI_GENERATED, status=DRAFT)`; `await db.flush()`; `background_tasks.add_task(_run_behavioral_feedback, feedback_id, transcript, correlation_id_var.get(""))`; return 202
    - `_run_behavioral_feedback`: open new `AsyncSessionFactory` session; POST to `/internal/agents/behavioral-feedback` with `X-Agent-API-Key` and `X-Correlation-ID`; on success populate `competency_ratings`, `narrative`, `hiring_recommendation`; on exception log ERROR `behavioral_feedback_agent_failed` with `feedback_id` and `correlation_id`; always `await db.commit()`
    - `get_feedback`: authorize — assigned interviewer, hiring manager for requisition, or Administrator/SuperAdministrator (403 otherwise)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [ ]* 7.2 Write property test for feedback write authorization (Property 9)
    - **Property 9: Feedback write authorization — assigned interviewer only**
    - **Validates: Requirements 3.6**
    - Use `@given(assigned_interviewer_id=st.uuids(), requesting_user_id=st.uuids())` with `assume(assigned_interviewer_id != requesting_user_id)` and `max_examples=100`
    - Non-assigned user → HTTPException 403; assigned interviewer → feedback created successfully

  - [ ]* 7.3 Write property test for submitted feedback immutability (Property 10)
    - **Property 10: Submitted feedback is immutable**
    - **Validates: Requirements 3.8, 3.9**
    - Use `@given(competency_ratings=st.dictionaries(st.text(min_size=1, max_size=50), st.integers(min_value=1, max_value=5), min_size=1, max_size=5))` with `max_examples=100`
    - After `submit_feedback`: any subsequent edit or submit attempt → HTTPException 409; feedback record unchanged

  - [x] 7.4 Implement feedback router in `app/modules/feedback/router.py`
    - `POST /api/v1/feedback` — `require_role("Interviewer", "Recruiter", "Administrator")`; returns 201
    - `GET /api/v1/feedback/{feedback_id}` — authorized roles (assigned interviewer, hiring manager, administrator)
    - `PATCH /api/v1/feedback/{feedback_id}` — assigned interviewer only; returns 200
    - `PATCH /api/v1/feedback/{feedback_id}/submit` — assigned interviewer only; returns 200
    - `POST /api/v1/feedback/transcript` — assigned interviewer only; returns 202
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_


- [x] 8. Implement QuestionnaireService and questionnaire router
  - [x] 8.1 Implement `QuestionnaireService` in `app/modules/questionnaires/service.py`
    - `create_questionnaire`: call `_validate_questions_yaml` (422 on failure); insert `Questionnaire`; `await db.flush()`
    - `_validate_questions_yaml`: `yaml.safe_load` (422 on parse error); validate list structure; for each question validate `id` (string), `text` (string, max 500), `type` (enum), `required` (bool); validate `options` for choice types; validate `minRating`/`maxRating` for rating type; collect all errors and raise 422 with field list
    - `link_questionnaire_to_requisition`: check `UniqueConstraint` (409 on duplicate); insert `JobRequisitionQuestionnaire`; `await db.flush()`
    - `auto_create_responses`: for each `JobRequisitionQuestionnaire` linked to `job_requisition_id`, check for existing `CandidateQuestionnaireResponse` (skip if exists); insert new response with `status=DRAFT`; `await db.flush()`; return list of created responses
    - `save_answers`: verify `response.status != SUBMITTED` (403 if submitted); load questionnaire YAML; compute `required_ids`; if `is_final_submit` validate all required answered (422 with missing IDs if not), set `status=SUBMITTED`; else set `status=INCOMPLETE` if any required unanswered; upsert `CandidateQuestionnaireAnswer`; `await db.flush()`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10_

  - [ ]* 8.2 Write property test for questionnaire YAML schema validation (Property 11)
    - **Property 11: Questionnaire YAML schema validation**
    - **Validates: Requirements 4.2, 4.3**
    - Use `@given(questions=st.lists(st.fixed_dictionaries({"id": st.text(min_size=1), "text": st.text(max_size=600), "type": st.text(), "required": st.booleans()}), min_size=0, max_size=5))` with `max_examples=100`
    - Missing required fields, text > 500 chars, or invalid type enum → HTTPException 422 with field list; valid schema → questionnaire stored

  - [ ]* 8.3 Write property test for questionnaire response auto-creation idempotency (Property 12)
    - **Property 12: Questionnaire response auto-creation is idempotent**
    - **Validates: Requirements 4.5**
    - Use `@given(n_questionnaires=st.integers(min_value=1, max_value=5), n_calls=st.integers(min_value=1, max_value=3))` with `max_examples=100`
    - Calling `auto_create_responses` N times for the same candidate-requisition pair → exactly `n_questionnaires` `CandidateQuestionnaireResponse` records with `status=DRAFT`; no duplicates

  - [ ]* 8.4 Write property test for submitted questionnaire response immutability (Property 13)
    - **Property 13: Submitted questionnaire response is immutable**
    - **Validates: Requirements 4.9, 4.10, 5.7**
    - Use `@given(answers=st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=100), min_size=1, max_size=5))` with `max_examples=100`
    - After `save_answers(is_final_submit=True)`: any subsequent `save_answers` call → HTTPException 403; response record and answers unchanged

  - [x] 8.5 Implement questionnaire router in `app/modules/questionnaires/router.py`
    - `POST /api/v1/questionnaires` — `require_role("Recruiter", "Administrator")`; returns 201
    - `GET /api/v1/questionnaires`, `GET /api/v1/questionnaires/{questionnaire_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `PATCH /api/v1/questionnaires/{questionnaire_id}` — `require_role("Recruiter", "Administrator")`
    - `POST /api/v1/questionnaires/{questionnaire_id}/link` — `require_role("Recruiter", "Administrator")`; link to requisition
    - `GET /api/v1/questionnaire-responses/{response_id}` — authorized roles
    - `PATCH /api/v1/questionnaire-responses/{response_id}/answers` — candidate or recruiter
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.8, 4.9, 4.10_


- [x] 9. Implement CandidatePortalService and portal router
  - [x] 9.1 Implement `CandidatePortalService` in `app/modules/portal/service.py`
    - `get_or_create_token`: query for existing active non-expired token for `(candidate_id, org_id)`; if found return it; else generate `raw_token = secrets.token_urlsafe(32)` (≥43 URL-safe chars), compute `token_hash = SHA-256(raw_token)`, set `expires_at = now() + timedelta(days=settings.PORTAL_TOKEN_TTL_DAYS)`; insert `CandidatePortalToken(is_active=True)`; `await db.flush()`; return token (raw_token returned once, not stored in plaintext)
    - `validate_token`: compute `token_hash = SHA-256(raw_token)`; query `CandidatePortalToken WHERE token_hash=? AND is_active=True AND expires_at > now() AND deleted_at IS NULL`; if not found raise HTTPException 401 with generic message (no disclosure of reason)
    - `verify_email_and_issue_jwt`: call `validate_token`; fetch `Candidate`; `decrypt_field(candidate.email).lower() == email.lower().strip()` (401 with same generic message if mismatch); sign JWT with claims `{sub, candidate_id, org_id, exp=now()+60min, iat}`; return JWT string
    - Wire `auto_create_responses` to call `get_or_create_token` after creating first `CandidateQuestionnaireResponse` for a candidate
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 9.2 Write property test for portal token minimum entropy and TTL (Property 14)
    - **Property 14: Portal token minimum entropy and TTL**
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - Use `@given(ttl_days=st.integers(min_value=1, max_value=365))` with `max_examples=100`
    - Generated token has ≥43 URL-safe chars (from 32 bytes); `expires_at == creation_time + ttl_days days`; invalid/expired/inactive token → 401 without revealing which condition applies

  - [ ]* 9.3 Write property test for portal email verification non-disclosure (Property 15)
    - **Property 15: Portal email verification non-disclosure**
    - **Validates: Requirements 5.4, 5.5**
    - Use `@given(submitted_email=st.emails(), actual_email=st.emails())` with `assume(submitted_email.lower() != actual_email.lower())` and `max_examples=100`
    - Email mismatch → HTTPException 401 with identical message as invalid token; no disclosure of whether token or email was wrong

  - [x] 9.4 Implement portal router in `app/modules/portal/router.py`
    - `POST /api/v1/portal/auth/verify` — unauthenticated; accepts `{token, email}`; returns JWT on success, 401 on failure
    - `GET /api/v1/portal/questionnaires` — token-only auth or JWT; returns candidate's questionnaire list and statuses
    - `GET /api/v1/portal/questionnaires/{response_id}` — token-only auth or JWT; returns questions and existing answers
    - `PATCH /api/v1/portal/questionnaires/{response_id}/answers` — token-only auth or JWT; save draft or submit
    - `GET /api/v1/portal/availability` — token-only auth or JWT; list candidate availability slots
    - `POST /api/v1/portal/availability` — token-only auth or JWT; create availability slot
    - `GET /api/v1/portal/interviews` — token-only auth or JWT; list upcoming and past interview slots
    - All portal endpoints restricted to authenticated candidate's own data within their organization
    - _Requirements: 5.2, 5.4, 5.6, 5.7, 5.8, 5.9_


- [x] 10. Checkpoint — questionnaire, portal, and feedback pipeline working
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement EmailConfigService and email config router
  - [x] 11.1 Implement `EmailConfigService` in `app/modules/email_config/service.py`
    - `create_or_update_config`: validate provider-specific required fields — `smtp` requires `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`; `sendgrid`/`ses` require `third_party_api_key` (422 with field list on failure); encrypt `smtp_password` and `third_party_api_key` via `encrypt_field` before storing; upsert `OrganizationEmailConfig`; `await db.flush()`
    - `get_config`: org-scoped fetch; return config with encrypted fields masked in response schema
    - `get_global_setting` / `update_global_setting`: fetch/update `SystemSetting WHERE setting_key='email_notifications_enabled'`; validate value is `"true"` or `"false"` (422 otherwise); `await db.flush()`
    - _Requirements: 6.1, 6.2, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 11.2 Write property test for OrganizationEmailConfig validation always runs (Property 17)
    - **Property 17: OrganizationEmailConfig validation always runs**
    - **Validates: Requirements 6.4, 6.8**
    - Use `@given(provider=st.sampled_from(list(ProviderType)), email_enabled=st.booleans(), missing_field=st.sampled_from(["smtp_host", "smtp_port", "smtp_username", "smtp_password", "third_party_api_key"]))` with `max_examples=100`
    - Missing required field for selected provider → HTTPException 422 regardless of `email_notifications_enabled` value; valid config → stored successfully

  - [x] 11.3 Implement email config router in `app/modules/email_config/router.py`
    - `GET /api/v1/email-config` — `require_role("Administrator", "SuperAdministrator")`; org-scoped
    - `POST /api/v1/email-config` — `require_role("Administrator", "SuperAdministrator")`; returns 201
    - `PATCH /api/v1/email-config` — `require_role("Administrator", "SuperAdministrator")`
    - `GET /api/v1/system-settings/email` — `require_role("SuperAdministrator")`
    - `PATCH /api/v1/system-settings/email` — `require_role("SuperAdministrator")`
    - _Requirements: 6.1, 6.2, 6.6, 6.7, 6.8_


- [x] 12. Implement CandidateAvailabilityService and availability router
  - [x] 12.1 Implement `CandidateAvailabilityService` in `app/modules/availability/service.py`
    - `create_availability`: call `_validate_slot(start_time, end_time, now)` — validate `start_time < end_time` (422), duration 30–480 minutes (422), `start_time >= now + 1 hour` (422); call `_check_active_slot_limit` — count active slots for `(candidate_id, org_id)`, raise 409 if >= 50; insert `CandidateAvailabilitySlot(status=ACTIVE)`; `await db.flush()`
    - `cancel_availability`: set `availability_slot.status=CANCELLED`; query `InterviewSlot WHERE status=SCHEDULED AND scheduled_start >= slot.start_time AND scheduled_end <= slot.end_time AND deleted_at IS NULL`; for each overlapping slot set `status=CANCELLED` and log INFO `interview_slot_cascade_cancelled`; `await db.flush()`
    - `list_availability`: org-scoped and candidate-scoped query filtering `deleted_at IS NULL`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 12.2 Write property test for availability slot validation (Property 18)
    - **Property 18: Availability slot validation**
    - **Validates: Requirements 7.2, 7.3**
    - Use `@given(duration_minutes=st.integers(min_value=-60, max_value=600), hours_in_future=st.floats(min_value=-2.0, max_value=5.0))` with `max_examples=200`
    - `start >= end`, duration < 30, duration > 480, or `start_time < now + 1h` → HTTPException 422 with violated rule; valid slot → created with `status=Active`

  - [ ]* 12.3 Write property test for active availability slot limit (Property 19)
    - **Property 19: Active availability slot limit per candidate per org**
    - **Validates: Requirements 7.6**
    - Use `@given(existing_count=st.integers(min_value=48, max_value=52))` with `max_examples=100`
    - Candidate with 50 active slots → 51st creation attempt → HTTPException 409; cancelled slots not counted toward limit

  - [ ]* 12.4 Write property test for availability cancellation cascade (Property 20)
    - **Property 20: Availability cancellation cascades to scheduled interview slots**
    - **Validates: Requirements 7.5**
    - Use `@given(n_overlapping=st.integers(min_value=0, max_value=5), n_non_overlapping=st.integers(min_value=0, max_value=3))` with `max_examples=100`
    - Cancel availability slot → all N overlapping `Scheduled` InterviewSlots set to `Cancelled` in same transaction; non-overlapping slots unaffected

  - [x] 12.5 Implement availability router in `app/modules/availability/router.py`
    - `GET /api/v1/availability` — candidate (portal auth) or `require_role("Recruiter", "Administrator")`
    - `POST /api/v1/availability` — candidate (portal auth); returns 201
    - `PATCH /api/v1/availability/{slot_id}` — candidate (portal auth); cancel slot
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6_


- [x] 13. Implement NotificationService, EmailDeliveryService, and notification router
  - [x] 13.1 Implement `EmailDeliveryService` in `app/modules/notifications/email_delivery.py`
    - `send(to, subject, body)`: if `org_config` provided dispatch to `_send_smtp`, `_send_sendgrid`, or `_send_ses` based on `provider_type`; else fall back to env-var SMTP defaults (`settings.SMTP_HOST`, etc.)
    - `_send_smtp`: build `MIMEMultipart("alternative")`; `smtplib.SMTP(host, port)`; `starttls` if `use_tls`; `login`; `sendmail`
    - `_send_sendgrid`: `httpx.AsyncClient.post` to `https://api.sendgrid.com/v3/mail/send` with Bearer auth
    - `_send_ses`: `boto3.client("ses").send_email`
    - Decrypt `smtp_password` and `third_party_api_key` via `decrypt_field` before use
    - _Requirements: 6.5_

  - [x] 13.2 Implement `NotificationService` in `app/modules/notifications/service.py`
    - `deliver(event_type, payload, org_id, recipient_email, locale)`: call `_is_delivery_enabled(org_id)` — check global `SystemSetting` first (log INFO and return None if "false"); check `OrganizationEmailConfig.email_notifications_enabled` (log INFO and return None if false); call `_resolve_template` (locale-specific then org-default fallback); if template disabled log INFO and return None; render subject and body via `_render`; insert `NotificationRecord(status=PENDING, attempt_count=0)`; `await db.flush()`; call `_attempt_delivery`
    - `_attempt_delivery`: loop attempts 1–5; call `EmailDeliveryService.send`; on success set `status=DELIVERED`, `delivered_at=now()`, `await db.flush()`, return; on exception log WARNING with attempt count; if `attempt < 5` set `status=RETRYING`, `await db.flush()`, `await asyncio.sleep(60 * 2**(attempt-1))`; after 5 failures set `status=PERMANENTLY_FAILED`, `await db.flush()`, log ERROR `notification_permanently_failed`
    - `send_24h_reminder(slot_id, org_id)`: fetch slot; skip if not `SCHEDULED` or `invitation_status` not in {PENDING, ACCEPTED}; skip if `now() < slot.scheduled_start - 24h`; decrypt interviewer email; call `deliver("interview_reminder", ...)`
    - `_render`: replace `{{variable}}` placeholders with payload values via regex
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10_

  - [ ]* 13.3 Write property test for two-level notification switch (Property 16)
    - **Property 16: Two-level notification switch — global takes precedence**
    - **Validates: Requirements 6.3, 6.4**
    - Use `@given(global_enabled=st.booleans(), org_enabled=st.booleans())` with `max_examples=100`
    - Global switch "false" → delivery skipped, INFO logged, result is None regardless of org setting; global "true" + org false → delivery skipped for that org only; both true → delivery attempted

  - [ ]* 13.4 Write property test for notification retry with exponential backoff (Property 21)
    - **Property 21: Notification retry with exponential backoff and permanent failure**
    - **Validates: Requirements 8.9, 8.10**
    - Use `@given(fail_on_attempt=st.integers(min_value=1, max_value=6))` with `max_examples=100`; mock `EmailDeliveryService.send` and `asyncio.sleep`
    - Delivery fails on all 5 attempts → `NotificationRecord.status=PermanentlyFailed`, ERROR logged; delivery succeeds on attempt N ≤ 5 → `status=Delivered`; backoff delays follow `60 * 2^(attempt-1)` seconds

  - [ ]* 13.5 Write property test for 24-hour reminder window (Property 22)
    - **Property 22: 24-hour reminder fires only within the correct window**
    - **Validates: Requirements 8.5**
    - Use `@given(hours_until_start=st.floats(min_value=-2.0, max_value=30.0))` with `max_examples=100`
    - `hours_until_start > 24` → no reminder sent; `0 <= hours_until_start <= 24` with `status=SCHEDULED` and valid `invitation_status` → reminder sent; slot not Scheduled or invitation not Pending/Accepted → no reminder

  - [x] 13.6 Implement notification router in `app/modules/notifications/router.py`
    - `POST /internal/agents/notification` — internal endpoint authenticated via `X-Agent-API-Key`; accepts notification delivery request
    - `GET /api/v1/notification-templates` — `require_role("Administrator", "SuperAdministrator")`; org-scoped
    - `POST /api/v1/notification-templates` — `require_role("Administrator", "SuperAdministrator")`; returns 201
    - `PATCH /api/v1/notification-templates/{template_id}` — `require_role("Administrator", "SuperAdministrator")`
    - `GET /api/v1/notification-records` — `require_role("Administrator", "SuperAdministrator")`; paginated
    - _Requirements: 8.7, 8.8, 8.9, 8.10_


- [~] 14. Implement CandidateFeedbackSurveyService and survey router
  - [~] 14.1 Implement `CandidateFeedbackSurveyService` in `app/modules/surveys/service.py`
    - `create_survey_for_journey`: check if survey already exists for `(journey_id)` (skip if yes); generate `raw_token = secrets.token_urlsafe(32)` (≥43 URL-safe chars), compute `token_hash = SHA-256(raw_token)`, set `expires_at = now() + 30 days`; insert `CandidateFeedbackSurvey(status=DRAFT, expires_at=...)`; insert `CandidateFeedbackSurveyToken(token_hash, is_active=True, expires_at=...)`; update survey `status=SENT`, `survey_token_id=token_id`; `await db.flush()`; publish event `survey_created` with candidate email
    - `get_survey_by_token`: compute `token_hash = SHA-256(token)`; query `CandidateFeedbackSurveyToken WHERE token_hash=? AND is_active=True AND expires_at > now()` (401 if not found); fetch survey; if `status=EXPIRED` or `status=COMPLETED` return 410; else fetch `CandidateFeedbackSurveyQuestion` for org
    - `submit_survey`: call `get_survey_by_token`; validate `rating` values 0–10 (422); validate `additional_comments` max 2000 chars (422); start transaction; insert `CandidateFeedbackSurveyResponse`; for each question insert `CandidateFeedbackSurveyAnswer` with rating and answer_id; update survey `status=COMPLETED, completed_at=now()`; set `token.is_active=False`; `await db.commit()`
    - `send_reminder`: query surveys `WHERE status=SENT AND created_at <= now()-7d AND first_reminder_sent_at IS NULL`; update `first_reminder_sent_at=now()`; publish event `survey_reminder` with candidate email
    - `expire_surveys`: query surveys `WHERE status=SENT AND expires_at <= now()`; update `status=EXPIRED`; deactivate tokens `WHERE expires_at <= now()` and `is_active=True`
    - `get_survey_questions`: org-scoped query for questions, ordered by `display_order`
    - _Requirements: 9.1, 9.2, 9.3, 9.6, 9.7, 9.8, 9.9, 9.14, 9.15, 9.16_

  - [ ]* 14.2 Write property test for survey creation and token entropy (Property 23)
    - **Property 23: Candidate feedback survey creation and token generation**
    - **Validates: Requirements 9.1, 9.2, 9.7, 9.8**
    - Use `@given(n_transitions=st.integers(min_value=1, max_value=3))` with `max_examples=100`
    - Transition OUT OF LoopInterview → survey created, token generated with ≥43 URL-safe chars, `expires_at == creation_time + 30 days`; second transition for same journey → no duplicate survey; first transition should have `status=SENT` after token creation

  - [ ]* 14.3 Write property test for survey token validation and expiry (Property 24)
    - **Property 24: Survey token validation and expiry enforcement**
    - **Validates: Requirements 9.11, 9.12, 9.13**
    - Use `@given(token_valid=st.booleans(), survey_expired=st.booleans(), survey_completed=st.booleans(), minutes_offset=st.integers(min_value=-60, max_value=1800))` with `max_examples=100`
    - Valid token + non-expired + not-completed survey → 200 with form; invalid token → 410; expired survey → 410; completed survey → 410; all 410 responses must have identical message (no disclosure)

  - [ ]* 14.4 Write property test for survey submission atomicity and resubmission prevention (Property 25)
    - **Property 25: Survey submission atomicity and resubmission prevention**
    - **Validates: Requirements 9.14, 9.15**
    - Use `@given(n_questions=st.integers(min_value=1, max_value=10), ratings=st.lists(st.integers(min_value=0, max_value=10), min_size=1, max_size=10), n_submissions=st.integers(min_value=1, max_value=3))` with `max_examples=100`
    - First submission with valid ratings → one Response + N Answers created atomically, survey `status=COMPLETED`, token `is_active=False`; second submission on same token → 409 with exact message; third submission → 409 again

  - [ ]* 14.5 Write property test for seven-day reminder and thirty-day expiry (Property 26)
    - **Property 26: Seven-day reminder window and silent 30-day expiry**
    - **Validates: Requirements 9.7, 9.10, 9.11**
    - Use `@given(hours_since_creation=st.floats(min_value=0.0, max_value=744.0))` with `max_examples=100`; mock scheduler time
    - Survey created at T; at T+7d-1h no reminder sent; at T+7d to T+7d+1h exactly one reminder sent (call `send_reminder`); at T+30d survey and token `status=EXPIRED`, no notification sent; reaccess after expiry → 410 silent

  - [ ]* 14.6 Write property test for survey response plain-text storage (Property 27)
    - **Property 27: Survey response plain-text storage for analytics**
    - **Validates: Requirements 9.16**
    - Use `@given(ratings=st.lists(st.integers(min_value=0, max_value=10), min_size=1, max_size=10), comments=st.text(max_size=2000))` with `max_examples=100`
    - Submit survey with various ratings and comments → fetch from DB via plain SQL without decryption → all values readable, aggregatable by category and time period

  - [ ]* 14.7 Write property test for survey-specific notification templates (Property 28)
    - **Property 28: Survey-specific notification template independence**
    - **Validates: Requirements 9.17, 9.18**
    - Use `@given(survey_template_enabled=st.booleans(), general_template_enabled=st.booleans())` with `max_examples=100`
    - Create both survey template and general template; trigger survey event → uses survey template if exists; general template updates must not affect survey templates and vice versa

  - [~] 14.8 Implement survey router in `app/modules/surveys/router.py`
    - `GET /api/v1/surveys/{token}` — unauthenticated; returns 200 with survey form and questions or 410 if invalid/expired/completed
    - `POST /api/v1/surveys/{token}/submit` — unauthenticated; accepts `{answers: {question_id: rating, ...}, additional_comments: string}`; returns 200 on success, 409 if already completed, 410 if expired
    - Survey form endpoints require no additional authentication beyond token validation
    - _Requirements: 9.9, 9.12, 9.13, 9.14, 9.15_


- [~] 15. Wire survey creation event to journey stage transitions
  - [~] 15.1 Update `InterviewJourneyService.transition_stage` in `app/modules/journeys/service.py`
    - When `to_stage` is any stage after LoopInterview (PanelReview, OfferPending, OfferExtended, OfferAccepted, OfferDeclined, Rejected, Withdrawn), call `background_tasks.add_task(_create_survey_on_loop_exit, journey.interview_journey_id, journey.candidate_id, journey.organization_id)`
    - `_create_survey_on_loop_exit`: open new session; call `SurveyService.create_survey_for_journey`; on success publish event `survey_created`; on exception log ERROR with correlation_id
    - _Requirements: 9.7_

  - [~] 15.2 Connect survey domain events to notification delivery
    - In `app/domain_events/handlers.py`, register handlers for: `survey_created` → call `NotificationService.deliver("survey_invitation", {survey_link, candidate_email}, org_id)` (Requirement 9.9); `survey_reminder` → call `NotificationService.deliver("survey_reminder", {survey_link, candidate_email}, org_id)` (Requirement 9.10)
    - Both handlers should use `SurveyFeedbackTemplate` for rendering (Requirement 9.17, 9.18)
    - _Requirements: 9.9, 9.10, 9.17, 9.18_

  - [~] 15.3 Implement survey reminder and expiry background scheduler in `app/modules/surveys/scheduler.py`
    - Create `run_survey_scheduler()` async function
    - Call `SurveyService.send_reminder()` — selects surveys 7+ days old with no reminder sent
    - Call `SurveyService.expire_surveys()` — selects surveys 30+ days old with status Sent, sets to Expired
    - Register scheduler to run periodically (e.g., every 15 minutes or configurable via env var `SURVEY_SCHEDULER_INTERVAL_MINUTES`)
    - Log all scheduler actions at INFO level
    - _Requirements: 9.10, 9.11, 9.26_


- [~] 16. Implement survey template management
  - [~] 16.1 Create survey template models and migration
    - Add `SurveyFeedbackTemplate(Base, AuditMixin, VersionMixin)` to `app/modules/surveys/models.py` with fields: `survey_feedback_template_id`, `organization_id`, `template_type` (initial_survey_invitation, survey_reminder), `subject` (max 200), `body_template` (text with `{{variable}}` placeholders), `is_enabled` (bool)
    - Add `UniqueConstraint("organization_id", "template_type")` to prevent duplicate templates per org
    - Add migration to create table with check constraint on template_type enum
    - _Requirements: 9.17, 9.18_

  - [~] 16.2 Implement survey template service and router
    - `CandidateFeedbackSurveyTemplateService` in `app/modules/surveys/service.py`: `create_template`, `update_template`, `get_template`, `delete_template` — all org-scoped, require Administrator or SuperAdministrator role
    - Router endpoints: `GET /api/v1/survey-templates`, `POST /api/v1/survey-templates`, `PATCH /api/v1/survey-templates/{template_id}` — all require Administrator or SuperAdministrator
    - _Requirements: 9.17, 9.18_


- [~] 17. Wire domain events to survey notification delivery
  - [~] 14.1 Connect domain event handlers to `NotificationService.deliver`
    - In `app/domain_events/handlers.py` (or equivalent), register handlers for: `journey_stage_changed` → notify candidate, recruiter, and hiring manager (Requirement 8.2); `candidate_questionnaire_response_created` → notify candidate with portal URL (Requirement 8.3); `interview_slot_created` → notify assigned interviewer (Requirement 8.4); `offer_accepted` → notify all interviewers on the journey (Requirement 8.6)
    - Each handler calls `NotificationService.deliver` with the appropriate `event_type`, `payload`, `org_id`, and `recipient_email`
    - Ensure `publish_event()` persist-first pattern is maintained: domain event row inserted before `BackgroundTasks.add_task` dispatches the handler
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.6_

  - [~] 14.2 Implement 24-hour reminder background scheduler
    - Create `app/modules/notifications/scheduler.py` with `run_reminder_check()` async function
    - Query `InterviewSlot WHERE status=SCHEDULED AND invitation_status IN ('Pending', 'Accepted') AND scheduled_start BETWEEN now() AND now()+24h AND deleted_at IS NULL`
    - For each slot call `NotificationService.send_24h_reminder(slot_id, org_id)`
    - Register scheduler to run periodically (e.g., every 15 minutes via APScheduler or equivalent)
    - _Requirements: 8.5_


- [~] 15. Register all routers and wire module into FastAPI application
  - [~] 15.1 Register all interview-workflow routers in `app/main.py` or the module registry
    - Include routers for: `journeys`, `slots`, `feedback`, `questionnaires`, `portal`, `email_config`, `availability`, `notifications`
    - Verify all route prefixes, tags, and OpenAPI metadata are consistent with the API design
    - Ensure `require_role()` dependencies are applied on every protected endpoint
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.7_

  - [~] 15.2 Add smoke test assertions for module integrity
    - Assert all required enum values present: `JourneyStage`, `JourneyOverallStatus`, `SlotType`, `SlotStatus`, `FeedbackType`, `FeedbackStatus`, `ResponseStatus`, `NotificationStatus`, `ProviderType`
    - Assert `system_settings` table contains `email_notifications_enabled = 'true'` seed row after migration
    - Assert `PORTAL_TOKEN_TTL_DAYS` and `AGENT_API_KEY` env vars are set and parseable
    - Assert all 8 mutable entities with `VersionMixin` have `version_id_col` configured: `InterviewJourney`, `InterviewSlot`, `InterviewFeedback`, `InterviewerPreference`, `Questionnaire`, `CandidateQuestionnaireResponse`, `OrganizationEmailConfig`, `NotificationTemplate`
    - _Requirements: 1.1, 5.1, 6.1, 8.7_

- [~] 16. Final checkpoint — all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical module boundaries
- Property tests validate universal correctness properties using Hypothesis with `max_examples=100`
- Unit tests validate specific examples, edge cases, and error conditions
- Tag each property test: `# Feature: interview-workflow, Property N: <property_text>`
- All PII fields use `encrypt_field`/`decrypt_field` (AES-256-GCM); never log or return plaintext secrets
- All service methods use `await db.flush()` (not `commit()`) — the router layer owns the transaction boundary
- Domain events follow persist-first pattern: event row inserted before background task dispatched


## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "2.2"] },
    { "id": 1, "tasks": ["2.3", "3.1", "3.2"] },
    { "id": 2, "tasks": ["4.1", "5.1", "7.1", "8.1", "9.1", "11.1", "12.1", "13.1", "13.2"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "4.5", "5.2", "5.3", "5.4", "5.5", "7.2", "7.3", "8.2", "8.3", "8.4", "9.2", "9.3", "11.2", "12.2", "12.3", "12.4", "13.3", "13.4", "13.5"] },
    { "id": 4, "tasks": ["4.6", "5.6", "7.4", "8.5", "9.4", "11.3", "12.5", "13.6"] },
    { "id": 5, "tasks": ["14.1", "14.2"] },
    { "id": 6, "tasks": ["15.1", "15.2"] }
  ]
}
```


- [ ] 14. Implement CandidateFeedbackSurveyService and survey router
  - [ ] 14.1 Implement `CandidateFeedbackSurveyService` in `app/modules/surveys/service.py`
    - `create_survey_for_journey`: check if survey already exists for `(journey_id)` (skip if yes); generate `raw_token = secrets.token_urlsafe(32)` (≥43 URL-safe chars), compute `token_hash = SHA-256(raw_token)`, set `expires_at = now() + 30 days`; insert `CandidateFeedbackSurvey(status=DRAFT, expires_at=...)`; insert `CandidateFeedbackSurveyToken(token_hash, is_active=True, expires_at=...)`; update survey `status=SENT`, `survey_token_id=token_id`; `await db.flush()`; publish event `survey_created` with candidate email
    - `get_survey_by_token`: compute `token_hash = SHA-256(token)`; query `CandidateFeedbackSurveyToken WHERE token_hash=? AND is_active=True AND expires_at > now()` (401 if not found); fetch survey; if `status=EXPIRED` or `status=COMPLETED` return 410; else fetch `CandidateFeedbackSurveyQuestion` for org
    - `submit_survey`: call `get_survey_by_token`; validate `rating` values 0–10 (422); validate `additional_comments` max 2000 chars (422); start transaction; insert `CandidateFeedbackSurveyResponse`; for each question insert `CandidateFeedbackSurveyAnswer` with rating and answer_id; update survey `status=COMPLETED, completed_at=now()`; set `token.is_active=False`; `await db.commit()`
    - `send_reminder`: query surveys `WHERE status=SENT AND created_at <= now()-7d AND first_reminder_sent_at IS NULL`; update `first_reminder_sent_at=now()`; publish event `survey_reminder` with candidate email
    - `expire_surveys`: query surveys `WHERE status=SENT AND expires_at <= now()`; update `status=EXPIRED`; deactivate tokens `WHERE expires_at <= now()` and `is_active=True`
    - `get_survey_questions`: org-scoped query for questions, ordered by `display_order`
    - _Requirements: 9.1, 9.2, 9.3, 9.6, 9.7, 9.8, 9.9, 9.14, 9.15, 9.16_

  - [ ]* 14.2 Write property test for survey creation and token entropy (Property 23)
    - **Property 23: Candidate feedback survey creation and token generation**
    - **Validates: Requirements 9.1, 9.2, 9.7, 9.8**
    - Use `@given(n_transitions=st.integers(min_value=1, max_value=3))` with `max_examples=100`
    - Transition OUT OF LoopInterview → survey created, token generated with ≥43 URL-safe chars, `expires_at == creation_time + 30 days`; second transition for same journey → no duplicate survey; first transition should have `status=SENT` after token creation

  - [ ]* 14.3 Write property test for survey token validation and expiry (Property 24)
    - **Property 24: Survey token validation and expiry enforcement**
    - **Validates: Requirements 9.11, 9.12, 9.13**
    - Use `@given(token_valid=st.booleans(), survey_expired=st.booleans(), survey_completed=st.booleans(), minutes_offset=st.integers(min_value=-60, max_value=1800))` with `max_examples=100`
    - Valid token + non-expired + not-completed survey → 200 with form; invalid token → 410; expired survey → 410; completed survey → 410; all 410 responses must have identical message (no disclosure)

  - [ ]* 14.4 Write property test for survey submission atomicity and resubmission prevention (Property 25)
    - **Property 25: Survey submission atomicity and resubmission prevention**
    - **Validates: Requirements 9.14, 9.15**
    - Use `@given(n_questions=st.integers(min_value=1, max_value=10), ratings=st.lists(st.integers(min_value=0, max_value=10), min_size=1, max_size=10), n_submissions=st.integers(min_value=1, max_value=3))` with `max_examples=100`
    - First submission with valid ratings → one Response + N Answers created atomically, survey `status=COMPLETED`, token `is_active=False`; second submission on same token → 409 with exact message; third submission → 409 again

  - [ ]* 14.5 Write property test for seven-day reminder and thirty-day expiry (Property 26)
    - **Property 26: Seven-day reminder window and silent 30-day expiry**
    - **Validates: Requirements 9.7, 9.10, 9.11**
    - Use `@given(hours_since_creation=st.floats(min_value=0.0, max_value=744.0))` with `max_examples=100`; mock scheduler time
    - Survey created at T; at T+7d-1h no reminder sent; at T+7d to T+7d+1h exactly one reminder sent (call `send_reminder`); at T+30d survey and token `status=EXPIRED`, no notification sent; reaccess after expiry → 410 silent

  - [ ]* 14.6 Write property test for survey response plain-text storage (Property 27)
    - **Property 27: Survey response plain-text storage for analytics**
    - **Validates: Requirements 9.16**
    - Use `@given(ratings=st.lists(st.integers(min_value=0, max_value=10), min_size=1, max_size=10), comments=st.text(max_size=2000))` with `max_examples=100`
    - Submit survey with various ratings and comments → fetch from DB via plain SQL without decryption → all values readable, aggregatable by category and time period

  - [ ]* 14.7 Write property test for survey-specific notification templates (Property 28)
    - **Property 28: Survey-specific notification template independence**
    - **Validates: Requirements 9.17, 9.18**
    - Use `@given(survey_template_enabled=st.booleans(), general_template_enabled=st.booleans())` with `max_examples=100`
    - Create both survey template and general template; trigger survey event → uses survey template if exists; general template updates must not affect survey templates and vice versa

  - [ ] 14.8 Implement survey router in `app/modules/surveys/router.py`
    - `GET /api/v1/surveys/{token}` — unauthenticated; returns 200 with survey form and questions or 410 if invalid/expired/completed
    - `POST /api/v1/surveys/{token}/submit` — unauthenticated; accepts `{answers: {question_id: rating, ...}, additional_comments: string}`; returns 200 on success, 409 if already completed, 410 if expired
    - Survey form endpoints require no additional authentication beyond token validation
    - _Requirements: 9.9, 9.12, 9.13, 9.14, 9.15_


- [ ] 15. Wire survey creation event to journey stage transitions
  - [ ] 15.1 Update `InterviewJourneyService.transition_stage` in `app/modules/journeys/service.py`
    - When `to_stage` is any stage after LoopInterview (PanelReview, OfferPending, OfferExtended, OfferAccepted, OfferDeclined, Rejected, Withdrawn), call `background_tasks.add_task(_create_survey_on_loop_exit, journey.interview_journey_id, journey.candidate_id, journey.organization_id)`
    - `_create_survey_on_loop_exit`: open new session; call `SurveyService.create_survey_for_journey`; on success publish event `survey_created`; on exception log ERROR with correlation_id
    - _Requirements: 9.7_

  - [ ] 15.2 Connect survey domain events to notification delivery
    - In `app/domain_events/handlers.py`, register handlers for: `survey_created` → call `NotificationService.deliver("survey_invitation", {survey_link, candidate_email}, org_id)` (Requirement 9.9); `survey_reminder` → call `NotificationService.deliver("survey_reminder", {survey_link, candidate_email}, org_id)` (Requirement 9.10)
    - Both handlers should use `SurveyFeedbackTemplate` for rendering (Requirement 9.17, 9.18)
    - _Requirements: 9.9, 9.10, 9.17, 9.18_

  - [ ] 15.3 Implement survey reminder and expiry background scheduler in `app/modules/surveys/scheduler.py`
    - Create `run_survey_scheduler()` async function
    - Call `SurveyService.send_reminder()` — selects surveys 7+ days old with no reminder sent
    - Call `SurveyService.expire_surveys()` — selects surveys 30+ days old with status Sent, sets to Expired
    - Register scheduler to run periodically (e.g., every 15 minutes or configurable via env var `SURVEY_SCHEDULER_INTERVAL_MINUTES`)
    - Log all scheduler actions at INFO level
    - _Requirements: 9.10, 9.11, 9.26_


- [ ] 16. Implement survey template management
  - [ ] 16.1 Create survey template models and migration
    - Add `SurveyFeedbackTemplate(Base, AuditMixin, VersionMixin)` to `app/modules/surveys/models.py` with fields: `survey_feedback_template_id`, `organization_id`, `template_type` (initial_survey_invitation, survey_reminder), `subject` (max 200), `body_template` (text with `{{variable}}` placeholders), `is_enabled` (bool)
    - Add `UniqueConstraint("organization_id", "template_type")` to prevent duplicate templates per org
    - Add migration to create table with check constraint on template_type enum
    - _Requirements: 9.17, 9.18_

  - [ ] 16.2 Implement survey template service and router
    - `CandidateFeedbackSurveyTemplateService` in `app/modules/surveys/service.py`: `create_template`, `update_template`, `get_template`, `delete_template` — all org-scoped, require Administrator or SuperAdministrator role
    - Router endpoints: `GET /api/v1/survey-templates`, `POST /api/v1/survey-templates`, `PATCH /api/v1/survey-templates/{template_id}` — all require Administrator or SuperAdministrator
    - _Requirements: 9.17, 9.18_


- [ ] 17. Wire domain events to survey notification delivery
  - [~] 17.1 Connect domain event handlers to `NotificationService.deliver`
    - In `app/domain_events/handlers.py` (or equivalent), register handlers for: `journey_stage_changed` → notify candidate, recruiter, and hiring manager (Requirement 8.2); `candidate_questionnaire_response_created` → notify candidate with portal URL (Requirement 8.3); `interview_slot_created` → notify assigned interviewer (Requirement 8.4); `offer_accepted` → notify all interviewers on the journey (Requirement 8.6); `survey_created` → notify candidate with survey link (Requirement 9.9); `survey_reminder` → notify candidate with reminder link (Requirement 9.10)
    - Each handler calls `NotificationService.deliver` with the appropriate `event_type`, `payload`, `org_id`, and `recipient_email`
    - Survey event handlers use `SurveyFeedbackTemplate` if exists, else fall back to `NotificationTemplate` (Requirement 9.17)
    - Ensure `publish_event()` persist-first pattern is maintained: domain event row inserted before `BackgroundTasks.add_task` dispatches the handler
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.6, 9.9, 9.10, 9.17, 9.18_

  - [~] 17.2 Implement 24-hour reminder background scheduler
    - Create `app/modules/notifications/scheduler.py` with `run_reminder_check()` async function
    - Query `InterviewSlot WHERE status=SCHEDULED AND invitation_status IN ('Pending', 'Accepted') AND scheduled_start BETWEEN now() AND now()+24h AND deleted_at IS NULL`
    - For each slot call `NotificationService.send_24h_reminder(slot_id, org_id)`
    - Register scheduler to run periodically (e.g., every 15 minutes via APScheduler or equivalent)
    - _Requirements: 8.5_


- [ ] 18. Register all routers and wire module into FastAPI application
  - [~] 18.1 Register all interview-workflow routers in `app/main.py` or the module registry
    - Include routers for: `journeys`, `slots`, `feedback`, `questionnaires`, `portal`, `email_config`, `availability`, `surveys`, `notifications`
    - Verify all route prefixes, tags, and OpenAPI metadata are consistent with the API design
    - Ensure `require_role()` dependencies are applied on every protected endpoint
    - Survey endpoints are unauthenticated (token-based only)
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.7, 9.1_

  - [~] 18.2 Add smoke test assertions for module integrity
    - Assert all required enum values present: `JourneyStage`, `JourneyOverallStatus`, `SlotType`, `SlotStatus`, `FeedbackType`, `FeedbackStatus`, `ResponseStatus`, `NotificationStatus`, `ProviderType`, `SurveyStatus`, `SurveyQuestionCategory`, `SurveyTemplateType`
    - Assert `system_settings` table contains `email_notifications_enabled = 'true'` seed row after migration
    - Assert `PORTAL_TOKEN_TTL_DAYS`, `SURVEY_SCHEDULER_INTERVAL_MINUTES`, and `AGENT_API_KEY` env vars are set and parseable
    - Assert all 9 mutable entities with `VersionMixin` have `version_id_col` configured: `InterviewJourney`, `InterviewSlot`, `InterviewFeedback`, `InterviewerPreference`, `Questionnaire`, `CandidateQuestionnaireResponse`, `OrganizationEmailConfig`, `NotificationTemplate`, `SurveyFeedbackTemplate`
    - Assert survey scheduler is running or can be invoked manually via admin endpoint
    - _Requirements: 1.1, 5.1, 6.1, 8.7, 9.1_

- [~] 19. Final checkpoint — all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical module boundaries
- Property tests validate universal correctness properties using Hypothesis with `max_examples=100`
- Unit tests validate specific examples, edge cases, and error conditions
- Tag each property test: `# Feature: interview-workflow, Property N: <property_text>`
- All PII fields use `encrypt_field`/`decrypt_field` (AES-256-GCM); never log or return plaintext secrets
- All service methods use `await db.flush()` (not `commit()`) — the router layer owns the transaction boundary
- Domain events follow persist-first pattern: event row inserted before background task dispatched
- Survey data (responses, answers, comments) stored in plain text for analytics aggregation


## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "2.2"] },
    { "id": 1, "tasks": ["2.3", "3.1", "3.2"] },
    { "id": 2, "tasks": ["4.1", "5.1", "7.1", "8.1", "9.1", "11.1", "12.1", "13.1", "13.2", "14.1", "16.1"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "4.5", "5.2", "5.3", "5.4", "5.5", "7.2", "7.3", "8.2", "8.3", "8.4", "9.2", "9.3", "11.2", "12.2", "12.3", "12.4", "13.3", "13.4", "13.5", "14.2", "14.3", "14.4", "14.5", "14.6", "14.7"] },
    { "id": 4, "tasks": ["4.6", "5.6", "7.4", "8.5", "9.4", "11.3", "12.5", "13.6", "14.8", "16.2"] },
    { "id": 5, "tasks": ["15.1", "15.2", "15.3", "17.1", "17.2"] },
    { "id": 6, "tasks": ["18.1", "18.2"] }
  ]
}
```
