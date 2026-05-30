# Implementation Plan: Candidate Lifecycle

## Overview

Implement the core recruiting data layer for TalentKru.ai using FastAPI, async SQLAlchemy, Alembic, and Python. The module covers candidate profile management with GlobalStatus FSM, resume upload and AI-driven ingestion via background tasks, skills taxonomy with case-insensitive matching, job profiles and postings with salary overlap filtering, job requisitions with status FSM and candidate association, a candidate self-service DSAR portal, and full GDPR compliance with Access/Erasure workflows and configurable retention purge. All 19 correctness properties are verified using Hypothesis property-based tests.

All code follows the conventions established in the Platform Foundation and Identity and Access modules: async SQLAlchemy sessions, soft delete, AES-256-GCM PII encryption, structlog structured logging, domain events via `publish_event()`, and `require_role()` / `require_privilege()` dependency factories.

## Correctness Properties Summary

This implementation verifies 19 correctness properties:
1. Candidate email uniqueness within organization
2. GlobalStatus FSM — only valid transitions permitted
3. Ineligible status requires IneligibilityReason
4. Logical delete excludes candidate from search
5. Resume file format and size validation
6. ParseStatus transitions correctly on ingestion outcome
7. Ingestion upserts all associated records on success
8. Skill matching is case-insensitive
9. Unmatched or zero skills do not block ingestion
10. JobPosting requires a valid JobProfile
11. Salary range overlap filter correctness
12. Candidate-requisition association validation
13. Requisition status FSM — transitions only on update
14. DSAR Access workflow only triggered for RequestType=Access
15. DSAR Erasure hard-deletes personal data and anonymizes audit trail
16. Retention policy purge respects configured retention days
17. Candidate expiry scheduler only affects qualifying Active candidates
18. Role-based access enforcement
19. DSAR denial requires minimum-length reason

---

## Tasks

- [x] 1. Set up module structure and Pydantic schemas
  - Create directory tree: `app/modules/{candidates,resumes,skills,job_profile,job_posting,requisitions,portal,privacy}/` with `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py` stubs
  - Add `hypothesis`, `pytest-asyncio`, `httpx`, `boto3` to `pyproject.toml` test/runtime dependencies if not already present
  - Create `app/modules/resumes/storage.py` stub with `StorageService` ABC, `LocalStorageBackend`, `S3StorageBackend`, and `get_storage_service()` factory
  - _Requirements: 1.1, 2.1, 2.4, 3.1, 4.1, 5.1, 6.1_


- [x] 2. Implement data models and Alembic migration
  - [x] 2.1 Create `Candidate` model in `app/modules/candidates/models.py`
    - Define `GlobalStatus(str, enum.Enum)` with ACTIVE, INTERVIEWING, EXPIRED, INELIGIBLE, DELETED values
    - Define `Candidate(Base, AuditMixin, VersionMixin)` with all columns: `candidate_id`, `organization_id`, `name` (VARCHAR 512, encrypted), `name_hash` (VARCHAR 64), `email` (VARCHAR 512, encrypted), `email_hash` (VARCHAR 64), `phone` (VARCHAR 200, encrypted, nullable), `location` (VARCHAR 200, nullable), `global_status` (SQLEnum), `ineligibility_reason` (VARCHAR 1000, nullable)
    - Add `UniqueConstraint("organization_id", "email_hash", name="uq_candidates_org_email")`
    - Add partial indexes: `idx_candidates_org_status` on `(organization_id, global_status) WHERE deleted_at IS NULL` and `idx_candidates_name_hash` on `(organization_id, name_hash) WHERE deleted_at IS NULL`
    - _Requirements: 1.1_

  - [x] 2.2 Create `Resume` and `CandidateJobHistory` models in `app/modules/resumes/models.py`
    - Define `ParseStatus(str, enum.Enum)` with PENDING, COMPLETED, FAILED values
    - Define `Resume(Base, AuditMixin)` with all columns from the design DDL; add `parsed_data` (JSONB, nullable)
    - Define `CandidateJobHistory(Base, AuditMixin)` with all columns from the design DDL
    - Add partial index `idx_resumes_candidate` on `(candidate_id) WHERE deleted_at IS NULL`
    - _Requirements: 2.1, 2.7_

  - [x] 2.3 Create skills taxonomy models in `app/modules/skills/models.py`
    - Define `SkillSource(str, enum.Enum)` with MANUAL, PARSED, INFERRED values
    - Define `Domain(Base, AuditMixin)`, `Skill(Base, AuditMixin)` with `UniqueConstraint("domain_id", "name")`
    - Define `CandidateSkill(Base, AuditMixin)` with `proficiency_rank` CHECK (1–5), `years_of_experience` CHECK (0–50), `UniqueConstraint("candidate_id", "skill_id")`
    - Define `RequisitionRequiredSkill(Base, AuditMixin)` with `required_proficiency_rank` CHECK (1–5), `weight` CHECK (1–10), `UniqueConstraint("job_requisition_id", "skill_id")`
    - Define `UnmatchedSkillReview(Base, AuditMixin)` with `unmatched_skill_name` (VARCHAR 200), `resolved` (Boolean, default False)
    - _Requirements: 3.1, 3.2, 3.3_


  - [x] 2.4 Create job profile and job posting models
    - Define `SkillDesignation(str, enum.Enum)` with REQUIRED, DESIRED values
    - Define `JobProfile(Base, AuditMixin, VersionMixin)` in `app/modules/job_profile/models.py` with `job_profile_id`, `organization_id`, `name` (VARCHAR 200)
    - Define `JobProfileSkill(Base, AuditMixin)` with `designation` (SQLEnum), `required_proficiency_rank` CHECK (1–5), `UniqueConstraint("job_profile_id", "skill_id")`
    - Define `JobPosting(Base, AuditMixin, VersionMixin)` in `app/modules/job_posting/models.py` with `work_locations` (ARRAY(String)), `salary_min`/`salary_max` (Numeric 12,2), `salary_currency` (VARCHAR 3), `sourcing_channel` (VARCHAR 100)
    - Add partial index `idx_job_postings_salary` on `(organization_id, salary_min, salary_max) WHERE deleted_at IS NULL`
    - _Requirements: 4.1, 4.2_

  - [x] 2.5 Create requisition and privacy models
    - Define `RequisitionStatus(str, enum.Enum)` with OPEN, ON_HOLD, CLOSED, CANCELLED values
    - Define `JobRequisition(Base, AuditMixin, VersionMixin)` and `CandidateRequisition(Base, AuditMixin)` in `app/modules/requisitions/models.py` with `UniqueConstraint("candidate_id", "job_requisition_id")`
    - Define `DSARRequestType(str, enum.Enum)` and `DSARStatus(str, enum.Enum)` in `app/modules/privacy/models.py`
    - Define `DataSubjectAccessRequest(Base, AuditMixin)` with `requested_at` (server_default=func.now()), `completed_at` (nullable), `denial_reason` (VARCHAR 1000, nullable)
    - Define `OrganizationRetentionPolicy(Base, AuditMixin)` with `UniqueConstraint("organization_id")` and integer defaults (730, 365, 2555)
    - _Requirements: 5.1, 6.1, 6.4_

  - [x] 2.6 Write Alembic migration for all candidate-lifecycle tables
    - Generate DDL for all 13 tables: `candidates`, `resumes`, `candidate_job_history`, `domains`, `skills`, `candidate_skills`, `unmatched_skill_reviews`, `job_profiles`, `job_profile_skills`, `job_postings`, `job_requisitions`, `requisition_required_skills`, `candidate_requisitions`, `data_subject_access_requests`, `organization_retention_policies`
    - Include all indexes, unique constraints, and CHECK constraints from the DDL summary in the design
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 6.4_


