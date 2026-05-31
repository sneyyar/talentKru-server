# Tech Stack & Build System

**Last Updated:** May 31, 2026

## Overview

This document covers the technology stack, build system, dependency management, and Python execution standards for TalentKru.ai.

## Technology Stack

### Backend Framework
- **FastAPI** (0.115.5): Modern async Python web framework with automatic OpenAPI documentation
- **Uvicorn** (0.34.2): ASGI server for running FastAPI applications
- **Python** (3.12+): Required version, managed with pyenv

### Database & ORM
- **PostgreSQL** (pgvector/pgvector:pg17): Primary database with vector extension for semantic search
- **SQLAlchemy** (2.0.40): Async ORM with asyncpg driver
- **Alembic** (1.18.4): Database migration tool
- **asyncpg** (0.31.0): Async PostgreSQL driver

### Data Validation & Serialization
- **Pydantic** (2.7.0): Data validation and settings management
- **Pydantic Settings** (2.6.1): Environment configuration management

### Security & Cryptography
- **PyJWT** (2.8.0): JWT token generation and validation
- **bcrypt** (4.1.0): Password hashing
- **cryptography** (43.0.0): Field-level encryption for PII

### Observability
- **structlog** (24.4.0): Structured logging
- **prometheus-client** (0.21.1): Metrics collection
- **OpenTelemetry SDK** (1.41.0): Distributed tracing
- **OpenTelemetry FastAPI Instrumentation** (0.62b0): Auto-instrumentation

### Cloud & Storage
- **boto3** (1.42.25): AWS SDK for S3 storage backend

### Development & Testing
- **pytest** (8.3.4): Test framework
- **pytest-asyncio** (0.24.0): Async test support
- **hypothesis** (6.119.3): Property-based testing
- **httpx** (0.28.0): Async HTTP client for testing
- **pytest-cov** (6.0.0): Coverage reporting
- **pytest-watch** (4.2.0): Test watcher for development
- **ruff** (0.5.0): Fast Python linter and formatter
- **mypy** (1.11.0): Static type checker
- **invoke** (3.0.3+): Task runner for development automation

### Utilities
- **python-dotenv** (1.0.0): Environment variable loading
- **greenlet** (3.5.1+): Lightweight concurrency for SQLAlchemy async
- **python-multipart** (0.0.29): Multipart form data parsing

## Dependency Management

### Package Manager
- **uv** (latest): Fast, Rust-based Python package manager
  - Lock file: `uv.lock` (committed to repo)
  - Config: `pyproject.toml`
  - Install: `pip install uv` or `brew install uv` (macOS)
  - **Never use pip directly** — always use `uv` for package operations

### Python Version Manager
- **pyenv**: Manages Python versions per project
  - Project version: Python 3.12.x (defined in `.python-version`)
  - Install: `brew install pyenv` (macOS)

### Task Runner
- **Invoke**: Automation for common development tasks
  - Config: `tasks.py`
  - Usage: `uv run invoke <task-name>`

## Build & Development Commands

### Installation
```zsh
# Install all dependencies (including dev)
uv sync

# Install only production dependencies
uv sync --no-dev

# Add a new dependency
uv add package_name

# Add a dev dependency
uv add --dev package_name

# Update all dependencies
uv lock --upgrade
```

### Running the Application
```zsh
# Development server with auto-reload (recommended)
uv run invoke dev

# Development server on custom port
uv run invoke dev --port 8001

# Production server (no auto-reload)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Interactive Python REPL
uv run python
```

### Testing
```zsh
# Run all tests
uv run invoke test

# Run tests with coverage report
uv run invoke test-cov

# Run tests in watch mode (re-runs on file changes)
uv run invoke test-watch

# Run specific test file
uv run invoke test --path tests/test_auth_service.py

# Run specific test function
uv run invoke test --path tests/test_auth_service.py::test_login
```

### Code Quality
```zsh
# Check code style with ruff
uv run invoke lint

# Auto-format code with ruff
uv run invoke format

# Check if code is properly formatted
uv run invoke format-check

# Run type checking with mypy
uv run invoke type-check

# Run all checks (lint, format-check, test)
uv run invoke check

# Run mypy directly
uv run mypy app

# Run ruff directly
uv run ruff check app tests
```

### Database Management
```zsh
# Apply all pending migrations
uv run invoke migrate

# Rollback last migration
uv run invoke migrate-down

# Show current migration status
uv run invoke db-status

# Test database connection
uv run invoke db-check

# Create new migration
uv run invoke db-revision --message "Add new_column to users"

# Initialize database users and schemas
uv run invoke db-init-users

# Run alembic directly
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic current
```

### Docker & PostgreSQL
```zsh
# Start PostgreSQL container
uv run invoke db-start

# Stop PostgreSQL container
uv run invoke db-stop

# Remove PostgreSQL container and volume
uv run invoke db-remove

# Start pgAdmin4 web UI
uv run invoke db-admin-start

# Stop pgAdmin4
uv run invoke db-admin-stop
```

