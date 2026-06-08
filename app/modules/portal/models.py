"""Candidate portal models (Req 5.1)."""

from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import BOOLEAN
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE

from app.base_model import AuditMixin, Base


class CandidatePortalToken(Base, AuditMixin):
    """Portal token for candidate access (Req 5.1, 5.2)."""

    __tablename__ = "candidate_portal_tokens"

    candidate_portal_token_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(BOOLEAN, nullable=False, default=True)

    __table_args__ = (Index("idx_portal_tokens_candidate", "candidate_id"),)