- [x] 3. Implement Pydantic schemas for all modules
  - [x] 3.1 Create candidate and resume schemas
    - `app/modules/candidates/schemas.py`: `CandidateCreate` (name, email required; phone, location optional), `CandidateUpdate` (all optional; includes `global_status`, `ineligibility_reason`), `CandidateResponse` (all fields; version for optimistic locking), `CandidateSearchParams` (name, email, status, page, page_size max 50)
    - `app/modules/resumes/schemas.py`: `ResumeUploadResponse` (resume_id, parse_status), `ResumeResponse` (all metadata and parsed fields), paginated list wrapper
    - Enforce max field lengths per requirements; every field must include `Field(description="...")` with description ≥10 characters
    - _Requirements: 1.1, 1.6, 2.1, 2.9_

  - [x] 3.2 Create skills, job profile, job posting, and requisition schemas
    - `app/modules/skills/schemas.py`: `DomainCreate`, `DomainResponse`, `SkillCreate`, `SkillResponse`, `CandidateSkillCreate` (proficiency_rank 1–5, years_of_experience 0–50), `CandidateSkillResponse`
    - `app/modules/job_profile/schemas.py`: `JobProfileCreate`, `JobProfileSkillCreate` (designation, required_proficiency_rank), `JobProfileResponse`
    - `app/modules/job_posting/schemas.py`: `JobPostingCreate` (job_profile_id required), `JobPostingFilter` (location, salary_filter_min, salary_filter_max, sourcing_channel), `JobPostingResponse`
    - `app/modules/requisitions/schemas.py`: `RequisitionCreate`, `RequisitionUpdate` (status, version), `RequisitionResponse`, `CandidateAssociationRequest` (candidate_id)
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 5.4_

  - [x] 3.3 Create portal and privacy schemas
    - `app/modules/portal/schemas.py`: `DSARCreateRequest` (request_type: Access | Erasure), `DSARResponse` (dsar_id, status, requested_at)
    - `app/modules/privacy/schemas.py`: `DSARManageResponse` (all DSAR fields), `DSARDenyRequest` (denial_reason, min 10 chars), `RetentionPolicyResponse`, `RetentionPolicyUpdate`
    - _Requirements: 6.1, 6.6, 6.7_


