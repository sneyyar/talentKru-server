"""
Tests for UserService.

Feature: identity-and-access
Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8, 1.9

Tests cover:
- User creation and validation
- User updates
- User queries (by ID, pagination)
- Password history tracking
- Account locking with optimistic locking
- Email uniqueness within organization
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
import hashlib

from app.modules.users.models import User, UserStatus, PasswordHistory
from app.modules.users.service import (
    UserService,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.crypto import decrypt_field


class TestUserServiceValidation:
    """Validation tests for UserService - test input validation without DB."""

    @pytest.mark.asyncio
    async def test_create_user_missing_email(self, db_session: AsyncSession, org_id):
        """Test that creating user without email raises ValueError."""
        service = UserService(db_session)
        
        with pytest.raises(ValueError, match="Email is required"):
            await service.create_user(
                email="",
                given_name="John",
                last_name="Doe",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_missing_given_name(self, db_session: AsyncSession, org_id):
        """Test that creating user without given_name raises ValueError."""
        service = UserService(db_session)
        
        with pytest.raises(ValueError, match="Given name is required"):
            await service.create_user(
                email="test@example.com",
                given_name="",
                last_name="Doe",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_missing_last_name(self, db_session: AsyncSession, org_id):
        """Test that creating user without last_name raises ValueError."""
        service = UserService(db_session)
        
        with pytest.raises(ValueError, match="Last name is required"):
            await service.create_user(
                email="test@example.com",
                given_name="John",
                last_name="",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_create_user_invalid_email_format(self, db_session: AsyncSession, org_id):
        """Test that creating user with invalid email format raises ValueError."""
        service = UserService(db_session)
        
        with pytest.raises(ValueError, match="Invalid email format"):
            await service.create_user(
                email="not-an-email",
                given_name="John",
                last_name="Doe",
                org_id=org_id,
            )


class TestUserServiceIntegration:
    """Integration tests for UserService - test full user lifecycle."""

    @pytest.mark.asyncio
    async def test_create_user_success(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test successful user creation with unique data."""
        service = UserService(db_session)
        
        # Create user with unique email using test_run_id
        email = f"user-{test_run_id}-{uuid4().hex[:8]}@example.com"
        user = await service.create_user(
            email=email,
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Verify user was created
        assert user.user_id is not None
        assert user.organization_id == org_id
        assert user.given_name == "John"
        assert user.last_name == "Doe"
        assert user.status == UserStatus.PENDING_INVITATION
        assert user.hashed_password is None
        assert user.locale == "en-US"
        
        # Verify email is encrypted (should not be plaintext)
        assert user.email != email
        
        # Verify email_hash is set
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        assert user.email_hash == email_hash

    @pytest.mark.asyncio
    async def test_create_user_email_uniqueness(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test that duplicate email in same org raises UserAlreadyExistsError."""
        service = UserService(db_session)
        email = f"unique-{test_run_id}@example.com"
        
        # Create first user
        user1 = await service.create_user(
            email=email,
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        assert user1.user_id is not None
        
        # Try to create second user with same email - should fail
        with pytest.raises(UserAlreadyExistsError):
            await service.create_user(
                email=email,
                given_name="Jane",
                last_name="Smith",
                org_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_session: AsyncSession, org_id, test_run_id):
        """Test retrieving user by ID."""
        service = UserService(db_session)
        email = f"get-user-{test_run_id}@example.com"
        
        # Create user
        created_user = await service.create_user(
            email=email,
            given_name="Alice",
            last_name="Wonder",
            org_id=org_id,
        )
        
        # Retrieve user
        retrieved_user = await service.get_user_by_id(created_user.user_id, org_id)
        assert retrieved_user is not None
        assert retrieved_user.user_id == created_user.user_id
        assert retrieved_user.given_name == "Alice"
        assert retrieved_user.last_name == "Wonder"

    @pytest.mark.asyncio
    async def test_get_user_by_id_wrong_org(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test that getting user from different org returns None."""
        service = UserService(db_session)
        email = f"wrong-org-{test_run_id}@example.com"
        
        # Create user in org_id
        created_user = await service.create_user(
            email=email,
            given_name="Bob",
            last_name="Builder",
            org_id=org_id,
        )
        
        # Try to get user with different org_id
        other_org_id = uuid4()
        retrieved_user = await service.get_user_by_id(created_user.user_id, other_org_id)
        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_update_user_success(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test successful user update."""
        service = UserService(db_session)
        email = f"update-{test_run_id}@example.com"
        
        # Create user
        user = await service.create_user(
            email=email,
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Update user
        updated_user = await service.update_user(
            user_id=user.user_id,
            org_id=org_id,
            given_name="Jane",
            last_name="Smith",
            locale="fr-FR",
        )
        
        assert updated_user.given_name == "Jane"
        assert updated_user.last_name == "Smith"
        assert updated_user.locale == "fr-FR"

    @pytest.mark.asyncio
    async def test_update_nonexistent_user(self, db_session: AsyncSession, org_id):
        """Test updating nonexistent user raises UserNotFoundError."""
        service = UserService(db_session)
        
        with pytest.raises(UserNotFoundError):
            await service.update_user(
                user_id=uuid4(),
                org_id=org_id,
                given_name="Jane",
            )

    @pytest.mark.asyncio
    async def test_list_users(self, db_session: AsyncSession, org_id, test_run_id):
        """Test listing users in organization."""
        service = UserService(db_session)
        
        # Create multiple users
        for i in range(3):
            email = f"list-{test_run_id}-{i}@example.com"
            await service.create_user(
                email=email,
                given_name=f"User{i}",
                last_name="Test",
                org_id=org_id,
            )
        
        # List users
        users, total_count = await service.list_users(org_id, page=1, page_size=10)
        
        # Should have at least 3 users
        assert len(users) >= 3
        assert total_count >= 3

    @pytest.mark.asyncio
    async def test_list_users_pagination(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test pagination of user list."""
        service = UserService(db_session)
        
        # Create 5 users
        for i in range(5):
            email = f"pagination-{test_run_id}-{i}@example.com"
            await service.create_user(
                email=email,
                given_name=f"User{i}",
                last_name="Test",
                org_id=org_id,
            )
        
        # Get first page with page_size=2
        page1_users, total1 = await service.list_users(org_id, page=1, page_size=2)
        assert len(page1_users) <= 2
        
        # Get second page
        page2_users, total2 = await service.list_users(org_id, page=2, page_size=2)
        assert total1 == total2  # Total count should be same

    @pytest.mark.asyncio
    async def test_lock_user(self, db_session: AsyncSession, org_id, test_run_id):
        """Test locking a user account."""
        service = UserService(db_session)
        email = f"lock-{test_run_id}@example.com"
        
        # Create user
        user = await service.create_user(
            email=email,
            given_name="Locked",
            last_name="User",
            org_id=org_id,
        )
        
        # Lock user
        locked_user = await service.lock_user(user.user_id, org_id)
        assert locked_user.status == UserStatus.LOCKED
        
        # Verify persistence
        retrieved = await service.get_user_by_id(user.user_id, org_id)
        assert retrieved.status == UserStatus.LOCKED

    @pytest.mark.asyncio
    async def test_lock_nonexistent_user(self, db_session: AsyncSession, org_id):
        """Test locking nonexistent user raises UserNotFoundError."""
        service = UserService(db_session)
        
        with pytest.raises(UserNotFoundError):
            await service.lock_user(uuid4(), org_id)

    @pytest.mark.asyncio
    async def test_password_history_tracking(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test password history tracking."""
        service = UserService(db_session)
        email = f"password-{test_run_id}@example.com"
        
        # Create user
        user = await service.create_user(
            email=email,
            given_name="History",
            last_name="User",
            org_id=org_id,
        )
        
        # Add password history entries
        hashes = []
        for i in range(3):
            hash_value = f"hash_{i}_" + "x" * 50
            entry = await service.add_password_history(user.user_id, hash_value)
            hashes.append(hash_value)
            assert entry.password_history_id is not None
        
        # Retrieve password history
        history = await service.get_password_history(user.user_id, limit=5)
        assert len(history) >= 3
        # Most recent first
        assert history[0].hashed_password == hashes[2]

    @pytest.mark.asyncio
    async def test_password_history_limit(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test password history respects limit parameter."""
        service = UserService(db_session)
        email = f"history-limit-{test_run_id}@example.com"
        
        # Create user
        user = await service.create_user(
            email=email,
            given_name="History",
            last_name="Limit",
            org_id=org_id,
        )
        
        # Add 5 password history entries
        for i in range(5):
            hash_value = f"hash_{i}_" + "x" * 50
            await service.add_password_history(user.user_id, hash_value)
        
        # Retrieve with limit=2
        history = await service.get_password_history(user.user_id, limit=2)
        assert len(history) == 2
