"""
JobRequisition ORM model.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).
"""

import enum
import uuid
from sqlalchemy import Column, String, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from app.base_model import AuditMixin, Base, VersionMixin


class RequisitionStatus(str, enum.Enum):
    """Requisition status enumeration."""
    Open = "Open"
    OnHold = "OnHold"
    Closed = "Closed"
    Cancelled = "Cancelled"


class JobRequisition(Base, AuditMixin, VersionMixin):
    """
    JobRequisition entity.

    Requirements: 5.1, 5.2
    """

    __tablename__ = "job_requisitions"

    job_requisition_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    job_profile_id = Column(UUID(as_uuid=True), nullable=False)
    external_requisition_id = Column(String(255), nullable=True)
    title = Column(String(200), nullable=False)
    department = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False)
    hiring_manager_user_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(SQLEnum(RequisitionStatus, native_enum=True), nullable=False, default=RequisitionStatus.Open)
    description = Column(String(5000), nullable=True)


class CandidateRequisition(Base, AuditMixin):
    """Candidate requisition association entity."""

    __tablename__ = "candidate_requisitions"

    candidate_requisition_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), nullable=False)
    job_requisition_id = Column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("candidate_id", "job_requisition_id", name="uq_candidate_requisition"),
    )
