# Project Structure & Organization

## Directory Layout

```
talentkru-server/
├── .kiro/                          # Kiro configuration
│   ├── specs/                      # Feature specifications
│   │   ├── candidate-lifecycle/
│   │   ├── identity-and-access/
│   │   ├── platform-foundation/
│   │   └── ...
│   └── steering/                   # Steering documents (this folder)
│
├── app/                            # Main application code
│   ├── __init__.py
│   ├── main.py                     # FastAPI app initialization, lifespan, routes
│   ├── config.py                   # Settings/environment configuration
│   ├── database.py                 # Database connection and session management
│   ├── dependencies.py             # FastAPI dependency injection
│   ├── base_model.py               # Base SQLAlchemy model
│   ├── crypto.py                   # Encryption/decryption utilities
│   ├── email_service.py            # Email sending service
│   ├── audit.py                    # Audit logging
│   ├── audit_models.py             # Audit log models
│   ├── shard_router.py             # Multi-tenancy routing
│   ├── openapi_utils.py            # OpenAPI documentation utilities
│   │
│   ├── modules/                    # Feature modules (each is a vertical slice)
│   │   ├── auth/                   # Authentication & JWT
│   │   │   ├── models.py           # SQLAlchemy models
│   │   │   ├── schemas.py          # Pydantic request/response schemas
│   │   │   ├── service.py          # Business logic
│   │   │   ├── router.py           # FastAPI routes
│   │   │   ├── dependencies.py     # Auth-specific dependencies
│   │   │   └── __init__.py
│   │   │
│   │   ├── users/                  # User management
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── organizations/          # Organization management
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── candidates/             # Candidate lifecycle
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── resumes/                # Resume ingestion & storage
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── storage.py          # S3/local storage abstraction
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── skills/                 # Skill extraction & matching
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── requisitions/           # Job requisitions
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── job_posting/            # Job postings
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── job_profile/            # Job profiles
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── matching/               # AI-powered candidate matching
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── journeys/               # Candidate interview journeys
│   │   │   ├── models.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── interviews/             # Interview management
│   │   │   ├── models.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── questionnaires/         # Interview questionnaires
│   │   │   ├── models.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── invitations/            # User invitations
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── password_reset/         # Password reset flow
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── rbac/                   # Role-based access control
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── privacy/                # Privacy & data retention
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── portal/                 # Candidate portal
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── reporting/              # Analytics & reporting
│   │   │   ├── models.py
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── agents/                 # Internal agent API
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   └── observability/          # Metrics & health endpoints
│   │       ├── router.py
│   │       └── __init__.py
│   │
│   ├── middleware/                 # Request middleware
│   │   ├── cors.py                 # Dynamic CORS per organization
│   │   ├── rate_limit.py           # Rate limiting
│   │   ├── auth_extraction.py      # JWT extraction & org context
│   │   └── __init__.py
│   │
│   ├── observability/              # Logging, metrics, tracing
│   │   ├── logging.py              # Structured logging setup
│   │   ├── middleware.py           # Correlation ID middleware
│   │   ├── tracing.py              # OpenTelemetry instrumentation
│   │   └── __init__.py
│   │
│   ├── domain_events/              # Event-driven architecture
│   │   ├── models.py               # DomainEvent model
│   │   ├── dispatcher.py           # Event dispatching
│   │   ├── retry.py                # Failed event retry logic
│   │   └── __init__.py
│   │
│   └── __init__.py
│
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures and configuration
│   ├── integration_fixtures.py     # Shared integration test fixtures
│   │
│   ├── test_auth_service.py        # Auth module tests
│   ├── test_auth_properties.py     # Property-based auth tests
│   ├── test_auth_router.py         # Auth router tests
│   │
│   ├── test_candidate_service.py   # Candidate service tests
│   ├── test_candidate_lifecycle_integration.py
│   ├── test_candidate_minimal.py
│   │
│   ├── test_resume_ingestion_service.py
│   ├── test_resume_models.py
│   │
│   ├── test_skills_service.py
│   ├── test_skill_matching_integration.py
│   │
│   ├── test_user_service.py
│   ├── test_organizations.py
│   │
│   ├── test_invitation_service.py
│   ├── test_password_reset_service.py
│   │
│   ├── test_rbac_service.py
│   ├── test_middleware_auth.py
│   │
│   ├── test_privacy_service.py
│   ├── test_dsar_integration.py
│   ├── test_portal_dsar.py
│   │
│   ├── test_job_posting_service.py
│   ├── test_job_posting_integration.py
│   │
│   ├── test_requisition_integration.py
│   ├── test_scheduler_integration.py
│   │
│   ├── test_domain_events_retry.py
│   ├── test_audit_log.py
│   │
│   ├── test_rate_limiting.py
│   ├── test_rate_limit_middleware.py
│   │
│   ├── test_health.py
│   ├── test_smoke.py
│   ├── test_smoke_candidate_lifecycle.py
│   │
│   ├── test_crypto.py
│   ├── test_dependencies.py
│   ├── test_impersonate.py
│   ├── test_impersonate_router.py
│   ├── test_login_router.py
│   │
│   └── __pycache__/
│
├── alembic/                        # Database migrations
│   ├── versions/                   # Migration files (auto-generated)
│   ├── env.py                      # Alembic environment configuration
│   ├── script.py.mako              # Migration template
│   └── __pycache__/
│
├── db-scripts/                     # SQL scripts
│   ├── create_user.sql             # Initial user/schema creation
│   └── create_kru_test_db.sql      # Test database creation
│
├── docs/                           # Documentation
│   └── Identity_and_access_guide.md
│
├── scripts/                        # Shell scripts
│   ├── start-postgres.sh
│   ├── stop-postgres.sh
│   └── remove-postgres.sh
│
├── data/                           # Local data storage
│   └── resumes/                    # Resume files (local storage backend)
│
├── ai_docs/                        # AI-generated documentation
│   ├── MIGRATION_GUIDE.md
│   ├── TASK_*.md
│   └── ...
│
├── specs/                          # Legacy spec documents
│   └── Kru-server-spec.md
│
├── .hypothesis/                    # Hypothesis test data cache
├── .pytest_cache/                  # Pytest cache
├── .venv/                          # Python virtual environment
├── __pycache__/                    # Python cache
│
├── .env                            # Environment variables (local, not committed)
├── .env.example                    # Environment template (committed)
├── .gitignore                      # Git ignore rules
├── .python-version                 # Python version (pyenv)
│
├── pyproject.toml                  # Poetry configuration & dependencies
├── poetry.lock                     # Locked dependency versions
├── alembic.ini                     # Alembic configuration
├── docker-compose.yml              # Docker Compose setup
├── Dockerfile                      # Docker image definition
├── entrypoint.sh                   # Docker entrypoint script
│
├── tasks.py                        # Invoke task definitions
├── README.md                       # Project README
├── setup.md                        # Setup guide
├── DOCUMENTATION_INDEX.md          # Documentation index
│
└── WAVE_*.md                       # Implementation wave summaries
```