- [ ] 4. Implement CandidateService and candidate router
  - [x] 4.1 Implement `CandidateService` in `app/modules/candidates/service.py`
    - `create_candidate`: compute `email_hash = SHA-256(lower(email))` and `name_hash = SHA-256(lower(name))`; encrypt name, email, phone via `encrypt_field`; check `(org_id, email_hash)` uniqueness (409 on conflict); set `global_status=ACTIVE`; `db.add(candidate)`; `await db.flush()`; call `publish_event("candidate_created", ...)`
    - `transition_status`: validate transition against `VALID_TRANSITIONS` dict (400 on invalid); enforce `ineligibility_reason` non-whitespace when transitioning to INELIGIBLE (400 if missing); set `deleted_at`/`deleted_by` when transitioning to DELETED; call `publish_event("candidate_status_changed", ...)`
    - `search_candidates`: paginated query filtering `deleted_at IS NULL`; case-insensitive partial match on `name_hash` (exact) and `email_hash` (exact) for lookup; partial name search via `func.lower(Candidate.name_hash).contains()`; max 50 per page
    - `get_candidate`: fetch by `(candidate_id, org_id)` with `deleted_at IS NULL`; 404 if not found
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 4.2 Write property test for candidate email uniqueness (Property 1)
    - **Property 1: Candidate email uniqueness within organization**
    - **Validates: Requirements 1.2**
    - Use `@given(email=st.emails(), name=st.text(min_size=1, max_size=200), org_id=st.uuids(), other_org_id=st.uuids())` with `assume(org_id != other_org_id)` and `max_examples=100`
    - Same email + same org → second `create_candidate` raises HTTPException 409; same email + different orgs → both succeed

  - [ ]* 4.3 Write property test for GlobalStatus FSM enforcement (Property 2)
    - **Property 2: GlobalStatus FSM — only valid transitions permitted**
    - **Validates: Requirements 1.7, 1.8**
    - Use `@given(from_status=st.sampled_from(list(GlobalStatus)), to_status=st.sampled_from(list(GlobalStatus)))` with `max_examples=100`
    - Valid transitions succeed and update `global_status`; invalid transitions raise HTTPException 400 and leave status unchanged

  - [ ]* 4.4 Write property test for Ineligible status requiring IneligibilityReason (Property 3)
    - **Property 3: Ineligible status requires IneligibilityReason**
    - **Validates: Requirements 1.4**
    - Use `@given(reason=st.one_of(st.none(), st.just(""), st.text(alphabet=" \t\n", min_size=1, max_size=50)))` with `max_examples=100`
    - Any absent/null/empty/whitespace-only reason → HTTPException 400; candidate `global_status` remains ACTIVE

  - [ ]* 4.5 Write property test for logical delete excluding from search (Property 4)
    - **Property 4: Logical delete excludes candidate from search**
    - **Validates: Requirements 1.5**
    - Use `@given(name=st.text(min_size=1, max_size=100), email=st.emails())` with `max_examples=100`
    - After DELETED transition: search by name and email returns no results for that candidate; raw DB fetch returns record with `deleted_at` set

  - [ ] 4.6 Implement candidate router in `app/modules/candidates/router.py`
    - `POST /api/v1/candidates` — `require_role("Recruiter", "Administrator")`; returns 201
    - `GET /api/v1/candidates` — `require_role("Recruiter", "Administrator", "HiringManager")`; paginated search
    - `GET /api/v1/candidates/{candidate_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `PATCH /api/v1/candidates/{candidate_id}` — `require_role("Recruiter", "Administrator")`; handles status transitions
    - Include full OpenAPI metadata (operation_id, summary ≤80 chars, description ≥20 chars) on every route
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8_


- [ ] 5. Implement resume storage backends and upload service
  - [x] 5.1 Implement `StorageService`, `LocalStorageBackend`, and `S3StorageBackend` in `app/modules/resumes/storage.py`
    - Define `ALLOWED_MIME_TYPES` set and `MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024`
    - `LocalStorageBackend.store`: create `{base_path}/{org_id}/` directory; write `{uuid4()}_{filename}`; return `local://{path}`
    - `LocalStorageBackend.delete`: unlink file if exists
    - `S3StorageBackend.store`: `boto3.client("s3").put_object(Bucket=settings.RESUME_BUCKET_NAME, Key=f"{org_id}/{uuid4()}_{filename}", Body=file_bytes)`; return `s3://{bucket}/{key}`
    - `S3StorageBackend.delete`: extract key from URI; call `delete_object`
    - `get_storage_service()`: return `S3StorageBackend()` if `settings.STORAGE_BACKEND == "s3"` else `LocalStorageBackend()`
    - _Requirements: 2.2, 2.3, 2.4_

  - [ ]* 5.2 Write property test for resume file format and size validation (Property 5)
    - **Property 5: Resume file format and size validation**
    - **Validates: Requirements 2.2, 2.3**
    - Use `@given(mime_type=st.text(min_size=1, max_size=100), file_size=st.integers(min_value=1, max_value=20*1024*1024))` with `max_examples=200`
    - Invalid MIME type or size > 10 MB → `validate_file` raises HTTPException 422; valid MIME + size ≤ 10 MB → no exception

  - [ ] 5.3 Implement `ResumeService.upload_resume` in `app/modules/resumes/service.py`
    - Call `validate_file(mime_type, len(file_bytes))` (422 on failure)
    - Call `await self.storage.store(file_bytes, filename, org_id)` to get `storage_uri`
    - Insert `Resume` record with `parse_status=PENDING`; `await db.flush()`
    - Call `background_tasks.add_task(_run_ingestion, resume_id, storage_uri, org_id, correlation_id_var.get(""))`
    - Return resume record with 202 status
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [ ] 5.4 Implement resume router in `app/modules/resumes/router.py`
    - `POST /api/v1/resumes/upload` — `require_role("Recruiter", "Administrator")`; accepts `multipart/form-data`; returns 202
    - `GET /api/v1/candidates/{candidate_id}/resumes` — `require_role("Recruiter", "Administrator", "HiringManager")`; paginated
    - `GET /api/v1/resumes/{resume_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - _Requirements: 2.2, 2.9, 2.10_


- [ ] 6. Implement resume ingestion background task
  - [ ] 6.1 Implement `_run_ingestion` and `_apply_ingestion_results` in `app/modules/resumes/service.py`
    - `_run_ingestion`: open new `AsyncSessionFactory` session; fetch `Resume` by `resume_id`; POST to `http://localhost:8000/internal/agents/resume-ingestion` with `X-Agent-API-Key` and `X-Correlation-ID` headers; on success call `_apply_ingestion_results` and set `parse_status=COMPLETED`; on any exception set `parse_status=FAILED` and log ERROR with `resume_id`, `correlation_id`; always `await db.commit()`
    - `_apply_ingestion_results`: call `CandidateService.upsert_candidate(extracted_data, org_id, db)` to create/update Candidate; insert `CandidateJobHistory` records for each job history entry; call `SkillService.match_and_link_skills(candidate_id, org_id, skills, db)`; associate resume with candidate; all within the same session
    - _Requirements: 2.5, 2.6, 2.8_

  - [ ]* 6.2 Write property test for ParseStatus transitions on ingestion outcome (Property 6)
    - **Property 6: ParseStatus transitions correctly on ingestion outcome**
    - **Validates: Requirements 2.6, 2.8**
    - Use `@given(agent_succeeds=st.booleans())` with `max_examples=100`; mock `httpx.AsyncClient.post`
    - Agent success → `parse_status=COMPLETED`, `parsed_data` populated; agent failure → `parse_status=FAILED`, error logged with `correlation_id`

  - [ ]* 6.3 Write property test for ingestion upsert of all associated records (Property 7)
    - **Property 7: Ingestion upserts all associated records on success**
    - **Validates: Requirements 2.6**
    - Use `@given(job_history_count=st.integers(min_value=0, max_value=5), skill_count=st.integers(min_value=0, max_value=10))` with `max_examples=100`
    - Successful ingestion with N job history entries and M skills → exactly N `CandidateJobHistory` records and ≤M `CandidateSkill` records created within the same transaction; `parse_status=COMPLETED`


