"""
PasswordResetToken ORM model for single-use password reset tokens.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.10
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.base_model import Base


class PasswordResetToken(Base):
    """
    Single-use password reset token for forgotten password recovery.

    When a user requests a password reset, a PasswordResetToken is generated
    and sent to their registered email address. The user submits the token
    along with a new password to reset their account credentials.

    Fields:
    - password_reset_token_id: UUID primary key
    - user_id: FK to users.user_id
    - token_hash: SHA-256 hash of the plain-text token (UNIQUE)
    - expires_at: Timestamp 15 minutes from issuance
    - is_used: Boolean flag; set to True when token is successfully used
    - created_at: Timestamp of token generation

    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.10
    """

    __tablename__ = "password_reset_tokens"

    password_reset_token_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    token_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 hex
    expires_at = Column(DateTime(timezone=True), nullable=False)  # 15 minutes from issuance
    is_used = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User")
