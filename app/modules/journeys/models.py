"""Interview journey data models."""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE, BOOLEAN

from app.base_model import Base, AuditMixin, VersionMixin


class JourneyStage(str, enum.Enum):
    """Interview journey stage."""
    SOURCED = "SOURCED"
    RECRUITER_SCREEN = "RECRUITER_SCREEN"
    MANAGER_SCREEN = "MANAGER_SCREEN"
    LOOP_INTERVIEW = "LOOP_INTERVIEW"
    PANEL_REVIEW = "PANEL_REVIEW"
    OFFER_PENDING = "OFFER_PENDING"
    OFFER_EXTENDED = "OFFER_EXTENDED"
    REJECTED = "REJECTED"
    OFFER_DECLINED = "OFFER_DECLINED"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    WITHDRAWN = "WITHDRAWN"


class JourneyStageStatus(str, enum.Enum):
    """Sub-status for non-terminal interview stages."""
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"


class JourneyOverallStatus(str, enum.Enum):
    """Overall journey status."""
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InterviewJourney(Base, AuditMixin, VersionMixin):
    """Interview journey for a candidate on a requisition (Req 1.1)."""
    __tablename__ = "interview_journeys"

    interview_journey_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False, index=True)
    journey_public_id = Column(String(64), nullable=False, unique=True)
    candidate_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    job_requisition_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    current_stage = Column(
        String(50),
        nullable=False,
        default=JourneyStage.SOURCED.value,
    )  # type: ignore[var-annotated]
    current_stage_status = Column(String(50), nullable=True)  # type: ignore[var-annotated]
    overall_status = Column(
        String(50),
        nullable=False,
        default=JourneyOverallStatus.ACTIVE.value,
    )  # type: ignore[var-annotated]
    offer_extended_at = Column(DateTime(timezone=True), nullable=True)
    offer_responded_at = Column(DateTime(timezone=True), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "current_stage IN ('SOURCED', 'RECRUITER_SCREEN', 'MANAGER_SCREEN', 'LOOP_INTERVIEW', "
            "'PANEL_REVIEW', 'OFFER_PENDING', 'OFFER_EXTENDED', 'REJECTED', 'OFFER_DECLINED', "
            "'OFFER_ACCEPTED', 'WITHDRAWN')",
            name="ck_interview_journeys_current_stage",
        ),
        CheckConstraint(
            "current_stage_status IS NULL OR "
            "current_stage_status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETE')",
            name="ck_interview_journeys_stage_status",
        ),
        CheckConstraint(
            "overall_status IN ('ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED')",
            name="ck_interview_journeys_overall_status",
        ),
        Index("idx_journeys_org_stage", "organization_id", "current_stage"),
        Index("idx_journeys_candidate", "candidate_id"),
    )


class InterviewJourneyStageHistory(Base, AuditMixin):
    """History of stage transitions for a journey (Req 1.4)."""
    __tablename__ = "interview_journey_stage_history"

    interview_journey_stage_history_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    interview_journey_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    from_stage = Column(String(50), nullable=False)
    to_stage = Column(String(50), nullable=False)
    changed_by_user_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False)
    comments = Column(String(2000), nullable=True)

    __table_args__ = (
        Index("idx_stage_history_journey", "interview_journey_id"),
    )


class CandidateInterviewJourney(Base, AuditMixin):
    """Join table linking candidates to journeys (encrypted on OfferAccepted, Req 1.6)."""
    __tablename__ = "candidate_interview_journeys"

    candidate_interview_journey_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    interview_journey_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    candidate_id_encrypted = Column(String(512), nullable=True)
    interview_journey_id_encrypted = Column(String(512), nullable=True)
    is_encrypted = Column(BOOLEAN, nullable=False, default=False)
    associated_at = Column(DateTime(timezone=True), nullable=False)
