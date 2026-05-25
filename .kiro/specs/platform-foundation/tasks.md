# Implementation Plan: Platform Foundation

## Overview

This plan implements the cross-cutting infrastructure for the TalentKru.ai FastAPI backend. Tasks are ordered so each step builds on the previous: project scaffolding → configuration → database layer → base models → observability → domain events → multi-tenancy → middleware → API conventions → concurrency control → wiring and integration.

All code is Python (FastAPI, SQLAlchemy async, Alembic, structlog, prometheus-client, hypothesis).

---

## Tasks

- [ ] 1. Scaffold project structure and tooling
  - Create the directory layout: `app/`, `app/domain_events/`, `app/observability/`, `app/middleware/`, `app/modules/` (with all 18 sub-module stubs), `alembic/versions/`, `tests/`
  - Add `pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `structlog`, `prometheus-client`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `hypothesis`, `pytest`, `pytest-asyncio`, `httpx`
  - Add `docker-compose.yml` with `postgres` (pgvector image) and `app` services; include a `test` profile for the test database
  - Add `.env.example` listing every required and optional variable from Requirements 1.1
  - Add `entrypoint.sh` that runs `alembic upgrade head` then starts `uvicorn`
  - _Requirements: 1.1, 1.4, 1.7_

- [ ] 2. Implement configuration management
  - [ ] 2.1 Implement `app/config.py` with `pydantic-settings` `BaseSettings`
    - Define all fields from Requirements 1.1 with correct types and defaults
    - Add `field_validator` for JWT_SIGNING_KEY, ENCRYPTION_KEY, AGENT_API_KEY, METRICS_USERNAME, METRICS_PASSWORD to reject empty/whitespace values
    - Add `database_url` property returning the `postgresql+asyncpg://` connection string
    - Instantiate `settings = Settings()` at module level so startup validation fires on import
    - _Requirements: 1.1, 1.2_

  - [ ]* 2.2 Write property test for startup validation (Property 1)
    - **Property 1: Startup fails on any missing required variable**
    - **Validates: Requirements 1.2**
    - Use `hypothesis` `st.sampled_from` over the list of required variable names; for each sampled variable, construct a `Settings` with that variable absent or empty and assert `ValidationError` is raised with the variable name in the message

- [ ] 3. Implement database layer and base models
  - [ ] 3.1 Implement `app/database.py`
    - Create async engine with `pool_pre_ping=True`, `pool_size=10`, `max_overflow=20`
    - Create `AsyncSessionFactory` with `expire_on_commit=False`
    - Implement `get_db_session()` async generator dependency with commit-on-success and rollback-on-exception
    - _Requirements: 1.4, 1.5_

  - [ ] 3.2 Implement `app/base_model.py` with `AuditMixin` and `VersionMixin`
    - Define `Base(DeclarativeBase)`
    - Define `current_user_id_var: ContextVar[str | None]`
    - Implement `AuditMixin` with `created_at`, `updated_at`, `deleted_at`, `created_by`, `updated_by`, `deleted_by` columns
    - Implement `VersionMixin` with `version` column and `__mapper_args__` returning `{"version_id_col": cls.__table__.c.version}`
    - Register a `SessionEvents.before_flush` listener that reads `current_user_id_var` and populates audit fields on new, dirty, and soft-deleted instances
    - _Requirements: 1.8, 1.9, 1.10, 7.1, 7.5_

  - [ ]* 3.3 Write property test for audit fields on create (Property 2)
    - **Property 2: Audit fields invariant on create**
    - **Validates: Requirements 1.8**
    - Use `hypothesis` `st.uuids()` for user IDs; set `current_user_id_var`, create an entity, flush, and assert `created_at` is UTC, `created_by` equals the user ID, `updated_at == created_at`, `deleted_at is None`

  - [ ]* 3.4 Write property test for audit fields on update (Property 3)
    - **Property 3: Audit fields invariant on update**
    - **Validates: Requirements 1.9**
    - Use `hypothesis` to generate a user ID for create and a different user ID for update; assert `updated_at >= created_at`, `updated_by` equals the update user, `created_at` and `created_by` are unchanged

  - [ ]* 3.5 Write property test for soft-delete audit field preservation (Property 4)
    - **Property 4: Soft-delete preserves prior audit fields**
    - **Validates: Requirements 1.10**
    - Capture pre-delete values of `created_at`, `created_by`, `updated_at`, `updated_by`; perform soft-delete; assert `deleted_at` is set, `deleted_by` equals current user, and all pre-delete fields are unchanged

