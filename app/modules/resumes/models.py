"""Resume and CandidateJobHistory ORM models.

Requirements: 2.1, 2.7
"""

import enum
import uuid
from sqlalchemy import Boolean, Column, Date, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.base_model import AuditMixin, Base, VersionMixin


class ParseStatus(str, enum.Enum):
    """Resume parsing status enumeration."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Resume(Base, AuditMixin, VersionMixin):
    """
    Resume entity for storing uploaded resume files and parsed data.

    Fields:
    - resume_id: UUID primary key
    - candidate_id: FK to candidates (nullable at upload)
    - organization_id: FK to organizations (org-scoped)
    - storage_location: URI to stored file (local:// or s3://)
    - mime_type: MIME type of uploaded file
    - file_name: Original filename
    - file_size_bytes: File size in bytes
    - uploaded_by_user_id: FK to users (who uploaded)
    - is_primary: Boolean flag for primary resume
    - parse_status: Pending, Completed, or Failed
    - parsed_data: JSONB containing extracted data (name, email, phone, job_history, skills)
    - AuditFields: created_at, updated_at, deleted_at, created_by, updated_by, deleted_by

    Requirements: 2.1, 2.7
    """

    __tablename__ = "resumes"

    resume_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id"), nullable=False)
    storage_location = Column(String(1024), nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    parse_status = Column(String(20), nullable=False, default=ParseStatus.PENDING.value)  # type: ignore[var-annotated]
    parsed_data = Column(JSONB, nullable=True)

    # Partial index on candidate_id where deleted_at IS NULL
    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('PENDING', 'COMPLETED', 'FAILED')",
            name="ck_resumes_parse_status",
        ),
        Index("idx_resumes_candidate", "candidate_id", postgresql_where=text("deleted_at IS NULL")),
    )


class CandidateJobHistory(Base, AuditMixin, VersionMixin):
    """
    Job history entry for a candidate extracted from resume or manually entered.

    Fields:
    - candidate_job_history_id: UUID primary key
    - candidate_id: FK to candidates
    - organization_id: FK to organizations (org-scoped)
    - company_name: Name of employer (max 200 characters)
    - job_title: Job title (max 200 characters)
    - start_date: Start date of employment
    - end_date: End date of employment (nullable for current roles)
    - description: Job description (max 2000 characters)
    - is_current: Boolean flag for current employment
    - AuditFields: created_at, updated_at, deleted_at, created_by, updated_by, deleted_by

    Requirements: 2.1, 2.7
    """

    __tablename__ = "candidate_job_history"

    candidate_job_history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id"), nullable=False)
    company_name = Column(String(200), nullable=False)
    job_title = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    description = Column(String(2000), nullable=True)
    is_current = Column(Boolean, nullable=False, default=False)
