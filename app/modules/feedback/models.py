"""Interview feedback models (Req 3.1)."""

import enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE, JSON

from app.base_model import Base, AuditMixin, VersionMixin


class FeedbackType(str, enum.Enum):
    """Feedback type."""
    MANUAL = "MANUAL"
    AI_GENERATED = "AI_GENERATED"


class FeedbackStatus(str, enum.Enum):
    """Feedback status."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class HiringRecommendation(str, enum.Enum):
    """Hiring recommendation."""
    STRONG_YES = "STRONG_YES"
    YES = "YES"
    NEUTRAL = "NEUTRAL"
    NO = "NO"
    STRONG_NO = "STRONG_NO"


class InterviewFeedback(Base, AuditMixin, VersionMixin):
    """Interview feedback (Req 3.1)."""
    __tablename__ = "interview_feedback"

    interview_feedback_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    interview_slot_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    type = Column(String(50), nullable=False, default=FeedbackType.MANUAL.value)  # type: ignore[var-annotated]
    status = Column(String(50), nullable=False, default=FeedbackStatus.DRAFT.value)  # type: ignore[var-annotated]
    competency_ratings = Column(JSON, nullable=True)
    narrative = Column(String(5000), nullable=True)
    hiring_recommendation = Column(String(50), nullable=True)  # type: ignore[var-annotated]

    __table_args__ = (
        CheckConstraint("type IN ('MANUAL', 'AI_GENERATED')", name="ck_feedback_type"),
        CheckConstraint("status IN ('DRAFT', 'SUBMITTED')", name="ck_feedback_status"),
        CheckConstraint(
            "hiring_recommendation IS NULL OR hiring_recommendation IN "
            "('STRONG_YES', 'YES', 'NEUTRAL', 'NO', 'STRONG_NO')",
            name="ck_hiring_recommendation",
        ),
        Index("idx_feedback_slot", "interview_slot_id"),
    )