### Utility Tasks
```zsh
# Clean up Python cache files
uv run invoke clean

# Show all installed dependencies
uv run invoke show-deps

# Complete setup (install, start DB, migrate)
uv run invoke setup

# Quick dev setup (start DB, migrate)
uv run invoke dev-setup
```

## Environment Configuration

### Required Environment Variables
See `.env.example` for template. Key variables:

```zsh
# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=talentkru
DATABASE_USER=talentkru
DATABASE_PASSWORD=<secure_password>

# Security (min 32 characters)
JWT_SIGNING_KEY=<32_char_minimum>
ENCRYPTION_KEY=<32_char_minimum>
AGENT_API_KEY=<32_char_minimum>

# Storage
STORAGE_BACKEND=local|s3
STORAGE_LOCAL_PATH=/data/resumes

# Metrics
METRICS_USERNAME=metrics
METRICS_PASSWORD=<secure_password>

# Docker PostgreSQL
PG_CONTAINER_NAME=local-postgresql-db
PG_IMAGE=pgvector/pgvector:pg17
PG_ADMIN_PASSWORD=<secure_password>
```

## Project Structure

```
talentkru-server/
├── app/                    # Main application code
│   ├── main.py            # FastAPI app initialization
│   ├── config.py          # Settings management
│   ├── database.py        # Database connection
│   ├── modules/           # Feature modules
│   ├── middleware/        # Request middleware
│   ├── observability/     # Logging, metrics, tracing
│   └── domain_events/     # Event system
├── tests/                 # Test suite
├── alembic/              # Database migrations
├── db-scripts/           # SQL scripts
├── docs/                 # Documentation
├── scripts/              # Shell scripts
├── pyproject.toml        # Poetry configuration
├── tasks.py              # Invoke tasks
├── alembic.ini           # Alembic configuration
├── docker-compose.yml    # Docker Compose setup
└── .env.example          # Environment template
```

## Enum-Based Columns Pattern

### Overview

When creating features with enumerated values (status fields, types, designations, etc.), use a simple, database-agnostic approach:

1. **Define enum in Python** with UPPERCASE names and values
2. **Store as VARCHAR in database** (no PostgreSQL enum types)
3. **Add check constraints** for database-level validation
4. **Pass `.value` property** when creating model instances

### Why This Approach?

- **No type registry caching issues** - Avoids SQLAlchemy enum type conflicts
- **Database portability** - Works across all databases (PostgreSQL, MySQL, SQLite, etc.)
- **Simple and explicit** - Easy to understand and maintain
- **Type-safe in Python** - Full IDE support and type checking
- **Database validation** - Check constraints ensure data integrity

### Implementation Pattern

#### 1. Define Enum (Python)

```python
import enum

class MyStatus(str, enum.Enum):
    """Status enumeration."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"
```

#### 2. Model Column (SQLAlchemy)

```python
from sqlalchemy import Column, String, CheckConstraint

class MyEntity(Base, AuditMixin):
    __tablename__ = "my_entities"
    
    status = Column(
        String(20),
        nullable=False,
        default=MyStatus.ACTIVE.value,
    )  # type: ignore[var-annotated]
    
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'PENDING')",
            name="ck_my_entities_status",
        ),
    )
```

#### 3. Migration (Alembic)

```python
def upgrade() -> None:
    op.create_table(
        'my_entities',
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
        # ... other columns ...
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'PENDING')",
            name='ck_my_entities_status',
        ),
    )
```

#### 4. Service Layer Usage

```python
class MyService:
    async def create_entity(self, ...):
        entity = MyEntity(
            status=MyStatus.ACTIVE.value,  # Pass .value property
            # ... other fields ...
        )
        self.db.add(entity)
        await self.db.flush()
        return entity
```

### Enum Naming Convention

- **Enum class name**: PascalCase (e.g., `GlobalStatus`, `ParseStatus`)
- **Enum member names**: UPPERCASE (e.g., `ACTIVE`, `PENDING`, `COMPLETED`)
- **Enum values**: UPPERCASE (e.g., `"ACTIVE"`, `"PENDING"`, `"COMPLETED"`)
- **Column type**: Always `String(20)` (adjust length as needed)
- **Check constraint name**: `ck_<table>_<column>` (e.g., `ck_candidates_global_status`)

### Common Enums in TalentKru

| Enum | Values | Table | Column |
|------|--------|-------|--------|
| GlobalStatus | ACTIVE, INTERVIEWING, EXPIRED, INELIGIBLE, DELETED | candidates | global_status |
| ParseStatus | PENDING, COMPLETED, FAILED | resumes | parse_status |
| UserStatus | ACTIVE, INACTIVE, LOCKED, PENDING_INVITATION | users | status |
| SkillDesignation | REQUIRED, DESIRED | job_profile_skills | designation |
| RequisitionStatus | OPEN, ON_HOLD, CLOSED, CANCELLED | job_requisitions | status |
| DSARRequestType | ACCESS, ERASURE | data_subject_access_requests | request_type |
| DSARStatus | PENDING, PROCESSING, COMPLETED, DENIED | data_subject_access_requests | status |
| EventStatus | PENDING, PROCESSED, FAILED | domain_events | status |
| SkillSource | MANUAL, PARSED, INFERRED | candidate_skills | source |
| JourneyOverallStatus | ACTIVE, ON_HOLD, COMPLETED, CANCELLED | interview_journeys | overall_status |