## Module Architecture Pattern

Each feature module follows a consistent vertical slice pattern:

### Module Structure
```
app/modules/feature_name/
├── __init__.py
├── models.py           # SQLAlchemy ORM models
├── schemas.py          # Pydantic request/response schemas
├── service.py          # Business logic (async methods)
├── router.py           # FastAPI routes
├── dependencies.py     # (optional) Feature-specific dependencies
└── storage.py          # (optional) External storage abstraction
```

### Responsibilities

- **models.py**: Database schema definitions using SQLAlchemy
  - Inherits from `app.base_model.Base`
  - Includes relationships, indexes, and constraints
  - May include encrypted fields for PII

- **schemas.py**: Request/response validation using Pydantic
  - Request schemas for POST/PUT operations
  - Response schemas for GET operations
  - Nested schemas for complex data structures

- **service.py**: Business logic and data operations
  - Async methods for all I/O operations
  - Database queries and mutations
  - Integration with other services
  - Event publishing for domain events

- **router.py**: FastAPI route handlers
  - Endpoint definitions with path, method, tags
  - Request/response documentation
  - Dependency injection for auth, validation
  - Delegates to service layer

- **dependencies.py**: (optional) Feature-specific FastAPI dependencies
  - Custom validators
  - Permission checks
  - Resource loading