- [ ] 4. Configure Alembic and initial migrations
  - Implement `alembic/env.py` importing `Base.metadata` and all module model files (noqa stubs for now)
  - Configure async migration runner using `run_async_migrations()` with `asyncio.run()`
  - Generate initial migration creating `organizations` and `domain_events` tables with all columns, indexes, and constraints from the DDL in the design
  - Ensure `CREATE EXTENSION IF NOT EXISTS vector` and `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"` are included in the initial migration
  - _Requirements: 1.4, 1.6, 2.1, 3.2_

- [ ] 5. Implement observability layer
  - [ ] 5.1 Implement `app/observability/middleware.py` — Correlation ID middleware
    - Define `correlation_id_var: ContextVar[str]`
    - Implement `CorrelationIDMiddleware(BaseHTTPMiddleware)` that reads `X-Correlation-ID` from request headers or generates a UUID4; stores in `correlation_id_var`; echoes back in response headers
    - _Requirements: 4.4, 4.6_

  - [ ] 5.2 Implement `app/observability/logging.py` — structured JSON logging
    - Configure `structlog` with processors: `add_log_level`, `add_logger_name`, `TimeStamper(fmt="iso")`, custom `add_correlation_id` processor reading `correlation_id_var`, `JSONRenderer`
    - Expose `get_logger(name: str)` helper
    - _Requirements: 4.1_

  - [ ] 5.3 Implement `app/observability/metrics.py` — Prometheus metric definitions
    - Define all seven metrics from Requirements 4.2: `resumes_parsed_total`, `match_computation_duration_ms` (Histogram with design buckets), `matches_per_requisition_total`, `questionnaire_completions_total`, `ai_agent_errors_total`, `interview_volume`, `no_show_rate`
    - _Requirements: 4.2_

  - [ ] 5.4 Implement `app/observability/tracing.py` — OpenTelemetry tracer setup
    - Initialize `TracerProvider` and configure `FastAPIInstrumentor`
    - Expose `get_tracer(name: str)` helper
    - Ensure spans are propagated through background tasks via `correlation_id_var`
    - _Requirements: 4.4_

  - [ ] 5.5 Implement metrics endpoint in `app/modules/observability/router.py`
    - Implement `verify_metrics_credentials` dependency using `HTTPBasic` and `secrets.compare_digest`
    - Implement `GET /metrics` route returning `generate_latest()` with `CONTENT_TYPE_LATEST`; include full OpenAPI metadata (operation_id, summary ≤80 chars, description ≥20 chars)
    - _Requirements: 4.2, 4.3, 5.1_

  - [ ]* 5.6 Write property test for metrics endpoint authentication (Property 11)
    - **Property 11: Metrics endpoint rejects unauthenticated requests**
    - **Validates: Requirements 4.3**
    - Use `hypothesis` `st.text()` for username and password; for any credential pair that does not exactly match `METRICS_USERNAME`/`METRICS_PASSWORD`, assert the response is `401 Unauthorized`

  - [ ]* 5.7 Write property test for structured log field completeness (Property 10)
    - **Property 10: Structured log entries contain required fields**
    - **Validates: Requirements 4.1**
    - Use `hypothesis` `st.sampled_from` over tracked workflow names; capture log output; assert each JSON record contains `correlation_id`, `timestamp`, `level`, `logger`, and `event` keys

  - [ ]* 5.8 Write property test for correlation ID propagation (Property 12)
    - **Property 12: Correlation ID propagation through background tasks**
    - **Validates: Requirements 4.4, 4.6**
    - Use `hypothesis` `st.text(min_size=1, max_size=64)` for correlation IDs; enqueue a background task with a known correlation ID; assert all log entries produced by the task carry the same ID

  - [ ]* 5.9 Write property test for AI agent failure log completeness (Property 13)
    - **Property 13: AI agent failure log completeness**
    - **Validates: Requirements 4.5**
    - Use `hypothesis` to generate agent names, payload sizes, and error types; simulate an agent failure; assert the ERROR log entry contains `correlation_id`, `agent_name`, `input_payload_size`, `error_type`, and `error_description`

