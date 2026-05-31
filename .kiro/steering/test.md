# Testing Guide

**Last Updated:** May 31, 2026

## Overview

TalentKru.ai uses **PostgreSQL** for all database and integration tests, not SQLite. Tests connect to a dedicated test database using environment variables from `.env`, ensuring consistency with production behavior and supporting advanced features like pgvector for semantic search.

## Test Database Configuration

### Environment Variables

Tests use these environment variables from `.env`:

```zsh
TEST_DATABASE_HOST=localhost
TEST_DATABASE_PORT=5432
TEST_DATABASE_NAME=kru_test_db
TEST_DATABASE_USER=kru_test
TEST_DATABASE_PASSWORD=kruTest2026
```

These are **separate** from production variables (`DATABASE_*`), allowing tests to run without affecting production data. Both databases exist in the **same PostgreSQL instance** for simplicity.

### Why PostgreSQL for Tests?

1. **Feature Parity**: Tests run against the same database engine as production
2. **pgvector Support**: Semantic search and vector operations work identically
3. **Advanced Features**: Constraints, triggers, and extensions behave as in production
4. **Data Integrity**: Foreign keys and complex relationships are validated
5. **Performance**: Realistic performance characteristics for benchmarking

## Setting Up Test Database

### Quick Setup (Recommended)

```zsh
# 1. Start PostgreSQL container (hosts both dev and test databases)
uv run invoke db-start

# 2. Initialize main database users
uv run invoke db-init-users

# 3. Apply migrations to main database
uv run invoke migrate

# 4. Initialize test database (creates test DB in same instance)
uv run invoke db-init-test

# 5. Run tests
uv run invoke test
```

The `db-init-test` task:
- Connects to the existing PostgreSQL instance
- Creates test database and test user
- Applies all migrations to test database
- Keeps test data isolated from production in separate database

### Manual Setup

If you prefer manual control:

```zsh
# 1. Start PostgreSQL container (if not already running)
uv run invoke db-start

# 2. Create test database
PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE kru_test_db;"

# 3. Create test user and schema
PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d kru_test_db -c "
  CREATE USER kru_test WITH PASSWORD 'kruTest2026';
  GRANT CONNECT ON DATABASE kru_test_db TO kru_test;
  CREATE SCHEMA talentkru_test AUTHORIZATION kru_test;
  ALTER USER kru_test SET search_path TO talentkru_test, public;
"

# 4. Apply migrations to test database
DATABASE_HOST=localhost \
DATABASE_PORT=5432 \
DATABASE_NAME=kru_test_db \
DATABASE_USER=kru_test \
DATABASE_PASSWORD=kruTest2026 \
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

```python
@pytest.fixture
async def db_session(async_session_factory):
    """Provides a database session for the test."""
    # Automatically rolls back after test
    yield session

@pytest.fixture
async def org_id(db_session):
    """Creates a test organization and returns its ID."""
    yield org_id

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
    candidate = Candidate(
        organization_id=org_id,
        first_name="John",
        last_name="Doe"
    )
    db_session.add(candidate)
    await db_session.flush()
    
    assert candidate.candidate_id is not None
```

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
TEST_DATABASE_HOST=localhost
TEST_DATABASE_PORT=5433
TEST_DATABASE_NAME=kru_test_db
TEST_DATABASE_USER=kru_test
TEST_DATABASE_PASSWORD=kruTest2026
```

## Troubleshooting

### Test Database Connection Issues

```zsh
# Check if PostgreSQL is running
docker ps | grep postgresql

# Test connection to main database
PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d krudb -c "SELECT 1"

# Test connection to test database
PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d kru_test_db -c "SELECT 1"

# View PostgreSQL container logs
docker logs local-postgresql-db

# Restart PostgreSQL container
docker restart local-postgresql-db
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
# Reinitialize test database
uv run invoke db-init-test

# Or manually reset test database
PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d kru_test_db -c "
  DROP SCHEMA IF EXISTS talentkru_test CASCADE;
  CREATE SCHEMA talentkru_test AUTHORIZATION kru_test;
"

# Then reapply migrations
DATABASE_HOST=localhost \
DATABASE_PORT=5432 \
DATABASE_NAME=kru_test_db \
DATABASE_USER=kru_test \
DATABASE_PASSWORD=kruTest2026 \
uv run alembic upgrade head
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
          POSTGRES_DB: krudb
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
      
      - name: Initialize main database
        run: |
          PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d krudb -f db-scripts/create_user.sql
      
      - name: Apply migrations to main database
        run: uv run alembic upgrade head
        env:
          DATABASE_HOST: localhost
          DATABASE_PORT: 5432
          DATABASE_NAME: krudb
          DATABASE_USER: talentkru_app
          DATABASE_PASSWORD: kruApp2026
      
      - name: Initialize test database
        run: |
          PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE kru_test_db;"
          PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d kru_test_db -c "
            CREATE USER kru_test WITH PASSWORD 'kruTest2026';
            GRANT CONNECT ON DATABASE kru_test_db TO kru_test;
            CREATE SCHEMA talentkru_test AUTHORIZATION kru_test;
            ALTER USER kru_test SET search_path TO talentkru_test, public;
          "
      
      - name: Apply migrations to test database
        run: uv run alembic upgrade head
        env:
          DATABASE_HOST: localhost
          DATABASE_PORT: 5432
          DATABASE_NAME: kru_test_db
          DATABASE_USER: kru_test
          DATABASE_PASSWORD: kruTest2026
      
      - name: Run tests
        run: uv run invoke test-cov
        env:
          TEST_DATABASE_HOST: localhost
          TEST_DATABASE_PORT: 5432
          TEST_DATABASE_NAME: kru_test_db
          TEST_DATABASE_USER: kru_test
          TEST_DATABASE_PASSWORD: kruTest2026
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

## Quick Reference

```zsh
# Setup
uv run invoke db-start              # Start PostgreSQL (hosts both dev and test)
uv run invoke db-init-users         # Initialize main database
uv run invoke migrate               # Apply migrations to main database
uv run invoke db-init-test          # Setup test database in same instance

# Run Tests
uv run invoke test                  # Run all tests
uv run invoke test-cov              # Run with coverage
uv run invoke test-watch            # Watch mode
uv run pytest tests/test_file.py    # Specific file
uv run pytest -k "test_name"        # Pattern matching

# Cleanup
uv run invoke clean                 # Clean cache
docker stop local-postgresql-db     # Stop PostgreSQL container
docker rm local-postgresql-db       # Remove PostgreSQL container
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