- **storage.py**: (optional) External storage abstraction
  - S3/local file storage interface
  - Upload/download operations
  - Used by resumes module

## Cross-Cutting Concerns

### Middleware Stack (in app/middleware/)
- **CorrelationIDMiddleware**: Generates X-Correlation-ID for request tracing
- **AuthExtractionMiddleware**: Extracts JWT and org context
- **RateLimitMiddleware**: Enforces per-org rate limits
- **DynamicCORSMiddleware**: Per-organization CORS policies

### Observability (in app/observability/)
- **logging.py**: Structured logging with structlog
- **middleware.py**: Correlation ID tracking
- **tracing.py**: OpenTelemetry auto-instrumentation

### Domain Events (in app/domain_events/)
- **models.py**: DomainEvent SQLAlchemy model
- **dispatcher.py**: Event publishing and dispatching
- **retry.py**: Retry logic for failed events

## Testing Organization

Tests mirror the module structure:
- `test_<module>_service.py`: Service layer unit tests
- `test_<module>_router.py`: Route handler tests
- `test_<module>_integration.py`: End-to-end integration tests
- `test_<module>_properties.py`: Property-based tests (Hypothesis)

### Test Fixtures (conftest.py)
- Database session fixtures
- Authenticated user fixtures
- Organization fixtures
- Mock external service fixtures

## Database Organization

### Migrations (alembic/versions/)
- Auto-generated by Alembic from model changes
- Numbered sequentially (001, 002, etc.)
- Include both upgrade and downgrade paths

### Schemas
- **public**: Default PostgreSQL schema
- **talentkru**: Main application schema (created in create_user.sql)
- **talentkru_test**: Test database schema

## Configuration & Environment

### Settings (app/config.py)
- Pydantic Settings for environment variable loading
- Validation of required variables
- Type-safe configuration access

### Environment Files
- `.env.example`: Template with all required variables
- `.env`: Local development (not committed)
- Docker Compose: Production-like environment

## API Organization

### Route Prefixes
- `/api/v1/`: Main API routes (all feature modules)
- `/internal/`: Internal agent API (no version prefix)
- `/metrics`: Prometheus metrics endpoint
- `/health`: Health check endpoint
- `/docs`: Swagger UI documentation
- `/redoc`: ReDoc documentation

### Response Format
- Success: `{ "data": {...}, "meta": {...} }`
- Error: `{ "detail": "...", "correlation_id": "..." }`
- Pagination: `{ "data": [...], "meta": { "total": N, "page": N } }`

## Key Architectural Patterns

### Multi-Tenancy
- Organization-based isolation via `org_id` in JWT
- Middleware extracts org context for all requests
- Queries filtered by org_id automatically

### Async/Await
- All I/O operations use async patterns
- Database queries via SQLAlchemy async
- HTTP calls via httpx async client

### Event-Driven
- Domain events published for audit trails
- Async event dispatcher
- Retry mechanism for failed events

### Dependency Injection
- FastAPI Depends() for route dependencies
- Service layer injected into routes
- Database session injected via get_db_session()

### Error Handling
- Custom exception handlers in main.py
- StaleDataError → HTTP 409 (optimistic lock conflict)
- Global exception handler → HTTP 500 with correlation ID

## Development Workflow

### Adding a New Feature
1. Create module directory: `app/modules/feature_name/`
2. Define models in `models.py`
3. Define schemas in `schemas.py`
4. Implement service in `service.py`
5. Create routes in `router.py`
6. Register router in `app/main.py`
7. Create migration: `poetry run invoke db-revision --message "Add feature"`
8. Write tests in `tests/test_feature_*.py`

### Modifying Existing Models
1. Update model in `app/modules/*/models.py`
2. Create migration: `poetry run invoke db-revision --message "..."`
3. Review generated migration in `alembic/versions/`
4. Apply migration: `poetry run invoke migrate`
5. Update tests if schema changed

### Adding Tests
1. Create test file: `tests/test_module_*.py`
2. Use fixtures from `conftest.py`
3. Run tests: `poetry run invoke test`
4. Check coverage: `poetry run invoke test-cov`
