"""
JobPosting ORM model stub.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).
"""

import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

from app.base_model import AuditMixin, Base, VersionMixin


class JobPosting(Base, AuditMixin, VersionMixin):
    """
    JobPosting entity stub.

    Requirements: 7.1, 7.5
    """

    __tablename__ = "job_postings"

    posting_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)
