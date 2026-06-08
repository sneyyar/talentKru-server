"""Email configuration models (Req 6.1, 6.2)."""

import enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE, BOOLEAN

from app.base_model import Base, AuditMixin, VersionMixin


class ProviderType(str, enum.Enum):
    """Email provider type."""
    SMTP = "SMTP"
    SENDGRID = "SENDGRID"
    SES = "SES"


class OrganizationEmailConfig(Base, AuditMixin, VersionMixin):
    """Organization-level email configuration (Req 6.2)."""
    __tablename__ = "organization_email_configs"

    organization_email_config_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False, unique=True)
    email_notifications_enabled = Column(BOOLEAN, nullable=False, default=True)
    provider_type = Column(String(50), nullable=False)  # type: ignore[var-annotated]
    smtp_host = Column(String(253), nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_username = Column(String(254), nullable=True)
    smtp_password = Column(String(512), nullable=True)
    smtp_use_tls = Column(BOOLEAN, nullable=True)
    third_party_api_key = Column(String(512), nullable=True)
    third_party_provider_region = Column(String(100), nullable=True)
    from_address = Column(String(254), nullable=False)
    from_name = Column(String(100), nullable=False)

    __table_args__ = (
        CheckConstraint("provider_type IN ('SMTP', 'SENDGRID', 'SES')", name="ck_provider_type"),
    )


class SystemSetting(Base, AuditMixin):
    """System-wide settings (Req 6.1)."""
    __tablename__ = "system_settings"

    setting_key = Column(String(500), primary_key=True)
    setting_value = Column(String(2000), nullable=False)
    description = Column(String(1000), nullable=True)
