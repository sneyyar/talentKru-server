"""
User service for user lifecycle management.

Provides:
- UserService: User CRUD, lockout logic, password history management
- User creation with email validation and encryption
- User status transitions with audit logging
- Password history tracking and validation

Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8, 1.9
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional, cast
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import write_audit_log
from app.crypto import decrypt_field, encrypt_field
from app.modules.users.models import PasswordHistory, User, UserStatus


# Email validation regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class UserService:
    """
    User service for managing user lifecycle.
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8, 1.9
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the user service.
        
        Args:
            db: AsyncSession for database access
        """
        self.db = db

    async def create_user(
        self,
        email: str,
        given_name: str,
        last_name: str,
        org_id: UUID,
        manager_user_id: Optional[UUID] = None,
        locale: str = "en-US",
        actor_id: Optional[UUID] = None,
        obo_by: Optional[UUID] = None,
    ) -> User:
        """
        Create a new user with PendingInvitation status.
        
        Args:
            email: User email address
            given_name: User's given name
            last_name: User's last name
            org_id: Organization ID
            manager_user_id: Optional manager user ID
            locale: User's locale preference (default: en-US)
            actor_id: User ID of the actor creating the user (for audit logging)
            obo_by: SuperAdmin user ID if this is an on-behalf-of action (for audit logging)
            
        Returns:
            Created User entity
            
        Raises:
            ValueError: If email format is invalid or required fields are missing
            UserAlreadyExistsError: If user with same email already exists in org
            
        Requirements: 1.1, 1.2, 1.3, 7.3
        """
        # Validate required fields
        if not email or not email.strip():
            raise ValueError("Email is required")
        if not given_name or not given_name.strip():
            raise ValueError("Given name is required")
        if not last_name or not last_name.strip():
            raise ValueError("Last name is required")
        
        # Validate email format
        if not EMAIL_REGEX.match(email):
            raise ValueError("Invalid email format")
        
        # Compute email hash for uniqueness
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        
        # Check for existing user with same email in org
        existing = await self._get_user_by_email_hash(email_hash, org_id)
        if existing:
            raise UserAlreadyExistsError(
                f"User with email {email} already exists in organization"
            )
        
        # Encrypt email
        encrypted_email = encrypt_field(email)
        
        # Create user with PendingInvitation status
        user = User(
            organization_id=org_id,
            email=encrypted_email,
            email_hash=email_hash,
            given_name=given_name.strip(),
            last_name=last_name.strip(),
            status=UserStatus.PENDING_INVITATION,
            manager_user_id=manager_user_id,
            hashed_password=None,  # No password until invitation accepted
            locale=locale,
        )
        
        self.db.add(user)
        await self.db.flush()
        
        # Write audit log entry if actor_id is provided
        if actor_id:
            await write_audit_log(
                actor_id=actor_id,
                action="UserCreated",
                target_entity="User",
                target_id=user.user_id,
                org_id=org_id,
                changed_values={
                    "email": email,
                    "given_name": given_name,
                    "last_name": last_name,
                    "status": UserStatus.PENDING_INVITATION.value,
                },
                obo_by=obo_by,
                timestamp=datetime.now(timezone.utc),
                db=self.db,
            )
        
        return user

    async def update_user(
        self,
        user_id: UUID,
        org_id: UUID,
        given_name: Optional[str] = None,
        last_name: Optional[str] = None,
        locale: Optional[str] = None,
        manager_user_id: Optional[UUID] = None,
        actor_id: Optional[UUID] = None,
        obo_by: Optional[UUID] = None,
    ) -> User:
        """
        Update user information.
        
        Args:
            user_id: User ID
            org_id: Organization ID for scoping
            given_name: New given name (optional)
            last_name: New last name (optional)
            locale: New locale (optional)
            manager_user_id: New manager user ID (optional)
            actor_id: User ID of the actor updating the user (for audit logging)
            obo_by: SuperAdmin user ID if this is an on-behalf-of action (for audit logging)
            
        Returns:
            Updated User entity
            
        Raises:
            UserNotFoundError: If user not found
            
        Requirements: 1.4, 1.6, 7.3
        """
        user = await self.get_user_by_id(user_id, org_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        
        # Track changed values for audit log
        changed_values = {}
        
        if given_name is not None:
            changed_values["given_name"] = given_name.strip()
            user.given_name = given_name.strip()
        if last_name is not None:
            changed_values["last_name"] = last_name.strip()
            user.last_name = last_name.strip()
        if locale is not None:
            changed_values["locale"] = locale
            user.locale = locale
        if manager_user_id is not None:
            changed_values["manager_user_id"] = str(manager_user_id)
            user.manager_user_id = manager_user_id
        
        await self.db.flush()
        
        # Write audit log entry if actor_id is provided and there were changes
        if actor_id and changed_values:
            await write_audit_log(
                actor_id=actor_id,
                action="UserUpdated",
                target_entity="User",
                target_id=user_id,
                org_id=org_id,
                changed_values=changed_values,
                obo_by=obo_by,
                timestamp=datetime.now(timezone.utc),
                db=self.db,
            )
        
        return user

    async def get_user_by_id(
        self, user_id: UUID, org_id: UUID
    ) -> Optional[User]:
        """
        Get a user by ID within an organization.
        
        Args:
            user_id: User ID
            org_id: Organization ID for scoping
            
        Returns:
            User entity or None if not found
        """
        stmt = (
            select(User)
            .where(User.user_id == user_id, User.organization_id == org_id)
            .options(selectinload(User.user_roles))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(
        self,
        org_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        """
        List users in an organization with pagination.
        
        Args:
            org_id: Organization ID
            page: Page number (1-indexed)
            page_size: Number of users per page (max 100)
            
        Returns:
            Tuple of (users, total_count)
            
        Requirements: 1.6
        """
        # Enforce max page size
        page_size = min(page_size, 100)
        
        # Get total count
        count_stmt = select(User).where(User.organization_id == org_id)
        count_result = await self.db.execute(count_stmt)
        total_count = len(count_result.scalars().all())
        
        # Get paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(User)
            .where(User.organization_id == org_id)
            .offset(offset)
            .limit(page_size)
            .options(selectinload(User.user_roles))
        )
        result = await self.db.execute(stmt)
        users = cast(list[User], result.scalars().all())  # type: ignore[arg-type]  # type: ignore[assignment]
        
        return users, total_count

    async def lock_user(self, user_id: UUID, org_id: UUID) -> User:
        """
        Lock a user account (set status to Locked).
        
        Uses VersionMixin optimistic locking with retry on StaleDataError.
        
        Args:
            user_id: User ID
            org_id: Organization ID for scoping
            
        Returns:
            Locked User entity
            
        Raises:
            UserNotFoundError: If user not found
            
        Requirements: 1.9
        """
        max_retries = 3
        for attempt in range(max_retries):
            user = await self.get_user_by_id(user_id, org_id)
            if not user:
                raise UserNotFoundError(f"User {user_id} not found")
            
            user.status = UserStatus.LOCKED  # type: ignore[assignment]
            
            try:
                await self.db.flush()
                return user
            except Exception as e:
                # Check if it's a stale data error (version mismatch)
                if "version" in str(e).lower() and attempt < max_retries - 1:
                    # Refresh and retry
                    await self.db.refresh(user)
                    continue
                raise

    async def get_password_history(
        self, user_id: UUID, limit: int = 5
    ) -> list[PasswordHistory]:
        """
        Get password history for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of entries to return (default 5)
            
        Returns:
            List of PasswordHistory entries (most recent first)
            
        Requirements: 1.8
        """
        stmt = (
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return cast(list[PasswordHistory], result.scalars().all())  # type: ignore[assignment]  # type: ignore[assignment]

    async def add_password_history(
        self, user_id: UUID, hashed_password: str
    ) -> PasswordHistory:
        """
        Add a password to the user's password history.
        
        Args:
            user_id: User ID
            hashed_password: Bcrypt-hashed password
            
        Returns:
            Created PasswordHistory entry
            
        Requirements: 1.8
        """
        entry = PasswordHistory(
            user_id=user_id,
            hashed_password=hashed_password,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def _get_user_by_email_hash(
        self, email_hash: str, org_id: UUID
    ) -> Optional[User]:
        """
        Look up a user by email hash within an organization.
        
        Args:
            email_hash: SHA-256 hash of lowercase email
            org_id: Organization ID for scoping
            
        Returns:
            User entity or None if not found
        """
        stmt = select(User).where(
            User.organization_id == org_id, User.email_hash == email_hash
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user that already exists."""

    pass


class UserNotFoundError(Exception):
    """Raised when a user is not found."""

    pass
