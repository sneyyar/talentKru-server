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
from app.modules.email_config.models import (
    OrganizationEmailConfig,
    SystemSetting,
    ProviderType,
)
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.job_profile.models import JobProfile
from app.modules.requisitions.models import JobRequisition, RequisitionStatus


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

# Import encrypt_field for use in fixtures
from app.crypto import encrypt_field


# ---------------------------------------------------------------------------
# Session-scoped test infrastructure
# 
# This design initializes the database once at suite start, runs tests
# sequentially with isolated data (each test uses unique identifiers),
# and cleans up at suite end. No per-test rollbacks needed.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def database_url():
    """Get the test database URL."""
    # Build URL from TEST_DATABASE_* variables
    test_host = os.getenv("TEST_DATABASE_HOST", "localhost")
    test_port = os.getenv("TEST_DATABASE_PORT", "5432")
    test_name = os.getenv("TEST_DATABASE_NAME", "kru_test_db")
    test_user = os.getenv("TEST_DATABASE_USER", "kru_test")
    test_password = os.getenv("TEST_DATABASE_PASSWORD", "kruTest2026")
    
    return f"postgresql+asyncpg://{test_user}:{test_password}@{test_host}:{test_port}/{test_name}"


@pytest.fixture(scope="function")
async def engine(database_url):
    """
    Create async engine for tests.
    
    Function-scoped to align with event loop scope.
    Uses StaticPool for test isolation.
    
    The test database user (kru_test) has search_path=kru_test,public
    which ensures tables are found in the kru_test schema.
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
    DELETE FROM talentkru_test.interview_journeys CASCADE;
    DELETE FROM talentkru_test.interview_journey_stage_history CASCADE;
    DELETE FROM talentkru_test.candidate_interview_journeys CASCADE;
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


@pytest.fixture
def current_user_context(user_id):
    """
    Set the current_user_id_var context for the test.
    
    This fixture automatically sets the current_user_id_var context variable
    before each test and resets it afterward. This allows the before_flush
    listener to properly populate audit fields (created_by, updated_by, deleted_by).
    
    Tests that need a different user context can override this by explicitly
    setting the context variable before calling the service method.
    """
    from app.base_model import current_user_id_var
    
    token = current_user_id_var.set(str(user_id))
    yield
    current_user_id_var.reset(token)


@pytest.fixture
async def test_candidate(db_session: AsyncSession, org_id, current_user_context):
    """
    Create a test candidate for use in tests that need candidate records.
    
    This fixture creates a minimal candidate with required fields.
    Use for tests that need to reference candidates via foreign key.
    """
    from app.modules.candidates.models import Candidate, GlobalStatus
    from app.crypto import encrypt_field
    import hashlib
    
    candidate_id = uuid4()
    name = f"Test Candidate {uuid4().hex[:8]}"
    email = f"candidate-{uuid4().hex[:8]}@test.com"
    
    candidate = Candidate(
        candidate_id=candidate_id,
        organization_id=org_id,
        name=encrypt_field(name),
        name_hash=hashlib.sha256(name.lower().encode()).hexdigest(),
        email=encrypt_field(email),
        email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
        global_status=GlobalStatus.ACTIVE.value,
    )
    db_session.add(candidate)
    await db_session.flush()
    return candidate


@pytest.fixture
async def test_job_profile(db_session: AsyncSession, org_id, current_user_context):
    """
    Create a test job profile for use in tests that need job profile records.
    
    This fixture creates a minimal job profile with required fields.
    Use for tests that need to reference job profiles.
    """
    from app.modules.job_profile.models import JobProfile
    
    job_profile_id = uuid4()
    job_profile = JobProfile(
        job_profile_id=job_profile_id,
        organization_id=org_id,
        name=f"Test Role {uuid4().hex[:8]}",
    )
    db_session.add(job_profile)
    await db_session.flush()
    return job_profile


@pytest.fixture
async def test_hiring_manager(db_session: AsyncSession, org_id, current_user_context):
    """
    Create a test hiring manager user for job requisitions.
    
    This fixture creates a minimal user to serve as a hiring manager.
    """
    from app.modules.users.models import User, UserStatus
    import hashlib
    
    user_id = uuid4()
    email = f"manager-{uuid4().hex[:8]}@test.com"
    
    user = User(
        user_id=user_id,
        organization_id=org_id,
        email=encrypt_field(email),
        email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
        given_name=encrypt_field("Test"),
        last_name=encrypt_field("Manager"),
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_job_requisition(db_session: AsyncSession, org_id, test_job_profile, test_hiring_manager, current_user_context):
    """
    Create a test job requisition for use in tests that need requisition records.
    
    This fixture creates a minimal job requisition with required fields.
    Use for tests that need to reference requisitions via foreign key.
    """
    from app.modules.requisitions.models import JobRequisition, RequisitionStatus
    
    job_requisition_id = uuid4()
    job_requisition = JobRequisition(
        job_requisition_id=job_requisition_id,
        organization_id=org_id,
        job_profile_id=test_job_profile.job_profile_id,
        title=f"Test Requisition {uuid4().hex[:8]}",
        department="Engineering",
        location="Remote",
        hiring_manager_user_id=test_hiring_manager.user_id,
        status=RequisitionStatus.OPEN.value,
    )
    db_session.add(job_requisition)
    await db_session.flush()
    return job_requisition
