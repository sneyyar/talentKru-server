# Requirements Document

## Introduction

This is the Platform Foundation module of TalentKru.ai Server, covering project configuration, multi-tenancy, domain events, observability, API documentation, CORS/versioning, and concurrency control. These requirements establish the cross-cutting infrastructure that all other modules depend on.

Key architectural decisions relevant to this module:
- PostgreSQL with pgvector extension for data persistence and semantic search.
- Docker Compose as the deployment target.
- Horizontal sharding modeled at the organization level with a default shard 0 placeholder.
- Soft delete only for data retention; interview artifacts attached to InterviewJourney with an encrypted join table for hired candidates.

## Glossary

- **Server**: The TalentKru.ai FastAPI backend application.
- **Organization**: A client tenant in the system; all data is scoped to an organization.
- **Shard**: A database partition; organizations include a shard_id for future horizontal scaling.
- **AuditFields**: Standard fields on all entities: CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy.
- **JWT_SIGNING_KEY**: The secret key used exclusively for HMAC-SHA256 signing and verification of JSON Web Tokens.
- **ENCRYPTION_KEY**: The secret key used exclusively for field-level encryption of PII data at rest.
- **DomainEvent**: A record representing a significant occurrence within the system, published to the internal event bus for cross-cutting concerns.

## Requirements

### Requirement 1: Project Foundation and Configuration

**User Story:** As a developer, I want a well-structured FastAPI project with environment-based configuration, so that the application is portable and follows 12-factor principles.

#### Acceptance Criteria

1. THE Server SHALL use a `.env` file for all environment-specific configuration including STORAGE_BACKEND (local or s3), STORAGE_LOCAL_PATH (filesystem directory for local storage), RESUME_BUCKET_NAME (S3 bucket for cloud storage), JWT_SIGNING_KEY, ENCRYPTION_KEY, PORTAL_TOKEN_TTL_DAYS, AI model identifiers, INTERVIEW_LEADERBOARD_DEFAULT_PERIOD_DAYS, DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, AGENT_API_KEY, METRICS_USERNAME, and METRICS_PASSWORD.
2. IF any required environment variable (JWT_SIGNING_KEY, ENCRYPTION_KEY, STORAGE_BACKEND, DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, AGENT_API_KEY, METRICS_USERNAME, or METRICS_PASSWORD) is missing or empty at startup, THEN THE Server SHALL fail to start and log an error message indicating which variable is missing.
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

### Requirement 3: Domain Event Infrastructure

**User Story:** As a platform developer, I want a cross-cutting domain event system, so that modules can publish and consume events for audit, notification, and workflow orchestration without tight coupling.

#### Acceptance Criteria

1. THE Server SHALL publish domain events to an internal event bus implemented using FastAPI BackgroundTasks for immediate processing and a persistent event log table (DomainEvent) for audit and retry purposes.
2. THE Server SHALL store DomainEvent entities with fields: EventID (UUID), EventType (string), Payload (JSON), PublishedAt (timestamp), ProcessedAt (nullable timestamp), and Status (Pending, Processed, Failed).
3. WHEN a domain event is published, THE Server SHALL persist the event with Status set to Pending and dispatch it to registered handlers via FastAPI BackgroundTasks.
4. WHEN a domain event handler completes successfully, THE Server SHALL update the DomainEvent Status to Processed and set ProcessedAt to the current UTC timestamp.
5. IF a domain event handler fails, THEN THE Server SHALL update the DomainEvent Status to Failed, log the error with the EventID and correlation ID, and retain the event for manual retry or automated retry via a scheduled background task.
6. THE Server SHALL expose an internal endpoint for retrying failed domain events, restricted to the SuperAdministrator role.
7. THE Server SHALL support the following event types at minimum: journey_stage_changed, questionnaire_submitted, interview_slot_created, offer_accepted, candidate_created, candidate_status_changed, role_assignment_changed, and requisition_status_changed.

### Requirement 4: Observability

**User Story:** As a platform operator, I want structured logging, metrics, and tracing, so that I can monitor system health and debug issues efficiently.

#### Acceptance Criteria