- [ ] 6. Checkpoint — core infrastructure
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement domain event infrastructure
  - [ ] 7.1 Implement `app/domain_events/models.py`
    - Define `EventStatus(str, enum.Enum)` with PENDING, PROCESSED, FAILED values
    - Define `DomainEvent(Base)` ORM model with all columns from the design: `event_id`, `event_type`, `payload` (JSONB), `published_at`, `processed_at`, `status` (SQLEnum), `correlation_id`
    - Add indexes on `status` and `event_type`
    - _Requirements: 3.2_

  - [ ] 7.2 Implement `app/domain_events/handlers.py`
    - Define `HandlerRegistry` mapping event type strings to async handler callables
    - Implement `register_handler(event_type: str, handler: Callable)` and `dispatch_event(event: DomainEvent, correlation_id: str | None)` functions
    - Pre-register stubs for all required event types: `journey_stage_changed`, `questionnaire_submitted`, `interview_slot_created`, `offer_accepted`, `candidate_created`, `candidate_status_changed`, `role_assignment_changed`, `requisition_status_changed`
    - _Requirements: 3.7_

  - [ ] 7.3 Implement `app/domain_events/publisher.py`
    - Implement `publish_event(event_type, payload, db, background_tasks, correlation_id)` following the persist-first pattern: `db.add(event)` → `await db.flush()` → conditionally `background_tasks.add_task(...)`
    - Implement `_dispatch_with_status_update(event_id, correlation_id)` with try/except/finally that always commits status update
    - Log `WARNING` when `background_tasks` is `None`; log `ERROR` on handler failure with `event_id` and `correlation_id`
    - _Requirements: 3.1, 3.3, 3.4, 3.5_

  - [ ]* 7.4 Write property test for event persistence without BackgroundTasks (Property 7)
    - **Property 7: Domain event persistence regardless of BackgroundTasks availability**
    - **Validates: Requirements 3.1, 3.3**
    - Use `hypothesis` `st.sampled_from` over required event types and `st.fixed_dictionaries` for payloads; call `publish_event(..., background_tasks=None)`; assert event is in DB with `status == PENDING`

  - [ ]* 7.5 Write property test for successful handler → Processed transition (Property 8)
    - **Property 8: Successful handler transitions event to Processed**
    - **Validates: Requirements 3.4**
    - Use `hypothesis` to generate event types and payloads; mock handler to succeed; assert `status == PROCESSED` and `processed_at` is a UTC timestamp after dispatch

  - [ ]* 7.6 Write property test for failed handler → Failed transition (Property 9)
    - **Property 9: Failed handler transitions event to Failed**
    - **Validates: Requirements 3.5**
    - Use `hypothesis` to generate event types; mock handler to raise an exception; assert `status == FAILED` and error is logged with `event_id` and `correlation_id`

  - [ ] 7.7 Implement `app/domain_events/retry.py`
    - Implement `retry_failed_events(db: AsyncSession)` that queries `DomainEvent` where `status == FAILED`, re-dispatches each via `_dispatch_with_status_update`, and logs results
    - _Requirements: 3.5, 3.6_

