"""
User and PasswordHistory ORM models.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).
"""

import enum
import uuid

from sqlalchemy import (
    Column,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.base_model import AuditMixin, Base, VersionMixin


class UserStatus(str, enum.Enum):
    """User account status enumeration."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"
    PENDING_INVITATION = "PENDING_INVITATION"


class User(Base, AuditMixin, VersionMixin):
    """
    User entity.

    Requirements: 1.1, 1.8, 7.1
    """

    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.organization_id"), nullable=True
    )

    # Email fields: stored encrypted; email_hash for uniqueness lookups
    email = Column(String(512), nullable=False)  # 512 to accommodate ciphertext
    email_hash = Column(String(64), nullable=False)  # SHA-256 hash

    # Name fields
    given_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    # Account status
    status = Column(
        String(20),
        nullable=False,
        default=UserStatus.PENDING_INVITATION.value,
    )  # type: ignore[var-annotated]

    # Manager relationship for organizational hierarchy
    manager_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )

    # Password: bcrypt hash, nullable until invitation accepted
    hashed_password = Column(String(60), nullable=True)

    # Failed login tracking
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    last_failed_login_at = Column(DateTime(timezone=True), nullable=True)

    # Locale preference
    locale = Column(String(10), nullable=False, default="en-US")

    # Relationships
    user_roles = relationship(
        "UserRole", back_populates="user", lazy="selectin"
    )
    password_history = relationship(
        "PasswordHistory",
        back_populates="user",
        order_by="PasswordHistory.created_at.desc()",
    )
    refresh_tokens = relationship("RefreshToken", back_populates="user")

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "email_hash", name="uq_users_org_email"
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'LOCKED', 'PENDING_INVITATION')",
            name="ck_users_status",
        ),
    )


class PasswordHistory(Base):
    """
    Password history tracking for audit and security purposes.

    Requirements: 1.8
    """

    __tablename__ = "password_history"

    password_history_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    hashed_password = Column(String(60), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="password_history")
