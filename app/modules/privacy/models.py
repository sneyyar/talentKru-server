"""Privacy and GDPR compliance ORM models."""

import enum
import uuid
from sqlalchemy import Column, String, DateTime, Integer, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from app.base_model import AuditMixin, Base


class DSARRequestType(str, enum.Enum):
    """Data Subject Access Request type enumeration."""
    ACCESS = "ACCESS"
    ERASURE = "ERASURE"


class DSARStatus(str, enum.Enum):
    """Data Subject Access Request status enumeration."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"


class DataSubjectAccessRequest(Base, AuditMixin):
    """Data Subject Access Request entity."""

    __tablename__ = "data_subject_access_requests"

    dsar_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), nullable=False)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    request_type = Column(String(20), nullable=False)  # type: ignore[var-annotated]
    status = Column(String(20), nullable=False, default=DSARStatus.PENDING.value)  # type: ignore[var-annotated]
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    denial_reason = Column(String(1000), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "request_type IN ('ACCESS', 'ERASURE')",
            name="ck_data_subject_access_requests_request_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'DENIED')",
            name="ck_data_subject_access_requests_status",
        ),
    )


class OrganizationRetentionPolicy(Base, AuditMixin):
    """Organization retention policy entity."""

    __tablename__ = "organization_retention_policies"

    organization_retention_policy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    candidate_data_retention_days = Column(Integer, nullable=False, default=730)
    resume_retention_days = Column(Integer, nullable=False, default=365)
    audit_log_retention_days = Column(Integer, nullable=False, default=2555)

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_organization_retention_policy"),
    )
