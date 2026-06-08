"""Interview slot models (Req 2.1, 2.8)."""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE, ARRAY, JSON, BOOLEAN

from app.base_model import Base, AuditMixin, VersionMixin


class SlotType(str, enum.Enum):
    """Interview slot type."""
    MANAGER = "MANAGER"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    PANEL = "PANEL"


class SlotStatus(str, enum.Enum):
    """Interview slot status."""
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class InvitationStatus(str, enum.Enum):
    """Interviewer invitation status."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class AttendanceStatus(str, enum.Enum):
    """Interview attendance status."""
    UNKNOWN = "UNKNOWN"
    ATTENDED = "ATTENDED"
    NO_SHOW = "NO_SHOW"


class InterviewSlot(Base, AuditMixin, VersionMixin):
    """Interview slot (Req 2.1)."""
    __tablename__ = "interview_slots"

    interview_slot_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False, index=True)
    interview_journey_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    type = Column(String(50), nullable=False)  # type: ignore[var-annotated]
    scheduled_start = Column(DateTime(timezone=True), nullable=False)
    scheduled_end = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default=SlotStatus.SCHEDULED.value)  # type: ignore[var-annotated]
    invitation_status = Column(String(50), nullable=True)  # type: ignore[var-annotated]
    attendance_status = Column(String(50), nullable=False, default=AttendanceStatus.UNKNOWN.value)  # type: ignore[var-annotated]
    interviewer_user_id = Column(UUID_TYPE(as_uuid=True), nullable=True)
    feedback_id = Column(UUID_TYPE(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint("type IN ('MANAGER', 'TECHNICAL', 'BEHAVIORAL', 'PANEL')", name="ck_interview_slots_type"),
        CheckConstraint(
            "status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETE', 'CANCELLED')",
            name="ck_interview_slots_status",
        ),
        CheckConstraint(
            "invitation_status IS NULL OR invitation_status IN ('PENDING', 'ACCEPTED', 'DECLINED')",
            name="ck_interview_slots_invitation_status",
        ),
        CheckConstraint(
            "attendance_status IN ('UNKNOWN', 'ATTENDED', 'NO_SHOW')",
            name="ck_interview_slots_attendance_status",
        ),
        Index("idx_slots_journey", "interview_journey_id"),
        Index("idx_slots_interviewer", "interviewer_user_id"),
    )


class InterviewerPreference(Base, AuditMixin, VersionMixin):
    """Interviewer scheduling preferences (Req 2.8)."""
    __tablename__ = "interviewer_preferences"

    interviewer_preference_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    interviewer_user_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    allowed_interview_types = Column(ARRAY(String(50)), nullable=False)
    max_interviews_per_day = Column(Integer, nullable=False, default=5)
    max_interviews_per_week = Column(Integer, nullable=False, default=20)
    working_hours = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("interviewer_user_id", "organization_id", name="uk_interviewer_org"),
        CheckConstraint("max_interviews_per_day >= 1 AND max_interviews_per_day <= 20", name="ck_max_per_day"),
        CheckConstraint("max_interviews_per_week >= 1 AND max_interviews_per_week <= 100", name="ck_max_per_week"),
    )