## Code Style & Standards

### Formatting
- **Line length**: 100 characters (configured in `pyproject.toml`)
- **Formatter**: Ruff (auto-format with `poetry run invoke format`)
- **Linter**: Ruff (check with `poetry run invoke lint`)

### Linting Rules (Ruff)
- **E**: PEP 8 errors
- **F**: PyFlakes (undefined names, unused imports)
- **I**: isort (import sorting)
- **UP**: pyupgrade (modern Python syntax)
- **Ignored**: E501 (line too long—handled by formatter)

### Type Checking
- **Tool**: mypy
- **Target**: Python 3.12
- **Run**: `poetry run invoke type-check`

### Testing Standards
- **Framework**: pytest with async support
- **Property-based testing**: Hypothesis
- **Coverage**: Aim for >80% coverage
- **Async tests**: Use `pytest-asyncio` with `asyncio_mode = "auto"`

## Docker Setup

### PostgreSQL Container
- **Image**: pgvector/pgvector:pg17 (includes vector extension)
- **Port**: 5432 (default, configurable)
- **Volume**: Named volume for data persistence
- **Admin user**: postgres
- **Database**: krudb (configurable)

### pgAdmin4 Container
- **Image**: dpage/pgadmin4
- **Port**: 8080 (default, configurable)
- **Access**: http://localhost:8080

### Docker Compose
- **File**: `docker-compose.yml`
- **Services**: PostgreSQL + pgAdmin4
- **Usage**: `docker-compose up` (starts both services)

## Common Development Workflows

### First-Time Setup
```zsh
# 1. Sync dependencies
uv run invoke sync

# 2. Start database
uv run invoke db-start

# 3. Initialize database users
uv run invoke db-init-users

# 4. Apply migrations
uv run invoke migrate

# 5. Start dev server
uv run invoke dev
```

### Daily Development
```zsh
# Terminal 1: Start dev server
uv run invoke dev

# Terminal 2: Run tests in watch mode
uv run invoke test-watch

# Terminal 3: Check code quality
uv run invoke lint
```

### Before Committing
```zsh
# Format code
uv run invoke format

# Run all checks
uv run invoke check

# Run full test suite
uv run invoke test-cov
```

### Adding Dependencies
```zsh
# Add a production dependency
uv run invoke add --package requests

# Add a dev dependency
uv run invoke add-dev --package pytest-xdist

# Upgrade all dependencies
uv run invoke lock-upgrade

# Refresh lock file
uv run invoke lock-refresh
```

## Troubleshooting

### Database Connection Issues
```zsh
# Test connection
uv run invoke db-check

# Check container status
docker ps

# View container logs
docker logs local-postgresql-db
```

### Python Version Issues
```zsh
# Verify correct Python version
uv run python --version  # Should show 3.12.x

# Reset pyenv
pyenv local 3.12.0
exec $SHELL
```

### Dependency Conflicts
```zsh
# Clear uv cache
uv run invoke cache-clean

# Reinstall dependencies
uv run invoke sync --refresh
```

### Running Python Scripts
```zsh
# Execute a Python script
uv run script_name.py

# Execute with arguments
uv run script_name.py --arg value

# Run Python interactively
uv run python

# Run pytest directly
uv run pytest

# Run pytest with specific file
uv run pytest tests/test_auth_service.py

# Run pytest with coverage
uv run pytest --cov=app --cov-report=html
```

## Performance Considerations

- **Async/await**: All I/O operations use async patterns
- **Connection pooling**: SQLAlchemy manages async connection pool
- **Batch operations**: Use bulk inserts for large datasets
- **Indexing**: Database indexes on frequently queried columns
- **Caching**: RevocationCache warmed on startup for JWT validation

## Python Execution Standards

**All Python executions must be prepended with `uv run`** to ensure consistent environment management, correct Python version (3.12.x), and proper dependency isolation.

### Common Python Operations

```zsh
# Scripts
uv run script_name.py
uv run script_name.py --arg value

# Testing
uv run pytest
uv run pytest tests/test_auth_service.py
uv run pytest --cov=app --cov-report=html

# Code Quality
uv run mypy app
uv run ruff check app tests
uv run ruff format app tests

# Database
uv run alembic upgrade head
uv run alembic downgrade -1

# Interactive REPL
uv run python
uv run ipython
```

### Why `uv run`?

1. **Environment Isolation**: Correct Python version and dependencies
2. **Consistency**: All developers use identical environments
3. **Reproducibility**: Lock file guarantees exact versions
4. **Safety**: Prevents accidental use of system Python
5. **Simplicity**: No manual virtual environment activation needed
