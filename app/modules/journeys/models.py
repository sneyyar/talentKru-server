"""
InterviewJourney ORM model.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).
"""

import enum
import uuid

from sqlalchemy import Column, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.base_model import AuditMixin, Base, VersionMixin


class JourneyOverallStatus(str, enum.Enum):
    """Overall status of an interview journey."""

    ACTIVE = "Active"
    ON_HOLD = "OnHold"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


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
        SQLEnum(JourneyOverallStatus, native_enum=True),
        nullable=False,
        default=JourneyOverallStatus.ACTIVE,
    )
