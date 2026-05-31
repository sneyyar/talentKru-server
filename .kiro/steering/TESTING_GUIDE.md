# Testing Guide

**Last Updated:** May 31, 2026

## Overview

TalentKru.ai uses **PostgreSQL** for all database and integration tests, not SQLite. Tests connect to a dedicated test database using environment variables defined in `.env`, ensuring consistency with production database behavior and supporting advanced features like pgvector for semantic search.

## Test Database Configuration

### Environment Variables

Tests use the following environment variables from `.env` for database connectivity:

```zsh
# Test database connection
TEST_DATABASE_HOST=localhost
TEST_DATABASE_PORT=5432
TEST_DATABASE_NAME=kru_test_db
TEST_DATABASE_USER=kru_test
TEST_DATABASE_PASSWORD=kruTest2026
```

These variables are **separate** from production database variables (`DATABASE_*`), allowing you to run tests without affecting production data.

### Why PostgreSQL for Tests?

1. **Feature Parity**: Tests run against the same database engine as production
2. **pgvector Support**: Semantic search and vector operations work identically
3. **Advanced Features**: Constraints, triggers, and extensions behave as in production
4. **Data Integrity**: Foreign keys and complex relationships are validated
5. **Performance**: Realistic performance characteristics for benchmarking

## Setting Up Test Database

### Option 1: Using Invoke Tasks (Recommended)

#### Quick Setup
```zsh
# 1. Start main PostgreSQL container
uv run invoke db-start

# 2. Initialize main database users
uv run invoke db-init-users

# 3. Apply migrations to main database
uv run invoke migrate

# 4. Initialize test database (creates separate container)
uv run invoke db-init-test

# 5. Run tests
uv run invoke test
```

#### What `db-init-test` Does
- Starts a separate PostgreSQL container on port 5433 (configurable via `TEST_DATABASE_PORT`)
- Creates test database and test user
- Applies all migrations to test database
- Keeps test data isolated from production

### Option 2: Manual Setup

If you prefer manual control:

```zsh
# 1. Start PostgreSQL container
docker run -d \
  --name local-postgresql-test \
  -e POSTGRES_PASSWORD=adminA11 \
  -e POSTGRES_DB=kru_test_db \
  -p 5433:5432 \
  pgvector/pgvector:pg17

# 2. Wait for PostgreSQL to be ready
sleep 5

# 3. Create test user and schema
PGPASSWORD=adminA11 psql -h localhost -p 5433 -U postgres -d kru_test_db -c "
  CREATE USER kru_test WITH PASSWORD 'kruTest2026';
  GRANT CONNECT ON DATABASE kru_test_db TO kru_test;
  CREATE SCHEMA talentkru_test AUTHORIZATION kru_test;
  ALTER USER kru_test SET search_path TO talentkru_test, public;
"

# 4. Apply migrations
uv run alembic upgrade head

# 5. Run tests
uv run invoke test
```

## Running Tests

### All Tests
```zsh
# Run entire test suite
uv run invoke test

# Run with verbose output
uv run invoke test --verbose

# Run with coverage report
uv run invoke test-cov

# Run in watch mode (re-runs on file changes)
uv run invoke test-watch
```

### Specific Tests
```zsh
# Run specific test file
uv run invoke test --path tests/test_auth_service.py

# Run specific test function
uv run invoke test --path tests/test_auth_service.py::test_login

# Run tests matching a pattern
uv run pytest -k "test_candidate" --tb=short

# Run only integration tests
uv run pytest -m integration

# Run only unit tests
uv run pytest -m unit
```

### With Coverage
```zsh
# Generate coverage report
uv run invoke test-cov

# View HTML coverage report
open htmlcov/index.html

# Coverage with specific file
uv run pytest --cov=app.modules.auth --cov-report=html tests/test_auth_service.py
```

### Watch Mode
```zsh
# Re-run tests on file changes
uv run invoke test-watch

# Watch specific test file
uv run pytest-watch tests/test_auth_service.py
```

## Test Database Lifecycle

### Before Each Test
- Database session is created
- Test fixtures are initialized
- Organization and user fixtures are created

### During Test
- Test executes with isolated database session
- All queries run against test database
- Transactions are active

### After Each Test
- Session is rolled back automatically
- Test data is cleaned up
- Database returns to clean state

This rollback mechanism ensures tests don't interfere with each other.

## Test Fixtures

### Available Fixtures (conftest.py)

#### Database Fixtures
```python
@pytest.fixture
async def db_session(async_session_factory):
    """Provides a database session for the test."""
    # Automatically rolls back after test
    yield session
```

#### Organization Fixtures
```python
@pytest.fixture
async def org_id(db_session):
    """Creates a test organization and returns its ID."""
    # Returns: UUID of test organization
    yield org_id
```

