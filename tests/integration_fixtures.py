"""
Shared fixtures and utilities for integration tests.

These fixtures connect to the real Docker pgvector database and provide
async database sessions for integration testing.
"""

import pytest
import os
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.base_model import Base
from app.config import settings
from app.modules.organizations.models import Organization
from app.modules.users.models import User
from app.modules.rbac.models import Role


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
        created_by=uuid4(),
    )
    db_session.add(org)
    await db_session.flush()
    return org.organization_id


@pytest.fixture
async def user_id(db_session: AsyncSession, org_id):
    """Create a test user and return its ID."""
    user = User(
        user_id=uuid4(),
        organization_id=org_id,
        email=f"test-{uuid4().hex[:8]}@example.com",
        email_hash=f"hash-{uuid4().hex[:8]}",
        password_hash="test_hash",
        first_name="Test",
        last_name="User",
        created_by=uuid4(),
    )
    db_session.add(user)
    await db_session.flush()
    return user.user_id


@pytest.fixture
async def recruiter_user(db_session: AsyncSession, org_id):
    """Create a test user with Recruiter role."""
    user = User(
        user_id=uuid4(),
        organization_id=org_id,
        email=f"recruiter-{uuid4().hex[:8]}@example.com",
        email_hash=f"hash-{uuid4().hex[:8]}",
        password_hash="test_hash",
        first_name="Recruiter",
        last_name="User",
        created_by=uuid4(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession, org_id):
    """Create a test user with Administrator role."""
    user = User(
        user_id=uuid4(),
        organization_id=org_id,
        email=f"admin-{uuid4().hex[:8]}@example.com",
        email_hash=f"hash-{uuid4().hex[:8]}",
        password_hash="test_hash",
        first_name="Admin",
        last_name="User",
        created_by=uuid4(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def hiring_manager_user(db_session: AsyncSession, org_id):
    """Create a test user with HiringManager role."""
    user = User(
        user_id=uuid4(),
        organization_id=org_id,
        email=f"hiring-{uuid4().hex[:8]}@example.com",
        email_hash=f"hash-{uuid4().hex[:8]}",
        password_hash="test_hash",
        first_name="Hiring",
        last_name="Manager",
        created_by=uuid4(),
    )
    db_session.add(user)
    await db_session.flush()
    return user
