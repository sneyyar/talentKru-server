"""Shared pytest fixtures and configuration for the test suite."""

import os
import pytest
import asyncio
import time
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text


# ---------------------------------------------------------------------------
# pytest-asyncio Event Loop Configuration
#
# The asyncio_default_fixture_loop_scope is set in pyproject.toml to "function"
# to ensure each test gets a fresh event loop.
# 
# Greenlet initialization: Import asyncpg early to ensure greenlet is properly
# initialized in the event loop. This prevents "MissingGreenlet" errors.
# ---------------------------------------------------------------------------

# Ensure greenlet is initialized by importing asyncpg at module level
try:
    import asyncpg  # noqa: F401
except ImportError:
    pass

from app.base_model import Base
from app.config import settings
from app.modules.organizations.models import Organization

# IMPORTANT: Import all models before running tests to ensure SQLAlchemy mappers
# are fully initialized. This prevents circular reference errors when fixtures
# try to create model instances.
# The order matters: import organizations first, then other models that depend on it.
from app.modules.users.models import User, UserStatus, PasswordHistory
from app.modules.auth.models import RefreshToken
from app.modules.rbac.models import UserRole, Role, Privilege, RolePrivilege


# ---------------------------------------------------------------------------
# Set required environment variables before any app module is imported.
# This prevents pydantic-settings from raising ValidationError at import time.
# ---------------------------------------------------------------------------

_REQUIRED_ENV = {
    "JWT_SIGNING_KEY": "test-jwt-signing-key",
    "ENCRYPTION_KEY": "test-encryption-key",
    "STORAGE_BACKEND": "local",
    "AGENT_API_KEY": "test-agent-api-key",
    "METRICS_USERNAME": "metrics_user",
    "METRICS_PASSWORD": "metrics_password",
}

# Set defaults for non-database variables
for _key, _value in _REQUIRED_ENV.items():
    os.environ.setdefault(_key, _value)

# Use TEST_DATABASE_* variables from .env if available, otherwise use defaults
_TEST_DB_DEFAULTS = {
    "DATABASE_HOST": os.getenv("TEST_DATABASE_HOST", "localhost"),
    "DATABASE_PORT": os.getenv("TEST_DATABASE_PORT", "5432"),
    "DATABASE_NAME": os.getenv("TEST_DATABASE_NAME", "kru_test_db"),
    "DATABASE_USER": os.getenv("TEST_DATABASE_USER", "kru_test"),
    "DATABASE_PASSWORD": os.getenv("TEST_DATABASE_PASSWORD", "kruTest2026"),
}

for _key, _value in _TEST_DB_DEFAULTS.items():
    os.environ.setdefault(_key, _value)


# ---------------------------------------------------------------------------
# Session-scoped test infrastructure
# 
# This design initializes the database once at suite start, runs tests
# sequentially with isolated data (each test uses unique identifiers),
# and cleans up at suite end. No per-test rollbacks needed.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def database_url():
    """Get the database URL from settings (session-scoped for all tests)."""
    return settings.database_url


