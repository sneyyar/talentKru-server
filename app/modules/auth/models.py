"""
RefreshToken and RevokedToken ORM models for token management.

Requirements: 4.1, 4.4, 4.7
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.base_model import Base


class RefreshToken(Base):
    """
    Refresh token model for managing long-lived token rotation.

    Stores hashed refresh tokens with expiration, revocation status, and
    token replacement tracking for secure token rotation.

    Requirements: 4.1, 4.4
    """

    __tablename__ = "refresh_tokens"

    refresh_token_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    token_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 hex
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)
    issued_at = Column(DateTime(timezone=True), nullable=False)
    replaced_by_token_id = Column(
        UUID(as_uuid=True),
        ForeignKey("refresh_tokens.refresh_token_id"),
        nullable=True,
    )

    user = relationship("User", back_populates="refresh_tokens")
    replaced_by = relationship("RefreshToken", remote_side=[refresh_token_id])


class RevokedToken(Base):
    """
    Revoked token model for tracking invalidated JWT tokens.

    Stores revoked JWT tokens (by jti claim) with revocation reason and
    expiration for cleanup. Supports logout, status changes, and password resets.

    Requirements: 4.7
    """

    __tablename__ = "revoked_tokens"

    revoked_token_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    jti = Column(String(36), nullable=False, unique=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(
        DateTime(timezone=True), nullable=False
    )  # for cleanup
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    reason = Column(
        String(64), nullable=True
    )  # e.g., "logout", "status_change", "password_reset"
