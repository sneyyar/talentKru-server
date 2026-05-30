"""
InvitationToken ORM model for single-use account setup tokens.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.base_model import Base


class InvitationToken(Base):
    """
    Single-use invitation token for new user account setup.

    When an administrator creates a new user, an InvitationToken is generated
    and sent to the user's email. The user submits the token along with a new
    password to activate their account and set their status to Active.

    Fields:
    - invitation_token_id: UUID primary key
    - user_id: FK to users.user_id
    - token_hash: SHA-256 hash of the plain-text token (UNIQUE)
    - expires_at: Timestamp 72 hours from issuance
    - is_used: Boolean flag; set to True when token is successfully used
    - created_at: Timestamp of token generation

    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
    """

    __tablename__ = "invitation_tokens"

    invitation_token_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    token_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 hex
    expires_at = Column(DateTime(timezone=True), nullable=False)  # 72 hours from issuance
    is_used = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User")