1. THE Server SHALL emit structured JSON logs with a correlation ID, timestamp, log level, module name, and event description for the following workflows: authentication attempts, candidate creation and status changes, resume uploads and ingestion results, matching invocations, interview scheduling and status updates, questionnaire submissions, AI agent invocations and completions, and portal access events.
2. THE Server SHALL expose a metrics endpoint in Prometheus-compatible format tracking: resumes parsed (counter), match computation duration in milliseconds (histogram), match counts per requisition (counter), questionnaire completion events (counter), AI agent error rates per agent name (counter), interview volume by stage, type, and organization (gauge), and no-show rates per organization (gauge).
3. THE Server SHALL restrict access to the metrics endpoint (GET /metrics) using HTTP Basic Authentication with credentials validated against METRICS_USERNAME and METRICS_PASSWORD environment variables.
4. THE Server SHALL propagate correlation IDs from the originating HTTP request through background tasks and AI agent invocations, and integrate distributed tracing spans across AI agent calls, storage backend operations, and database query execution.
5. WHEN an AI agent call fails, THE Server SHALL log the failure at ERROR level with the correlation ID, agent name, input payload size, resume or requisition identifier if applicable, error type, and error description.
6. WHEN a background task is enqueued, THE Server SHALL include the originating request's correlation ID in the task context so that all log entries and trace spans produced by the task are linked to the original request.

### Requirement 5: API Documentation and AI Agent Compatibility

**User Story:** As a developer integrating AI agents, I want all API endpoints to be fully documented with OpenAPI metadata, so that agents can dynamically discover and use the API.

#### Acceptance Criteria

1. THE Server SHALL include operation_id (snake_case), summary (maximum 80 characters), and description (minimum 20 characters) on every FastAPI route decorator.
2. THE Server SHALL include Field(description="...") with a minimum length of 10 characters on every Pydantic model field used in request or response schemas.
3. THE Server SHALL generate a valid OpenAPI 3.1 specification accessible at the /docs and /openapi.json endpoints, containing entries for every registered route.
4. IF a request targets an internal agent endpoint (any route under the /internal/agents/ path prefix) without a valid X-Agent-API-Key header, THEN THE Server SHALL return a 401 Unauthorized response.
5. THE Server SHALL load the expected agent API key value from an environment variable defined in the .env configuration file.

### Requirement 6: CORS and API Versioning

**User Story:** As a platform developer, I want configurable CORS policies and versioned API endpoints, so that the candidate portal can safely call the API from browser contexts and clients can migrate between API versions gracefully.

#### Acceptance Criteria

1. THE Server SHALL support configurable CORS allowed origins per organization, stored in the Organization entity as a list of origin URLs (maximum 20 origins per organization, each maximum 253 characters).
2. WHEN a preflight or actual CORS request arrives, THE Server SHALL resolve the requesting origin against the target organization's allowed origins list and include appropriate Access-Control-Allow-Origin, Access-Control-Allow-Methods, Access-Control-Allow-Headers, and Access-Control-Allow-Credentials headers in the response.
3. IF a CORS request originates from an origin not in the organization's allowed origins list, THEN THE Server SHALL omit CORS headers from the response, causing the browser to block the request.
4. THE Server SHALL prefix all API routes with /api/v1/ to establish a versioned URL namespace.
5. THE Server SHALL include a Sunset header with an ISO 8601 date on any endpoint that has been marked for deprecation, indicating the date after which the endpoint will be removed.
6. THE Server SHALL include a Deprecation header with value "true" on deprecated endpoints, along with a Link header pointing to the replacement endpoint documentation.

### Requirement 7: Concurrency Control

**User Story:** As a developer, I want optimistic locking on mutable entities, so that concurrent updates do not silently overwrite each other and data integrity is preserved.

#### Acceptance Criteria

1. THE Server SHALL include a Version column (integer, starting at 1) on all mutable entities: Candidate, User, InterviewJourney, InterviewSlot, JobRequisition, JobPosting, JobProfile, Questionnaire, CandidateQuestionnaireResponse, InterviewFeedback, InterviewerPreference, Organization, OrganizationEmailConfig, and NotificationTemplate.
2. WHEN a client submits an update request, THE Server SHALL require the current Version value in the request payload (via an If-Match header or a version field in the request body).
3. WHEN processing an update, THE Server SHALL compare the submitted Version against the stored Version; IF the versions match, THE Server SHALL increment the Version by 1 and persist the update.
4. IF the submitted Version does not match the stored Version, THEN THE Server SHALL reject the update with a 409 Conflict response containing an error message indicating the resource has been modified by another request, the current Version value, and a recommendation to re-fetch and retry.
5. THE Server SHALL implement optimistic locking at the ORM level using SQLAlchemy's version_id_col feature to ensure atomicity of the version check and increment within a single database transaction.
