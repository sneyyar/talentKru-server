"""
Interview ORM model stubs: InterviewSlot, InterviewFeedback, InterviewerPreference.

All three inherit Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1
and 7.5 (optimistic locking on all mutable entities).
"""

import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

from app.base_model import AuditMixin, Base, VersionMixin


class InterviewSlot(Base, AuditMixin, VersionMixin):
    """
    InterviewSlot entity stub.

    Requirements: 7.1, 7.5
    """

    __tablename__ = "interview_slots"

    slot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)


class InterviewFeedback(Base, AuditMixin, VersionMixin):
    """
    InterviewFeedback entity stub.

    Requirements: 7.1, 7.5
    """

    __tablename__ = "interview_feedback"

    feedback_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)


class InterviewerPreference(Base, AuditMixin, VersionMixin):
    """
    InterviewerPreference entity stub.

    Requirements: 7.1, 7.5
    """

    __tablename__ = "interviewer_preferences"

    preference_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)
