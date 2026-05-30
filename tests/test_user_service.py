"""
Tests for UserService.

Feature: identity-and-access
Property 1: Email uniqueness within organization

Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8, 1.9
"""

import pytest
from hypothesis import given, settings as hypothesis_settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from app.base_model import Base
from app.modules.users.models import User, UserStatus, PasswordHistory
from app.modules.users.service import (
    UserService,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.organizations.models import Organization
from app.modules.rbac.models import Role, UserRole, Privilege, RolePrivilege
from app.modules.auth.models import RefreshToken, RevokedToken


@pytest.fixture
async def async_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        # Create tables in dependency order
        await conn.run_sync(lambda c: Role.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: Privilege.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: User.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: UserRole.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: RolePrivilege.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: PasswordHistory.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: RefreshToken.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: RevokedToken.__table__.create(c, checkfirst=True))
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


class TestUserServiceBasics:
    """Basic unit tests for UserService."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, async_db):
        """Test successful user creation."""
        service = UserService(async_db)
        org_id = uuid4()
        
        user = await service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        assert user.user_id is not None
        assert user.organization_id == org_id
        assert user.given_name == "John"
        assert user.last_name == "Doe"
        assert user.status == UserStatus.PENDING_INVITATION
        assert user.hashed_password is None

    @pytest.mark.asyncio
    async def test_create_user_missing_email(self, async_db):
        """Test that creating user without email raises ValueError."""
        service = UserService(async_db)
        org_id = uuid4()
        
        with pytest.raises(ValueError, match="Email is required"):
            await service.create_user(
                email="",
                given_name="John",
                last_name="Doe",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_missing_given_name(self, async_db):
        """Test that creating user without given_name raises ValueError."""
        service = UserService(async_db)
        org_id = uuid4()
        
        with pytest.raises(ValueError, match="Given name is required"):
            await service.create_user(
                email="test@example.com",
                given_name="",
                last_name="Doe",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_missing_last_name(self, async_db):
        """Test that creating user without last_name raises ValueError."""
        service = UserService(async_db)
        org_id = uuid4()
        
        with pytest.raises(ValueError, match="Last name is required"):
            await service.create_user(
                email="test@example.com",
                given_name="John",
                last_name="",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_invalid_email_format(self, async_db):
        """Test that creating user with invalid email format raises ValueError."""
        service = UserService(async_db)
        org_id = uuid4()
        
        with pytest.raises(ValueError, match="Invalid email format"):
            await service.create_user(
                email="not-an-email",
                given_name="John",
                last_name="Doe",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_same_org(self, async_db):
        """Test that creating duplicate user in same org raises UserAlreadyExistsError."""
        service = UserService(async_db)
        org_id = uuid4()
        
        # Create first user
        await service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Try to create duplicate
        with pytest.raises(UserAlreadyExistsError):
            await service.create_user(
                email="test@example.com",
                given_name="Jane",
                last_name="Smith",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_same_email_different_org(self, async_db):
        """Test that same email can be used in different organizations."""
        service = UserService(async_db)
        org_id_1 = uuid4()
        org_id_2 = uuid4()
        
        # Create user in org 1
        user1 = await service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id_1,
        )
        
        # Create user with same email in org 2
        user2 = await service.create_user(
            email="test@example.com",
            given_name="Jane",
            last_name="Smith",
            org_id=org_id_2,
        )
        
        assert user1.user_id != user2.user_id
        assert user1.organization_id == org_id_1
        assert user2.organization_id == org_id_2

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, async_db):
        """Test retrieving user by ID."""
        service = UserService(async_db)
        org_id = uuid4()
        
        created_user = await service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        retrieved_user = await service.get_user_by_id(created_user.user_id, org_id)
        
        assert retrieved_user is not None
        assert retrieved_user.user_id == created_user.user_id
        assert retrieved_user.given_name == "John"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, async_db):
        """Test that getting non-existent user returns None."""
        service = UserService(async_db)
        org_id = uuid4()
        
        user = await service.get_user_by_id(uuid4(), org_id)
        
        assert user is None

    @pytest.mark.asyncio
    async def test_lock_user(self, async_db):
        """Test locking a user."""
        service = UserService(async_db)
        org_id = uuid4()
        
        user = await service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        locked_user = await service.lock_user(user.user_id, org_id)
        
        assert locked_user.status == UserStatus.LOCKED

    @pytest.mark.asyncio
    async def test_lock_user_not_found(self, async_db):
        """Test that locking non-existent user raises UserNotFoundError."""
        service = UserService(async_db)
        org_id = uuid4()
        
        with pytest.raises(UserNotFoundError):
            await service.lock_user(uuid4(), org_id)


@given(
    email=st.emails(),
    given_name=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
    last_name=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
)
@hypothesis_settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.filter_too_much])
@pytest.mark.asyncio
async def test_email_uniqueness_within_organization(
    async_db, email, given_name, last_name
):
    """
    Property 1: Email uniqueness within organization
    
    Validates: Requirements 1.2, 1.3
    
    Same email + same org → second call raises 409 (UserAlreadyExistsError)
    Same email + different orgs → both succeed
    """
    # Skip if email is invalid (st.emails() can generate some invalid emails)
    import re
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if not EMAIL_REGEX.match(email) or len(email) > 254:
        return
    
    service = UserService(async_db)
    org_id_1 = uuid4()
    org_id_2 = uuid4()
    
    # Create user in org 1
    user1 = await service.create_user(
        email=email,
        given_name=given_name,
        last_name=last_name,
        org_id=org_id_1,
    )
    assert user1 is not None
    
    # Try to create duplicate in same org - should fail
    with pytest.raises(UserAlreadyExistsError):
        await service.create_user(
            email=email,
            given_name=given_name,
            last_name=last_name,
            org_id=org_id_1,
        )
    
    # Create same email in different org - should succeed
    user2 = await service.create_user(
        email=email,
        given_name=given_name,
        last_name=last_name,
        org_id=org_id_2,
    )
    assert user2 is not None
    assert user1.user_id != user2.user_id