- [ ] 8. Implement multi-tenant organization module
  - [ ] 8.1 Implement `app/shard_router.py`
    - Implement `get_shard_id(organization_id: UUID) -> int` always returning 0
    - Implement `get_engine_for_org(organization_id: UUID)` returning the shard-0 engine from a `shard_engines` dict
    - _Requirements: 2.2, 2.3_

  - [ ] 8.2 Implement `app/modules/organizations/models.py`
    - Define `Organization(Base, AuditMixin, VersionMixin)` with all columns: `organization_id`, `name` (VARCHAR 128), `slug` (VARCHAR 64, UNIQUE), `logo_url`, `primary_color`, `secondary_color`, `terms_url`, `contact_name` (VARCHAR 128, nullable), `contact_email` (VARCHAR 254, nullable), `contact_phone` (VARCHAR 32, nullable), `feature_flags` (JSONB), `shard_id` (default 0), `allowed_origins` (ARRAY of VARCHAR 253)
    - _Requirements: 2.1, 2.2, 6.1_

  - [ ] 8.3 Implement `app/modules/organizations/schemas.py`
    - Define Pydantic request/response schemas: `OrganizationCreate`, `OrganizationUpdate`, `OrganizationResponse`
    - Include `contact_name` (optional str, max 128), `contact_email` (optional EmailStr), and `contact_phone` (optional str, max 32) fields in all three schemas
    - Every field must include `Field(description="...")` with description ≥10 characters
    - Include `version` field in `OrganizationUpdate` and `OrganizationResponse` for optimistic locking
    - _Requirements: 2.1, 5.2, 7.2_

  - [ ] 8.4 Implement `app/modules/organizations/service.py`
    - Implement `create_organization`, `update_organization`, `get_organization`, `list_organizations` service functions
    - Enforce slug uniqueness with a pre-write SELECT check; raise `HTTPException(409)` with `{"detail": "slug already in use", "field": "slug"}` on conflict
    - Apply `shard_id = 0` on create
    - _Requirements: 2.1, 2.2, 2.6, 2.7_

  - [ ] 8.5 Implement `app/modules/organizations/router.py`
    - Define REST endpoints: `POST /organizations`, `GET /organizations`, `GET /organizations/{org_id}`, `PATCH /organizations/{org_id}`
    - Prefix with `/api/v1` (applied in `main.py`)
    - Restrict all endpoints to `SuperAdministrator` role via `require_super_admin()` dependency
    - Include full OpenAPI metadata on every route (operation_id, summary ≤80 chars, description ≥20 chars)
    - _Requirements: 2.6, 5.1, 6.4_

  - [ ] 8.6 Implement `app/dependencies.py` — shared dependencies
    - Implement `get_org_scoped_query(model_class, organization_id, db)` returning a SELECT filtered by `organization_id` and `deleted_at IS NULL`
    - Implement `get_current_principal()` dependency (JWT stub — full JWT validation is in the `auth` module; this returns the principal with `organization_id` and `role`)
    - Implement `require_super_admin()` dependency that raises `HTTPException(403)` if role is not SuperAdministrator
    - _Requirements: 2.4, 2.5, 2.6_

  - [ ]* 8.7 Write property test for organization data isolation (Property 5)
    - **Property 5: Organization data isolation**
    - **Validates: Requirements 2.4, 2.5**
    - Use `hypothesis` `st.uuids()` to generate two distinct organization IDs; create records for each; assert `get_org_scoped_query` with org A never returns records belonging to org B

  - [ ]* 8.8 Write property test for duplicate slug rejection (Property 6)
    - **Property 6: Duplicate slug rejection**
    - **Validates: Requirements 2.7**
    - Use `hypothesis` `st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Nd')), min_size=1, max_size=64)` for slugs; create an org with a slug; attempt to create/update another org with the same slug; assert `409` response with slug error message

- [ ] 9. Implement middleware stack
  - [ ] 9.1 Implement `app/middleware/cors.py` — dynamic per-org CORS middleware
    - Implement `DynamicCORSMiddleware(BaseHTTPMiddleware)` with `_extract_org_id(request)` and `_get_allowed_origins(org_id)` (with 60-second LRU cache)
    - Set CORS headers only when origin is in the allowed list; log `WARN` with origin and org ID when blocked
    - Handle preflight `OPTIONS` requests
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 9.2 Write property test for CORS origin enforcement (Property 17)
    - **Property 17: CORS headers present only for allowed origins**
    - **Validates: Requirements 6.2, 6.3**
    - Use `hypothesis` to generate lists of allowed origins and a requesting origin; assert `Access-Control-Allow-Origin` is present iff the origin is in the allowed list

  - [ ] 9.3 Implement `app/middleware/versioning.py` — deprecation header decorator
    - Implement `deprecated(sunset_date: str, replacement_link: str)` decorator that injects `Sunset`, `Deprecation: true`, and `Link` headers into the response
    - _Requirements: 6.5, 6.6_

  - [ ] 9.4 Implement `app/middleware/auth.py` — agent API key guard
    - Implement `require_agent_api_key(request: Request)` FastAPI dependency
    - Reject with `401` if `X-Agent-API-Key` header is missing, empty, or does not match `settings.AGENT_API_KEY`
    - Reject with `401` if `settings.AGENT_API_KEY` is not defined or empty
    - _Requirements: 5.4, 5.5_

  - [ ]* 9.5 Write property test for agent API key enforcement (Property 16)
    - **Property 16: Internal agent endpoints reject requests without API key**
    - **Validates: Requirements 5.4**
    - Use `hypothesis` `st.text()` for API key values; for any key that does not exactly match the configured `AGENT_API_KEY`, assert the response to `/internal/agents/` is `401 Unauthorized`

