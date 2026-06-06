# Testing Guide

**Last Updated:** June 6, 2026

## Overview

TalentKru.ai uses **PostgreSQL** for all database and integration tests. Tests connect to a dedicated test database using environment variables from `.env` (separate from production `DATABASE_*` variables), ensuring consistency with production behavior and supporting advanced features like pgvector.

### Why PostgreSQL?
- Feature parity with production
- pgvector support for semantic search
- Advanced features (constraints, triggers, extensions) work identically
- Foreign keys and relationships validated
- Realistic performance characteristics

## Test Architecture

### Stable Design (Implemented June 6, 2026)

Tests use a **three-layer architecture** with no per-test rollbacks:

**Layer 1: Session-Scoped Initialization**
- `test_suite_init` fixture cleans database at suite start and end (via psql)
- Prevents cross-suite data pollution

**Layer 2: Function-Scoped Sessions**
- Fresh `db_session` per test with `expire_on_commit=False`
- StaticPool for test isolation
- No automatic rollback (data persists by design)

**Layer 3: Test Data Isolation**
- `test_run_id` fixture generates unique IDs: `{test_name}-{timestamp}`
- Use in all unique fields to prevent conflicts across runs

**Result**: Tests run sequentially without interference; fully production-like (real commits).

## Test Database Configuration

### Environment Variables

```zsh
TEST_DATABASE_HOST=localhost
TEST_DATABASE_PORT=5432
TEST_DATABASE_NAME=kru_test_db
TEST_DATABASE_USER=kru_test
TEST_DATABASE_PASSWORD=kruTest2026
```

**Note**: These are separate from production `DATABASE_*` variables.

## Setup

```zsh
# Quick setup
uv run invoke db-start              # Start PostgreSQL
uv run invoke db-init-users         # Initialize main database
uv run invoke migrate               # Apply migrations to main database
uv run invoke db-init-test          # Initialize test database
uv run invoke test                  # Run tests
```

For manual setup, see [Tech Stack Guide - Database Management](./tech.md#database-management).

## Running Tests

```zsh
# All tests
uv run invoke test

# With coverage
uv run invoke test-cov

# Watch mode (re-runs on changes)
uv run invoke test-watch

# Specific file
uv run pytest tests/test_auth_service.py -v

# Specific test
uv run pytest tests/test_auth_service.py::test_login -v

# Pattern matching
uv run pytest -k "test_candidate" -v
```

## Test Fixtures

### Core Fixtures (conftest.py)

- `db_session`: Fresh AsyncSession per test (function-scoped, no cleanup)
- `test_run_id`: Unique ID per test; use as `f"{data}-{test_run_id}"` for uniqueness
- `org_id`: Test organization UUID
- `user_id`, `recruiter_user`, `admin_user`, `hiring_manager_user`: Test user UUIDs

### Example Usage

```python
@pytest.mark.asyncio
async def test_create_domain(db_session: AsyncSession, test_run_id):
    """Test domain creation with unique data."""
    service = SkillService(db_session)
    # Use test_run_id for unique data
    name = f"Python-{test_run_id}"
    domain = await service.create_domain(name)
    
    assert domain.domain_id is not None
    assert domain.name == name
```

## Writing Tests

**Key Principle**: Use `test_run_id` to create unique data so tests don't interfere.

### Basic Pattern

```python
@pytest.mark.asyncio
async def test_create_item(db_session: AsyncSession, test_run_id):
    """Test description."""
    service = MyService(db_session)
    
    # Arrange: Create unique test data
    item_name = f"TestItem-{test_run_id}"
    
    # Act: Call service (commits automatically)
    result = await service.create_item(item_name)
    
    # Assert: Verify results (object attributes accessible)
    assert result.id is not None
    assert result.name == item_name
```

### Error Testing

```python
@pytest.mark.asyncio
async def test_duplicate_error(db_session: AsyncSession, test_run_id):
    """Test 409 conflict on duplicate."""
    service = MyService(db_session)
    name = f"TestItem-{test_run_id}"
    
    await service.create_item(name)
    
    with pytest.raises(HTTPException) as exc_info:
        await service.create_item(name)
    
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
```

### Complex Operations

```python
@pytest.mark.asyncio
async def test_workflow(db_session: AsyncSession, test_run_id, org_id):
    """Test multi-step workflow."""
    from sqlalchemy import select
    
    service = MyService(db_session)
    
    # Create related data with unique identifiers
    item1 = await service.create_item(f"Item1-{test_run_id}", org_id)
    item2 = await service.create_item(f"Item2-{test_run_id}", org_id)
    
    # Link items
    result = await service.link_items(item1.id, item2.id)
    
    # Verify via query
    stmt = select(Item).where(Item.id == item1.id)
    persisted = await db_session.execute(stmt)
    assert persisted.scalar_one() is not None
```

## Test Configuration (conftest.py)

### Key Settings

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"  # Critical for fixture scopes
testpaths = ["tests"]
addopts = "-v --tb=short"
```

### Session Factory Configuration

```python
async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keeps objects valid after service commits
    autoflush=True,
)

create_async_engine(
    database_url,
    poolclass=StaticPool,  # Test isolation
    connect_args={"timeout": 30},
)
```

### Environment Variables (Auto-Set in conftest.py)

```python
_REQUIRED_ENV = {
    "JWT_SIGNING_KEY": "test-jwt-signing-key",
    "ENCRYPTION_KEY": "test-encryption-key",
    "STORAGE_BACKEND": "local",
    "AGENT_API_KEY": "test-agent-api-key",
    "METRICS_USERNAME": "metrics_user",
    "METRICS_PASSWORD": "metrics_password",
}
```

Defaults overridden by `.env` if present.

## Troubleshooting

### Connection Issues

```zsh
# Test connection
docker ps | grep postgresql

# Verify database exists
PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d kru_test_db -c "SELECT 1"
```

### Test Failures

```zsh
# Run with verbose output
uv run pytest -v -s tests/test_file.py

# Run single test with debugger
uv run pytest -v -s --pdb tests/test_file.py::test_function

# Check Python cache
uv run invoke clean
uv run invoke sync --refresh
```

### Database State Issues

```zsh
# Reset test database (deletes all test data)
uv run invoke db-init-test

# Or manually reset
PGPASSWORD=adminA11 psql -h localhost -p 5432 -U postgres -d kru_test_db -c "
  DROP SCHEMA IF EXISTS talentkru_test CASCADE;
  CREATE SCHEMA talentkru_test AUTHORIZATION kru_test;
"
```

### Data Conflicts on Rerun

**Cause**: Tests creating same data names as previous run.

**Solution**: Use `test_run_id` fixture in all unique fields:

```python
# ❌ Wrong - same name every run
domain_name = "Python"

# ✅ Correct - unique per test
domain_name = f"Python-{test_run_id}"
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- Detailed guides in repository:
  - `TEST_ARCHITECTURE_FIXED.md` - Technical deep-dive
  - `TEST_FIX_SUMMARY.md` - Quick reference
  - `TEST_IMPLEMENTATION_GUIDE.md` - Developer guide
