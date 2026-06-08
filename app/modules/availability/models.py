"""Candidate availability models (Req 7.1)."""

import enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    DateTime,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE

from app.base_model import Base, AuditMixin


class AvailabilityInterviewType(str, enum.Enum):
    """Interview type for availability."""
    RECRUITER_SCREEN = "RECRUITER_SCREEN"
    MANAGER_SCREEN = "MANAGER_SCREEN"
    LOOP_INTERVIEW = "LOOP_INTERVIEW"


class AvailabilityStatus(str, enum.Enum):
    """Availability slot status."""
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class CandidateAvailabilitySlot(Base, AuditMixin):
    """Candidate availability slot (Req 7.1)."""
    __tablename__ = "candidate_availability_slots"

    candidate_availability_slot_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    interview_type = Column(String(50), nullable=False)  # type: ignore[var-annotated]
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default=AvailabilityStatus.ACTIVE.value)  # type: ignore[var-annotated]

    __table_args__ = (
        CheckConstraint(
            "interview_type IN ('RECRUITER_SCREEN', 'MANAGER_SCREEN', 'LOOP_INTERVIEW')",
            name="ck_interview_type",
        ),
        CheckConstraint("status IN ('ACTIVE', 'CANCELLED')", name="ck_availability_status"),
    )
