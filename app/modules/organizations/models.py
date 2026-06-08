"""
Organization ORM models.

Contains:
- Organization: client tenant entity
- OrganizationEmailConfig: per-org email configuration (mutable, versioned)

All models inherit Base, AuditMixin, and VersionMixin to satisfy Requirements
7.1 and 7.5 (optimistic locking on all mutable entities).
"""

import uuid

from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from app.base_model import AuditMixin, Base, VersionMixin


class Organization(Base, AuditMixin, VersionMixin):
    """
    Tenant organization entity.

    Each organization represents an independent client tenant. All data queries
    are scoped by organization_id derived from the authenticated principal.
    The slug must be unique across all organizations and is used in URL paths
    and human-readable identifiers.

    Requirements: 2.1, 2.2, 6.1
    """

    __tablename__ = "organizations"

    # Primary key
    organization_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Core identity
    name = Column(String(128), nullable=False)
    slug = Column(String(64), nullable=False, unique=True, index=True)

    # Branding settings
    logo_url = Column(String(512), nullable=True)
    primary_color = Column(String(7), nullable=True)    # hex color, e.g. "#FF5733"
    secondary_color = Column(String(7), nullable=True)  # hex color
    terms_url = Column(String(512), nullable=True)

    # Primary contact details
    contact_name = Column(String(128), nullable=True)
    contact_email = Column(String(254), nullable=True)  # RFC 5321 max length
    contact_phone = Column(String(32), nullable=True)

    # Feature flags — JSON object of string keys to boolean values
    feature_flags = Column(JSONB, nullable=False, server_default="{}")

    # Shard routing — default 0 (single-shard deployment placeholder)
    shard_id = Column(Integer, nullable=False, default=0)

    # CORS allowed origins — max 20 entries, each max 253 characters (Req 6.1)
    allowed_origins = Column(ARRAY(String(253)), nullable=False, server_default="{}")  # type: ignore[var-annotated]

    # Rate limiting — requests per minute for authenticated endpoints (Req 8.3)
    rate_limit_per_minute = Column(Integer, nullable=False, default=1000)
