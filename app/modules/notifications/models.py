"""Notification models (Req 8.7, 8.9)."""

import enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE, BOOLEAN

from app.base_model import Base, AuditMixin, VersionMixin


class NotificationStatus(str, enum.Enum):
    """Notification delivery status."""
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    RETRYING = "RETRYING"
    PERMANENTLY_FAILED = "PERMANENTLY_FAILED"


class NotificationTemplate(Base, AuditMixin, VersionMixin):
    """Notification template for event (Req 8.7)."""
    __tablename__ = "notification_templates"

    notification_template_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    subject = Column(String(200), nullable=False)
    body_template = Column(String(5000), nullable=False)
    is_enabled = Column(BOOLEAN, nullable=False, default=True)
    locale = Column(String(10), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "event_type", "locale", name="uk_template_event_locale"),
    )


class NotificationRecord(Base, AuditMixin):
    """Notification delivery record (Req 8.9)."""
    __tablename__ = "notification_records"

    notification_record_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    event_type = Column(String(100), nullable=False)
    recipient_email = Column(String(254), nullable=False)
    status = Column(String(50), nullable=False, default=NotificationStatus.PENDING.value)  # type: ignore[var-annotated]
    attempt_count = Column(Integer, nullable=False, default=0)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'DELIVERED', 'RETRYING', 'PERMANENTLY_FAILED')",
            name="ck_notification_status",
        ),
    )
