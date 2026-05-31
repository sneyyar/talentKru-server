"""
InterviewJourney ORM model.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).
"""

import enum
import uuid

from sqlalchemy import Column, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.base_model import AuditMixin, Base, VersionMixin


class JourneyOverallStatus(str, enum.Enum):
    """Overall status of an interview journey."""

    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InterviewJourney(Base, AuditMixin, VersionMixin):
    """
    InterviewJourney entity.

    Requirements: 7.1, 7.5
    """

    __tablename__ = "interview_journeys"

    interview_journey_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )

    # Candidate reference for expiry check
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("candidates.candidate_id"),
        nullable=False,
    )

    # Overall status for expiry check
    overall_status = Column(
        String(20),
        nullable=False,
        default=JourneyOverallStatus.ACTIVE.value,
    )  # type: ignore[var-annotated]

    __table_args__ = (
        CheckConstraint(
            "overall_status IN ('ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED')",
            name="ck_interview_journeys_overall_status",
        ),
    )
