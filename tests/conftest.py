"""Shared pytest fixtures and configuration for the test suite."""

import os
import pytest
import asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.base_model import Base
from app.config import settings
from app.modules.organizations.models import Organization


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
# Integration Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def database_url():
    """Get the database URL from settings."""
    return settings.database_url


@pytest.fixture(scope="session")
async def engine(database_url):
    """Create async engine for integration tests."""
    # Use NullPool to avoid connection pooling issues in tests
    engine = create_async_engine(
        database_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"timeout": 30},
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def async_session_factory(engine):
    """Create async session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db_session(async_session_factory):
    """
    Provide a database session for each test.
    
    Automatically rolls back after the test to keep database clean.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            # Rollback to clean up test data
            await session.rollback()


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
    # Just return a UUID - we don't need to create actual User records for these tests
    return uuid4()


@pytest.fixture
async def recruiter_user(db_session: AsyncSession, org_id):
    """Create a test user with Recruiter role."""
    # Just return a UUID
    return uuid4()


@pytest.fixture
async def admin_user(db_session: AsyncSession, org_id):
    """Create a test user with Administrator role."""
    # Just return a UUID
    return uuid4()


@pytest.fixture
async def hiring_manager_user(db_session: AsyncSession, org_id):
    """Create a test user with HiringManager role."""
    # Just return a UUID
    return uuid4()