#### User Fixtures
```python
@pytest.fixture
async def user_id(db_session, org_id):
    """Creates a test user and returns its ID."""
    yield user_id

@pytest.fixture
async def recruiter_user(db_session, org_id):
    """Creates a recruiter user."""
    yield recruiter_id

@pytest.fixture
async def admin_user(db_session, org_id):
    """Creates an admin user."""
    yield admin_id

@pytest.fixture
async def hiring_manager_user(db_session, org_id):
    """Creates a hiring manager user."""
    yield hiring_manager_id
```

### Using Fixtures in Tests

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_create_candidate(db_session: AsyncSession, org_id):
    """Test candidate creation."""
    # db_session: Database session for this test
    # org_id: UUID of test organization
    
    # Your test code here
    candidate = Candidate(
        organization_id=org_id,
        first_name="John",
        last_name="Doe"
    )
    db_session.add(candidate)
    await db_session.flush()
    
    # Assertions
    assert candidate.candidate_id is not None
```

## Test Organization

### Directory Structure
```
tests/
├── conftest.py                          # Shared fixtures
├── integration_fixtures.py              # Integration test helpers
│
├── test_auth_service.py                 # Auth service tests
├── test_auth_router.py                  # Auth router tests
├── test_auth_properties.py              # Property-based auth tests
│
├── test_candidate_service.py            # Candidate service tests
├── test_candidate_lifecycle_integration.py
├── test_candidate_minimal.py
│
├── test_resume_ingestion_service.py     # Resume tests
├── test_resume_models.py
│
├── test_skills_service.py               # Skills tests
├── test_skill_matching_integration.py
│
├── test_user_service.py                 # User tests
├── test_organizations.py
│
├── test_invitation_service.py           # Invitation tests
├── test_password_reset_service.py
│
├── test_rbac_service.py                 # RBAC tests
├── test_middleware_auth.py
│
├── test_privacy_service.py              # Privacy tests
├── test_dsar_integration.py
├── test_portal_dsar.py
│
├── test_job_posting_service.py          # Job posting tests
├── test_job_posting_integration.py
│
├── test_requisition_integration.py      # Requisition tests
├── test_scheduler_integration.py
│
├── test_domain_events_retry.py          # Event tests
├── test_audit_log.py
│
├── test_rate_limiting.py                # Rate limiting tests
├── test_rate_limit_middleware.py
│
├── test_health.py                       # Health check tests
├── test_smoke.py                        # Smoke tests
├── test_smoke_candidate_lifecycle.py
│
├── test_crypto.py                       # Crypto tests
├── test_dependencies.py
├── test_impersonate.py
├── test_impersonate_router.py
├── test_login_router.py
│
└── __pycache__/
```

### Test File Naming Conventions

- `test_<module>_service.py`: Service layer unit tests
- `test_<module>_router.py`: Route handler tests
- `test_<module>_integration.py`: End-to-end integration tests
- `test_<module>_properties.py`: Property-based tests (Hypothesis)
- `test_<module>_models.py`: Model/schema tests

## Writing Tests

### Basic Test Template

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

@pytest.mark.asyncio
async def test_example_functionality(db_session: AsyncSession, org_id):
    """Test description."""
    # Arrange: Set up test data
    test_data = {
        "organization_id": org_id,
        "name": "Test Item",
    }
    
    # Act: Execute the code being tested
    result = await some_service.create_item(db_session, **test_data)
    
    # Assert: Verify the results
    assert result.name == "Test Item"
    assert result.organization_id == org_id
```

### Async Test Pattern

All tests must use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_operation(db_session: AsyncSession):
    """Test async database operation."""
    # Use await for async calls
    result = await db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) >= 0
```

### Integration Test Pattern

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_workflow(db_session: AsyncSession, org_id):
    """Test complete workflow across multiple services."""
    # Create candidate
    candidate = Candidate(organization_id=org_id, first_name="John")
    db_session.add(candidate)
    await db_session.flush()
    
    # Upload resume
    resume = Resume(candidate_id=candidate.candidate_id, file_path="test.pdf")
    db_session.add(resume)
    await db_session.flush()
    
    # Extract skills
    skills = await skill_service.extract_skills(db_session, resume.resume_id)
    
    # Verify
    assert len(skills) > 0
```

### Property-Based Testing (Hypothesis)

```python
from hypothesis import given, strategies as st

@given(
    first_name=st.text(min_size=1, max_size=100),
    last_name=st.text(min_size=1, max_size=100),
)
@pytest.mark.asyncio
async def test_candidate_creation_properties(
    db_session: AsyncSession,
    org_id,
    first_name,
    last_name,
):
    """Test candidate creation with various inputs."""
    candidate = Candidate(
        organization_id=org_id,
        first_name=first_name,
        last_name=last_name,
    )
    db_session.add(candidate)
    await db_session.flush()
    
    assert candidate.first_name == first_name
    assert candidate.last_name == last_name
```

## Test Configuration (conftest.py)