- [ ] 10. Implement concurrency control (optimistic locking)
  - [ ] 10.1 Verify `VersionMixin` is applied to all mutable entity stubs
    - Create stub ORM model files for all 14 mutable entities listed in Requirements 7.1 that are not yet defined: `Candidate`, `User`, `InterviewJourney`, `InterviewSlot`, `JobRequisition`, `JobPosting`, `JobProfile`, `Questionnaire`, `CandidateQuestionnaireResponse`, `InterviewFeedback`, `InterviewerPreference`, `OrganizationEmailConfig`, `NotificationTemplate`
    - Each stub must inherit `Base`, `AuditMixin`, `VersionMixin` and define at minimum `__tablename__` and primary key
    - _Requirements: 7.1, 7.5_

  - [ ] 10.2 Implement optimistic lock conflict handler in `app/main.py`
    - Register `@app.exception_handler(StaleDataError)` returning `JSONResponse(409)` with `detail`, `hint` fields
    - _Requirements: 7.4_

  - [ ]* 10.3 Write property test for version_id_col configuration (Property 19)
    - **Property 19: All mutable entities have version_id_col configured**
    - **Validates: Requirements 7.1, 7.5**
    - Iterate over all 14 mutable entity mapper objects; assert each has `version_id_col` set to its `version` column

  - [ ]* 10.4 Write property test for optimistic lock increment (Property 20)
    - **Property 20: Optimistic lock increment on matching version**
    - **Validates: Requirements 7.3**
    - Use `hypothesis` `st.integers(min_value=1, max_value=100)` for initial version N; create an entity at version N; submit update with version N; assert entity is persisted at version N+1

  - [ ]* 10.5 Write property test for optimistic lock conflict on mismatch (Property 21)
    - **Property 21: Optimistic lock conflict on mismatched version**
    - **Validates: Requirements 7.4**
    - Use `hypothesis` to generate version N and a mismatched version M (M ≠ N); submit update with version M; assert `409 Conflict` response and entity remains at version N in the database