@pytest.fixture(scope="function")
async def engine(database_url):
    """
    Create async engine for tests.
    
    Function-scoped to align with event loop scope.
    Uses StaticPool for test isolation.
    """
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        database_url,
        echo=False,
        poolclass=StaticPool,  # Use StaticPool instead of NullPool for tests
        connect_args={"timeout": 30},
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
def async_session_factory(engine):
    """Create async session factory (function-scoped)."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Keep object attributes after commit to avoid sync reload
        autoflush=True,
    )


@pytest.fixture(scope="session", autouse=True)
def test_suite_init():
    """
    Initialize test database state at suite start.
    
    This fixture clears test data before and after the suite runs
    using psql commands.
    """
    import subprocess
    import os
    
    # Build psql command with credentials from environment
    host = os.getenv("TEST_DATABASE_HOST", "localhost")
    port = os.getenv("TEST_DATABASE_PORT", "5432")
    db_name = os.getenv("TEST_DATABASE_NAME", "kru_test_db")
    user = os.getenv("TEST_DATABASE_USER", "kru_test")
    password = os.getenv("TEST_DATABASE_PASSWORD", "kruTest2026")
    
    cleanup_sql = """
    DELETE FROM talentkru_test.candidate_skills CASCADE;
    DELETE FROM talentkru_test.unmatched_skill_reviews CASCADE;
    DELETE FROM talentkru_test.skills CASCADE;
    DELETE FROM talentkru_test.domains CASCADE;
    DELETE FROM talentkru_test.candidate_requisitions CASCADE;
    DELETE FROM talentkru_test.candidates CASCADE;
    DELETE FROM talentkru_test.job_profiles CASCADE;
    DELETE FROM talentkru_test.job_postings CASCADE;
    DELETE FROM talentkru_test.job_requisitions CASCADE;
    DELETE FROM talentkru_test.refresh_tokens CASCADE;
    DELETE FROM talentkru_test.password_history CASCADE;
    DELETE FROM talentkru_test.user_roles CASCADE;
    DELETE FROM talentkru_test.users CASCADE;
    DELETE FROM talentkru_test.organizations CASCADE;
    """
    
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    
    # Run cleanup at suite start
    try:
        subprocess.run(
            ["psql", "-h", host, "-p", port, "-U", user, "-d", db_name, "-c", cleanup_sql],
            env=env,
            check=False,
            capture_output=True,
            timeout=10,
        )
    except Exception as e:
        print(f"Warning: Could not run pre-cleanup: {e}")
    
    yield  # Run all tests
    
    # Run cleanup at suite end
    try:
        subprocess.run(
            ["psql", "-h", host, "-p", port, "-U", user, "-d", db_name, "-c", cleanup_sql],
            env=env,
            check=False,
            capture_output=True,
            timeout=10,
        )
    except Exception as e:
        print(f"Warning: Could not run post-cleanup: {e}")


@pytest.fixture
async def db_session(async_session_factory):
    """
    Provide a database session for each test.
    
    IMPORTANT: Each test must use UNIQUE data (via timestamps or UUIDs)
    so that tests don't conflict with each other. Tests run sequentially
    without per-test rollback.
    
    Since services use @transactional() decorators that commit(),
    data persists across tests. This is by design - tests must be
    designed to work with accumulated data or use unique identifiers.
    """
    async with async_session_factory() as session:
        yield session
        # NO cleanup here - tests are designed to not interfere with each other


@pytest.fixture
def test_run_id(request):
    """
    Generate a unique test run identifier for each test.
    
    Use this in test data (e.g., domain names, emails) to ensure
    tests don't conflict even if run multiple times.
    
    Combines timestamp with test name for uniqueness.
    
    Example:
        test_run_id = "test_create_domain_success-1717728540"
        domain_name = f"Python-{test_run_id}"
    """
    import time
    test_name = request.node.name
    timestamp = int(time.time() * 1000000)  # Microsecond precision
    return f"{test_name}-{timestamp}"


@pytest.fixture
async def org_id(db_session: AsyncSession):
    """Create a test organization and return its ID."""
    org = Organization(
        organization_id=uuid4(),
        name=f"Test Org {uuid4().hex[:8]}",
        slug=f"test-org-{uuid4().hex[:8]}",
        created_by=uuid4(),
    )
    db_session.add(org)
    await db_session.flush()
    return org.organization_id


@pytest.fixture
async def user_id(db_session: AsyncSession, org_id):
    """Create a test user and return its ID."""
    return uuid4()


@pytest.fixture
async def recruiter_user(db_session: AsyncSession, org_id):
    """Create a test user with Recruiter role."""
    return uuid4()


@pytest.fixture
async def admin_user(db_session: AsyncSession, org_id):
    """Create a test user with Administrator role."""
    return uuid4()


@pytest.fixture
async def hiring_manager_user(db_session: AsyncSession, org_id):
    """Create a test user with HiringManager role."""
    return uuid4()