- [ ] 7. Checkpoint — candidate and resume pipeline working
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement skills taxonomy service and router
  - [x] 8.1 Implement `SkillService` in `app/modules/skills/service.py`
    - `create_domain`: check name uniqueness (409 on conflict); insert `Domain`; return
    - `create_skill`: check `(domain_id, name)` uniqueness (409 on conflict); insert `Skill`; return
    - `match_and_link_skills(candidate_id, org_id, extracted_skills)`: for each skill name, execute `SELECT Skill WHERE func.lower(Skill.name) == skill_name.lower().strip()`; if matched → upsert `CandidateSkill(source=PARSED)`; if unmatched → insert `UnmatchedSkillReview` and log WARNING; zero skills → no-op; `await db.flush()`
    - `add_candidate_skill`: validate `proficiency_rank` 1–5 and `years_of_experience` 0–50 (422 on violation); check duplicate (409); insert `CandidateSkill`
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6_

  - [ ]* 8.2 Write property test for case-insensitive skill matching (Property 8)
    - **Property 8: Skill matching is case-insensitive**
    - **Validates: Requirements 3.4**
    - Use `@given(base_name=st.text(min_size=2, max_size=50, alphabet=st.characters(whitelist_categories=("L",))), case_variant=st.sampled_from(["lower", "upper", "title", "mixed"]))` with `max_examples=100`
    - Skill stored as `base_name.lower()`; extracted variant in any case → `CandidateSkill` linked to the existing `Skill` entity

  - [ ]* 8.3 Write property test for unmatched and zero skills not blocking ingestion (Property 9)
    - **Property 9: Unmatched or zero skills do not block ingestion**
    - **Validates: Requirements 3.5, 3.6**
    - Use `@given(skill_names=st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10))` with `max_examples=100`
    - All skill names are non-existent in taxonomy; `match_and_link_skills` completes without exception; `UnmatchedSkillReview` records created for each non-empty name; empty list → no records created

  - [ ] 8.4 Implement skills router in `app/modules/skills/router.py`
    - `GET /api/v1/domains`, `POST /api/v1/domains` — `require_role("Recruiter", "Administrator")`
    - `GET /api/v1/domains/{domain_id}/skills`, `POST /api/v1/domains/{domain_id}/skills` — `require_role("Recruiter", "Administrator")`
    - `GET /api/v1/candidates/{candidate_id}/skills`, `POST /api/v1/candidates/{candidate_id}/skills` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `GET /api/v1/unmatched-skill-reviews` — `require_role("Administrator")`; paginated list of unresolved reviews
    - _Requirements: 3.1, 3.2, 3.3_