- [ ] 11. Implement API documentation conventions and OpenAPI validation
  - [ ] 11.1 Implement OpenAPI metadata enforcement helpers
    - Add a startup check (or test utility) that iterates `app.routes` and asserts every `APIRoute` has `operation_id` (snake_case), `summary` (≤80 chars), and `description` (≥20 chars)
    - Add a Pydantic model introspection utility that checks every `FieldInfo` in request/response schemas has `description` ≥10 characters
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 11.2 Write property test for route OpenAPI metadata completeness (Property 14)
    - **Property 14: Every registered route has required OpenAPI metadata**
    - **Validates: Requirements 5.1**
    - Iterate all `APIRoute` objects in the FastAPI app; for each, assert `operation_id` is present and snake_case, `summary` ≤80 chars, `description` ≥20 chars

  - [ ]* 11.3 Write property test for Pydantic field descriptions (Property 15)
    - **Property 15: Every Pydantic request/response field has a description**
    - **Validates: Requirements 5.2**
    - Collect all Pydantic models registered as request bodies or response schemas; for each field, assert `field_info.description` is a string of length ≥10

  - [ ]* 11.4 Write property test for API route versioning prefix (Property 18)
    - **Property 18: All API routes are prefixed with /api/v1/**
    - **Validates: Requirements 6.4**
    - Iterate all `APIRoute` objects excluding `/health`, `/metrics`, `/docs`, `/openapi.json`, `/internal/*`; assert each path starts with `/api/v1/`

- [ ] 12. Wire everything together in `app/main.py`
  - [ ] 12.1 Implement `app/main.py` — FastAPI app factory
    - Create `FastAPI` instance with `title`, `version`, `openapi_url="/openapi.json"`, `docs_url="/docs"`
    - Register middleware in the correct order: `CorrelationIDMiddleware`, `StructuredLoggingMiddleware`, `TracingMiddleware`, `DynamicCORSMiddleware`, `MetricsMiddleware`
    - Register exception handlers: `StaleDataError` → 409, global `Exception` → 500 with correlation ID
    - Include all module routers with `/api/v1` prefix
    - Include observability router (metrics endpoint) without `/api/v1` prefix
    - Implement `GET /health` endpoint with DB connectivity check and version field
    - _Requirements: 1.3, 1.7, 6.4_

  - [ ] 12.2 Register all module routers and internal agent router
    - Include all 18 module routers under `/api/v1`
    - Create `app/modules/agents/router.py` stub with `dependencies=[Depends(require_agent_api_key)]` on the `/internal/agents/` prefix
    - _Requirements: 1.7, 5.4_

- [ ] 13. Checkpoint — full integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Write integration and smoke tests
  - [ ]* 14.1 Write integration tests for health check endpoint
    - Test `GET /health` returns `{"status": "healthy", "version": "..."}` when DB is reachable
    - Test `GET /health` returns `{"status": "unhealthy"}` when DB is unreachable
    - _Requirements: 1.3_

  - [ ]* 14.2 Write integration tests for organization CRUD endpoints
    - Test create, read, update, list operations via HTTP client
    - Test slug uniqueness enforcement returns `409` with correct body
    - Test SuperAdministrator restriction returns `403` for non-super-admin callers
    - _Requirements: 2.6, 2.7_

  - [ ]* 14.3 Write integration tests for domain event retry endpoint
    - Test `POST /internal/domain-events/retry` restricted to SuperAdministrator
    - Test that failed events are re-dispatched and status updated
    - _Requirements: 3.6_

  - [ ]* 14.4 Write smoke tests
    - Verify pgvector extension is available
    - Verify Alembic migrations complete without error
    - Verify all required event type constants are defined in `handlers.py`
    - Verify `version_id_col` is configured on all 14 mutable mappers
    - Verify `GET /health` returns `{"status": "healthy"}` against the live database
    - _Requirements: 1.3, 1.4, 3.7, 7.1, 7.5_

- [ ] 15. Final checkpoint — all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with `max_examples=100` and the tag format `# Feature: platform-foundation, Property N: <property_text>`
- Checkpoints at tasks 6, 13, and 15 ensure incremental validation
- Stub ORM models in task 10.1 are intentionally minimal; full implementations belong to their respective feature modules
- The `VersionMixin.__mapper_args__` uses `declared_attr` to ensure the correct table column is referenced per subclass

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "3.1", "3.2"] },
    { "id": 2, "tasks": ["2.2", "3.3", "3.4", "3.5", "4"] },
    { "id": 3, "tasks": ["5.1", "5.2", "5.3", "5.4", "7.1", "8.1", "8.2"] },
    { "id": 4, "tasks": ["5.5", "5.7", "7.2", "8.3", "8.6"] },
    { "id": 5, "tasks": ["5.6", "5.8", "5.9", "7.3", "8.4", "9.3", "9.4", "10.1"] },
    { "id": 6, "tasks": ["7.4", "7.5", "7.6", "7.7", "8.5", "8.7", "8.8", "9.1", "9.5", "10.2"] },
    { "id": 7, "tasks": ["9.2", "10.3", "10.4", "10.5", "11.1"] },
    { "id": 8, "tasks": ["11.2", "11.3", "11.4", "12.1"] },
    { "id": 9, "tasks": ["12.2"] },
    { "id": 10, "tasks": ["14.1", "14.2", "14.3", "14.4"] }
  ]
}
```
