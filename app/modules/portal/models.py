"""Portal ORM models."""

import uuid
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from app.base_model import AuditMixin, Base


class DataSubjectAccessRequest(Base, AuditMixin):
    """Data Subject Access Request entity."""

    __tablename__ = "data_subject_access_requests"

    dsar_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), nullable=False)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