- [ ] 9. Implement JobProfile service and router
  - [x] 9.1 Implement `JobProfileService` in `app/modules/job_profile/service.py`
    - `create_job_profile(org_id, name, skills, created_by)`: insert `JobProfile`; for each skill entry insert `JobProfileSkill(designation, required_proficiency_rank)`; `await db.flush()`; return
    - `update_job_profile`: update name and skill associations; use `VersionMixin` optimistic locking (409 on `StaleDataError`)
    - `delete_job_profile`: soft-delete by setting `deleted_at`/`deleted_by`
    - `get_job_profile` / `list_job_profiles`: org-scoped queries filtering `deleted_at IS NULL`
    - _Requirements: 4.1_

  - [ ] 9.2 Implement job profile router in `app/modules/job_profile/router.py`
    - `POST /api/v1/job-profiles` — `require_role("Recruiter")`; returns 201
    - `GET /api/v1/job-profiles`, `GET /api/v1/job-profiles/{job_profile_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `PATCH /api/v1/job-profiles/{job_profile_id}`, `DELETE /api/v1/job-profiles/{job_profile_id}` — `require_role("Recruiter")`; 403 for any other role
    - _Requirements: 4.1, 4.6_

- [ ] 10. Implement JobPosting service and router
  - [x] 10.1 Implement `JobPostingService` in `app/modules/job_posting/service.py`
    - `create_posting`: validate `job_profile_id` exists, belongs to org, and `deleted_at IS NULL` (400 if invalid); insert `JobPosting`; `await db.flush()`; return
    - `list_postings`: org-scoped query; apply location filter (`work_locations.any(location)`); apply salary overlap filter (`salary_min <= filter_max AND salary_max >= filter_min`) when both filter values provided; apply `sourcing_channel` exact match; paginated with offset/limit
    - `update_posting` / `delete_posting`: org-scoped; `VersionMixin` optimistic locking
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [ ]* 10.2 Write property test for JobPosting requiring valid JobProfile (Property 10)
    - **Property 10: JobPosting requires a valid JobProfile**
    - **Validates: Requirements 4.3, 4.4**
    - Use `@given(profile_exists=st.booleans(), profile_deleted=st.booleans(), same_org=st.booleans())` with `max_examples=100`
    - Missing, deleted, or cross-org `job_profile_id` → HTTPException 400; valid profile → posting created successfully

  - [ ]* 10.3 Write property test for salary range overlap filter correctness (Property 11)
    - **Property 11: Salary range overlap filter correctness**
    - **Validates: Requirements 4.5**
    - Use `@given(postings=st.lists(st.fixed_dictionaries({"salary_min": st.floats(0, 200000), "salary_max": st.floats(0, 200000)}), min_size=1, max_size=20), filter_min=st.floats(0, 200000), filter_max=st.floats(0, 200000))` with `assume(filter_min <= filter_max)` and `max_examples=100`
    - All returned postings satisfy `posting.salary_min <= filter_max AND posting.salary_max >= filter_min`; no non-overlapping posting appears in results

  - [ ] 10.4 Implement job posting router in `app/modules/job_posting/router.py`
    - `POST /api/v1/job-postings` — `require_role("Recruiter")`; returns 201
    - `GET /api/v1/job-postings` — `require_role("Recruiter", "Administrator", "HiringManager")`; accepts filter query params
    - `GET /api/v1/job-postings/{job_posting_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `PATCH /api/v1/job-postings/{job_posting_id}`, `DELETE /api/v1/job-postings/{job_posting_id}` — `require_role("Recruiter")`; 403 for any other role
    - _Requirements: 4.2, 4.5, 4.6_


- [ ] 11. Checkpoint — skills, job profiles, and job postings working
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement RequisitionService and requisition router
  - [ ] 12.1 Implement `RequisitionService` in `app/modules/requisitions/service.py`
    - `create_requisition`: set `status=OPEN` regardless of any value in the request body; insert `JobRequisition`; `await db.flush()`; call `publish_event("requisition_status_changed", ...)`; return
    - `transition_status`: validate against `VALID_REQUISITION_TRANSITIONS` dict (400 on invalid); update `status`; `await db.flush()`; call `publish_event("requisition_status_changed", ...)`
    - `associate_candidate`: validate `requisition.status == OPEN` (400 if not); validate `candidate.global_status in (ACTIVE, INTERVIEWING)` (400 if not); check duplicate `CandidateRequisition` (409 if exists); insert `CandidateRequisition`; `await db.flush()`
    - `list_requisitions`: org-scoped paginated query; filter by `hiring_manager_user_id`, `status`, `department`, `domain` (via join to `job_profile_skills` → `skills` → `domains`)
    - `add_required_skill`: validate `proficiency_rank` 1–5 and `weight` 1–10 (422); check duplicate (409); insert `RequisitionRequiredSkill`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 12.2 Write property test for candidate-requisition association validation (Property 12)
    - **Property 12: Candidate-requisition association validation**
    - **Validates: Requirements 5.3**
    - Use `@given(req_status=st.sampled_from(list(RequisitionStatus)), candidate_status=st.sampled_from(list(GlobalStatus)), is_duplicate=st.booleans())` with `max_examples=100`
    - Non-Open requisition → 400; non-Active/Interviewing candidate → 400; duplicate association → 409; valid combination → success

  - [ ]* 12.3 Write property test for requisition status FSM enforcement (Property 13)
    - **Property 13: Requisition status FSM — transitions only on update**
    - **Validates: Requirements 5.2, 5.6**
    - Use `@given(from_status=st.sampled_from(list(RequisitionStatus)), to_status=st.sampled_from(list(RequisitionStatus)))` with `max_examples=100`
    - Creation always sets `status=OPEN`; valid update transitions succeed; invalid transitions → HTTPException 400

  - [ ] 12.4 Implement requisition router in `app/modules/requisitions/router.py`
    - `POST /api/v1/requisitions` — `require_role("Recruiter", "Administrator")`; returns 201
    - `GET /api/v1/requisitions`, `GET /api/v1/requisitions/{requisition_id}` — `require_role("Recruiter", "Administrator", "HiringManager")`
    - `PATCH /api/v1/requisitions/{requisition_id}` — `require_role("Recruiter", "Administrator")`
    - `POST /api/v1/requisitions/{requisition_id}/candidates` — `require_role("Recruiter", "Administrator")`; associate candidate
    - `POST /api/v1/requisitions/{requisition_id}/required-skills` — `require_role("Recruiter", "Administrator")`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_


- [ ] 13. Implement portal DSAR endpoint and privacy service
  - [ ] 13.1 Implement portal DSAR creation in `app/modules/portal/service.py` and `router.py`
    - `PortalService.create_dsar(candidate_id, org_id, request_type)`: insert `DataSubjectAccessRequest(status=PENDING, requested_at=now())`; `await db.flush()`; return
    - `POST /api/v1/portal/dsar` — authenticated candidates only (any role); returns 201 with `dsar_id` and `status=Pending`
    - Endpoint must remain permanently accessible; no role restriction beyond valid JWT
    - _Requirements: 6.1_

  - [ ] 13.2 Implement `PrivacyService` DSAR management in `app/modules/privacy/service.py`
    - `process_access_dsar(dsar)`: guard `dsar.request_type == ACCESS` (400 if not); compile candidate profile, job history, skills, questionnaire responses, availability slots, and journey metadata; set `dsar.status=COMPLETED`, `dsar.completed_at=now()`; `await db.flush()`; return compiled dict
    - `process_erasure_dsar(dsar)`: hard-delete `Resume` records for `candidate_id`; hard-delete `Candidate` record; anonymize `AuditLog` entries (set `candidate_id=None`, `anonymized=True`, `anonymized_placeholder="ANONYMIZED"`); set `dsar.status=COMPLETED`, `dsar.completed_at=now()`; `await db.flush()`
    - `deny_dsar(dsar, denial_reason, denied_by)`: validate `len(denial_reason.strip()) >= 10` (400 if not); set `dsar.status=DENIED`, `dsar.denial_reason=denial_reason`; write audit log entry with `denied_by`; `await db.flush()`
    - `list_dsars(org_id, status, page, page_size)`: org-scoped paginated query
    - _Requirements: 6.2, 6.3, 6.6, 6.7_

  - [ ]* 13.3 Write property test for DSAR Access workflow isolation (Property 14)
    - **Property 14: DSAR Access workflow only triggered for RequestType=Access**
    - **Validates: Requirements 6.2**
    - Use `@given(request_type=st.sampled_from(list(DSARRequestType)))` with `max_examples=100`
    - `request_type != ACCESS` → `process_access_dsar` raises HTTPException 400; no data compiled; `request_type == ACCESS` → data compiled and returned

  - [ ]* 13.4 Write property test for DSAR Erasure hard-deleting personal data (Property 15)
    - **Property 15: DSAR Erasure hard-deletes personal data and anonymizes audit trail**
    - **Validates: Requirements 6.3**
    - Use `@given(resume_count=st.integers(min_value=0, max_value=5))` with `max_examples=100`
    - After `process_erasure_dsar`: candidate record absent from DB; all resume records absent; audit log entries for candidate have `anonymized=True`; `dsar.status=COMPLETED`

  - [ ]* 13.5 Write property test for DSAR denial requiring minimum-length reason (Property 19)
    - **Property 19: DSAR denial requires minimum-length reason**
    - **Validates: Requirements 6.7**
    - Use `@given(reason=st.one_of(st.none(), st.just(""), st.text(max_size=9)))` with `max_examples=100`
    - Short/absent reason → HTTPException 400; DSAR status unchanged; valid reason (≥10 chars) → denial recorded in audit log

  - [ ] 13.6 Implement privacy management router in `app/modules/privacy/router.py`
    - `GET /api/v1/dsar` — `require_role("Administrator", "HRManager")`; paginated list
    - `PATCH /api/v1/dsar/{dsar_id}` — `require_role("Administrator", "HRManager")`; process Access or Erasure based on `request_type`
    - `POST /api/v1/dsar/{dsar_id}/deny` — `require_role("Administrator", "HRManager")`; requires `denial_reason`
    - `GET /api/v1/privacy/retention-policy` — `require_role("Administrator")`
    - `PATCH /api/v1/privacy/retention-policy` — `require_role("Administrator")`
    - _Requirements: 6.2, 6.3, 6.6, 6.7_


- [ ] 14. Implement background schedulers
  - [ ] 14.1 Implement `CandidateService.run_expiry_check` in `app/modules/candidates/service.py`
    - Compute `cutoff = now() - timedelta(days=90)`
    - Build subquery for candidates with active `InterviewJourney` (OverallStatus ACTIVE or ON_HOLD, `deleted_at IS NULL`)
    - Query `Candidate WHERE global_status=ACTIVE AND updated_at < cutoff AND deleted_at IS NULL AND candidate_id NOT IN (active_journey_subq)`
    - For each result: set `global_status=EXPIRED`; call `publish_event("candidate_expired", ...)`
    - `await db.flush()`; log INFO `expiry_run_complete` with count; return count
    - _Requirements: 1.3_

  - [ ]* 14.2 Write property test for candidate expiry scheduler qualification (Property 17)
    - **Property 17: Candidate expiry scheduler only affects qualifying Active candidates**
    - **Validates: Requirements 1.3**
    - Use `@given(days_since_update=st.integers(min_value=0, max_value=200), has_active_journey=st.booleans())` with `max_examples=100`
    - Backdate `updated_at` by `days_since_update`; optionally create active journey; run `run_expiry_check()`
    - `days_since_update >= 90 AND NOT has_active_journey` → `global_status=EXPIRED`; otherwise → `global_status=ACTIVE`

  - [ ] 14.3 Implement `PrivacyService.run_retention_purge` in `app/modules/privacy/service.py`
    - Query all `OrganizationRetentionPolicy` records
    - For each policy: compute `candidate_cutoff = now() - timedelta(days=policy.candidate_data_retention_days)` and `resume_cutoff = now() - timedelta(days=policy.resume_retention_days)`
    - Hard-delete `Resume` records where `organization_id == policy.organization_id AND created_at < resume_cutoff`; log INFO `retention_purge_resume` per record
    - Hard-delete `Candidate` records where `organization_id == policy.organization_id AND created_at < candidate_cutoff AND deleted_at IS NOT NULL`; log INFO `retention_purge_candidate` per record
    - `await db.flush()`; return `{"candidates": N, "resumes": M}`
    - _Requirements: 6.5_

  - [ ]* 14.4 Write property test for retention policy purge respecting configured days (Property 16)
    - **Property 16: Retention policy purge respects configured retention days**
    - **Validates: Requirements 6.5**
    - Use `@given(retention_days=st.integers(min_value=1, max_value=3650), age_days=st.integers(min_value=0, max_value=4000))` with `max_examples=100`
    - Create candidate/resume with `created_at` backdated by `age_days`; configure policy with `retention_days`; run `run_retention_purge()`
    - `age_days > retention_days` → record purged and logged; `age_days <= retention_days` → record preserved

  - [ ] 14.5 Register expiry and retention schedulers in `app/main.py` lifespan
    - Add `asyncio.create_task(_run_expiry_scheduler())` and `asyncio.create_task(_run_retention_scheduler())` in the lifespan `asynccontextmanager`
    - Each scheduler loops `asyncio.sleep(24 * 3600)` then opens a new `AsyncSessionFactory` session, calls the service method, and commits
    - Cancel both tasks on shutdown
    - _Requirements: 1.3, 6.5_


- [ ] 15. Implement role-based access enforcement and wire all modules
  - [ ] 15.1 Verify `require_role()` guards on all protected endpoints
    - Audit every router in `candidates`, `resumes`, `skills`, `job_profile`, `job_posting`, `requisitions`, `portal`, `privacy` to confirm `require_role()` dependencies are applied per the authorization matrix in the design
    - Ensure `POST /api/v1/portal/dsar` has no role restriction beyond valid JWT
    - Ensure DSAR management endpoints (`GET /dsar`, `PATCH /dsar/{id}`, `POST /dsar/{id}/deny`) are restricted to `Administrator` or `HRManager`
    - _Requirements: 2.10, 4.6, 6.6_

  - [ ]* 15.2 Write property test for role-based access enforcement (Property 18)
    - **Property 18: Role-based access enforcement**
    - **Validates: Requirements 2.10, 4.6, 6.6**
    - Use `@given(role=st.sampled_from(["SuperAdministrator", "Administrator", "Recruiter", "HiringManager", "CommitteeMember", "HRManager", "Interviewer"]))` with `max_examples=100`
    - Non-Recruiter → `POST /job-profiles` returns 403; non-Recruiter/Administrator → `POST /resumes/upload` returns 403; non-Recruiter/Administrator/HiringManager → `GET /resumes` returns 403; non-Administrator/HRManager → `GET /dsar` returns 403

  - [ ] 15.3 Register all candidate-lifecycle routers in `app/main.py`
    - Include `candidates`, `resumes`, `skills`, `job_profile`, `job_posting`, `requisitions`, `portal`, `privacy` routers under `/api/v1` prefix
    - Ensure `POST /api/v1/portal/dsar` is not excluded from JWT auth (candidates must be authenticated)
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1_

  - [ ] 15.4 Add Alembic `env.py` imports for all candidate-lifecycle models
    - Import all 13 model modules in `alembic/env.py` so `Base.metadata` includes all tables
    - Verify `alembic check` reports no missing migrations
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 6.4_


- [ ] 16. Checkpoint — all modules wired and role guards verified
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Write integration and smoke tests
  - [ ]* 17.1 Write integration tests for full candidate lifecycle
    - Create candidate → upload resume → mock ingestion agent → verify Candidate/CandidateJobHistory/CandidateSkill records → search by name/email → transition status → soft-delete → verify excluded from search
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 2.5, 2.6_

  - [ ]* 17.2 Write integration tests for skill matching and unmatched review
    - Create domain and skill → ingest resume with matching skill name in various cases → verify `CandidateSkill` linked to existing `Skill`
    - Ingest resume with unmatched skill name → verify `UnmatchedSkillReview` created; ingestion still completes with `ParseStatus=COMPLETED`
    - _Requirements: 3.4, 3.5, 3.6_

  - [ ]* 17.3 Write integration tests for job posting salary overlap filter
    - Create postings with various salary ranges → filter with overlap query → verify all results satisfy `posting.salary_min <= filter_max AND posting.salary_max >= filter_min`
    - _Requirements: 4.5_

  - [ ]* 17.4 Write integration tests for requisition pipeline
    - Create requisition → verify `status=Open`; associate Active candidate → verify success; associate Ineligible candidate → verify 400; transition status through valid path → verify; attempt invalid transition → verify 400
    - _Requirements: 5.2, 5.3, 5.6_

  - [ ]* 17.5 Write integration tests for DSAR Access and Erasure workflows
    - Create candidate with full data → submit Access DSAR via portal → process via admin → verify JSON document contains all fields and `status=Completed`
    - Create candidate → submit Erasure DSAR → process → verify hard-delete of candidate/resumes and audit log anonymization
    - _Requirements: 6.2, 6.3_

  - [ ]* 17.6 Write integration tests for retention purge and expiry scheduler
    - Create data with backdated timestamps → run `run_retention_purge()` → verify only expired data removed and each purge logged
    - Create Active candidates with various ages and journey states → run `run_expiry_check()` → verify correct candidates set to Expired
    - _Requirements: 1.3, 6.5_

  - [ ]* 17.7 Write smoke tests for candidate-lifecycle module
    - `STORAGE_BACKEND` env var is set to a valid value (`local` or `s3`)
    - `LocalStorageBackend` base directory is writable when `STORAGE_BACKEND=local`
    - `RESUME_BUCKET_NAME` is configured when `STORAGE_BACKEND=s3`
    - All required enum values present: `GlobalStatus`, `ParseStatus`, `RequisitionStatus`, `DSARRequestType`, `DSARStatus`
    - Alembic migrations complete without error on all 13 candidate-lifecycle tables
    - Expiry and retention schedulers start without error on application startup
    - _Requirements: 1.1, 2.4, 6.4_

- [ ] 18. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints at tasks 7, 11, 16, and 18 ensure incremental validation
- Property tests use Hypothesis with `max_examples=100` (minimum 200 for Property 5); tag each test with `# Feature: candidate-lifecycle, Property N: <property_text>`
- Unit tests complement property tests by covering specific examples, edge cases, and error conditions per the Testing Strategy in the design
- All code uses async SQLAlchemy sessions throughout; no synchronous DB calls
- PII fields (name, email, phone) are stored AES-256-GCM encrypted; SHA-256 hashes enable search without decryption
- The `_run_ingestion` background task opens its own `AsyncSessionFactory` session independent of the request session
- `VersionMixin` optimistic locking is applied to `Candidate`, `JobProfile`, `JobPosting`, and `JobRequisition`; `StaleDataError` → 409
- The portal DSAR endpoint (`POST /api/v1/portal/dsar`) must remain permanently accessible to all authenticated candidates
- Storage backend is selected at startup via `STORAGE_BACKEND` env var; `get_storage_service()` is injected as a FastAPI dependency
- Expiry and retention schedulers run as `asyncio.create_task` in the FastAPI lifespan; each opens a fresh DB session per run

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5"] },
    { "id": 2, "tasks": ["2.6", "3.1", "3.2", "3.3"] },
    { "id": 3, "tasks": ["4.1", "5.1", "8.1", "9.1", "10.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "4.5", "4.6", "5.2", "5.3", "5.4", "6.1", "8.2", "8.3", "8.4", "9.2", "10.2", "10.3", "10.4"] },
    { "id": 5, "tasks": ["6.2", "6.3", "12.1"] },
    { "id": 6, "tasks": ["12.2", "12.3", "12.4", "13.1", "13.2"] },
    { "id": 7, "tasks": ["13.3", "13.4", "13.5", "13.6", "14.1", "14.2", "14.3", "14.4", "14.5"] },
    { "id": 8, "tasks": ["15.1", "15.2", "15.3", "15.4"] },
    { "id": 9, "tasks": ["17.1", "17.2", "17.3", "17.4", "17.5", "17.6", "17.7"] }
  ]
}
```