### Environment Setup

The `conftest.py` file automatically sets required environment variables:

```python
_REQUIRED_ENV = {
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "5432",
    "DATABASE_NAME": "talentkru_test",
    "DATABASE_USER": "test_user",
    "DATABASE_PASSWORD": "test_password",
    "JWT_SIGNING_KEY": "test-jwt-signing-key",
    "ENCRYPTION_KEY": "test-encryption-key",
    "STORAGE_BACKEND": "local",
    "AGENT_API_KEY": "test-agent-api-key",
    "METRICS_USERNAME": "metrics_user",
    "METRICS_PASSWORD": "metrics_password",
}
```

These defaults are overridden by `.env` values if present.

### Customizing Test Configuration

To override test database settings, add to `.env`:

```zsh
# Override test database settings
TEST_DATABASE_HOST=localhost
TEST_DATABASE_PORT=5433
TEST_DATABASE_NAME=kru_test_db
TEST_DATABASE_USER=kru_test
TEST_DATABASE_PASSWORD=kruTest2026
```

## Troubleshooting

### Test Database Connection Issues

```zsh
# Check if test database is running
docker ps | grep postgresql

# Test connection manually
PGPASSWORD=kruTest2026 psql -h localhost -p 5433 -U kru_test -d kru_test_db -c "SELECT 1"

# View test container logs
docker logs local-postgresql-test

# Restart test database
docker restart local-postgresql-test
```

### Tests Hanging or Timing Out

```zsh
# Increase timeout in pytest.ini or pyproject.toml
[tool:pytest]
timeout = 300  # 5 minutes

# Run with verbose output to see where it hangs
uv run pytest -v -s tests/test_file.py

# Run single test with debugging
uv run pytest -v -s --pdb tests/test_file.py::test_function
```

### Database State Issues

```zsh
# Clear test database and reinitialize
uv run invoke db-init-test

# Or manually reset
docker stop local-postgresql-test
docker rm local-postgresql-test
uv run invoke db-init-test
```

### Import Errors in Tests

```zsh
# Ensure dependencies are synced
uv run invoke sync

# Clear Python cache
uv run invoke clean

# Reinstall dependencies
uv run invoke sync --refresh
```

### Async Test Errors

Ensure all async operations use `await`:

```python
# ❌ WRONG
result = db_session.execute(select(User))

# ✅ CORRECT
result = await db_session.execute(select(User))
```

## Performance Optimization

### Running Tests in Parallel

```zsh
# Install pytest-xdist
uv run invoke add-dev --package pytest-xdist

# Run tests in parallel (4 workers)
uv run pytest -n 4

# Auto-detect number of CPUs
uv run pytest -n auto
```

### Reducing Test Execution Time

```zsh
# Run only fast tests (skip slow integration tests)
uv run pytest -m "not slow"

# Run specific test module
uv run pytest tests/test_auth_service.py

# Stop on first failure
uv run pytest -x

# Stop after N failures
uv run pytest --maxfail=3
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: pgvector/pgvector:pg17
        env:
          POSTGRES_PASSWORD: adminA11
          POSTGRES_DB: kru_test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install uv
        run: pip install uv
      
      - name: Sync dependencies
        run: uv sync
      
      - name: Run tests
        run: uv run invoke test-cov
        env:
          TEST_DATABASE_HOST: localhost
          TEST_DATABASE_PORT: 5432
          TEST_DATABASE_NAME: kru_test_db
          TEST_DATABASE_USER: postgres
          TEST_DATABASE_PASSWORD: adminA11
```

## Best Practices

### ✅ DO

- Use `@pytest.mark.asyncio` for all async tests
- Use fixtures for common setup (db_session, org_id, user_id)
- Test one thing per test function
- Use descriptive test names: `test_<what>_<when>_<then>`
- Clean up resources in fixtures (via rollback)
- Use parametrize for testing multiple scenarios
- Mock external services (AI API, email, etc.)

### ❌ DON'T

- Use SQLite for tests (use PostgreSQL)
- Create test data without fixtures
- Leave test data in database after test
- Test multiple concerns in one test
- Use hardcoded UUIDs or timestamps
- Skip database tests for "speed"
- Modify `.env` for test configuration (use environment variables)

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## Quick Reference

```zsh
# Setup
uv run invoke db-start              # Start main PostgreSQL
uv run invoke db-init-users         # Initialize main database
uv run invoke migrate               # Apply migrations
uv run invoke db-init-test          # Setup test database

# Run Tests
uv run invoke test                  # Run all tests
uv run invoke test-cov              # Run with coverage
uv run invoke test-watch            # Watch mode
uv run pytest tests/test_file.py    # Specific file
uv run pytest -k "test_name"        # Pattern matching

# Cleanup
uv run invoke clean                 # Clean cache
docker stop local-postgresql-test   # Stop test container
docker rm local-postgresql-test     # Remove test container
```
