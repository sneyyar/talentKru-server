"""
Candidate ORM model.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).

Requirement 1.1: Candidate Management
- Stores candidate profiles with encrypted PII (Name, Email, Phone)
- Uses SHA-256 hashes for uniqueness enforcement and exact-match lookups
- Supports GlobalStatus transitions (Active, Interviewing, Expired, Ineligible, Deleted)
- Includes partial indexes for efficient filtering by organization and status
"""

import enum
import uuid

from sqlalchemy import (
    Column,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.base_model import AuditMixin, Base, VersionMixin


class GlobalStatus(str, enum.Enum):
    """Candidate global status enumeration.
    
    Requirement 1.1: GlobalStatus values for candidate lifecycle tracking.
    """

    Active = "Active"
    Interviewing = "Interviewing"
    Expired = "Expired"
    Ineligible = "Ineligible"
    Deleted = "Deleted"


class Candidate(Base, AuditMixin, VersionMixin):
    """
    Candidate entity.

    Requirements: 1.1, 7.1, 7.5
    
    Stores candidate profiles with:
    - Encrypted PII fields (name, email, phone) using AES-256-GCM
    - SHA-256 hashes for uniqueness enforcement and exact-match lookups
    - GlobalStatus for lifecycle tracking
    - Soft delete via deleted_at audit field
    """

    __tablename__ = "candidates"

    candidate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.organization_id"), nullable=False
    )

    # Name fields: encrypted for PII protection, hash for uniqueness/search
    # Max 512 to accommodate AES-256-GCM ciphertext (plaintext max 200 chars)
    name = Column(String(512), nullable=False)
    name_hash = Column(String(64), nullable=False)  # SHA-256 hash

    # Email fields: encrypted for PII protection, hash for uniqueness/search
    # Max 512 to accommodate AES-256-GCM ciphertext (plaintext max 254 chars)
    email = Column(String(512), nullable=False)
    email_hash = Column(String(64), nullable=False)  # SHA-256 hash

    # Phone field: encrypted for PII protection, nullable
    # Max 200 to accommodate AES-256-GCM ciphertext (plaintext max 50 chars)
    phone = Column(String(200), nullable=True)

    # Location: not encrypted, nullable
    location = Column(String(200), nullable=True)

    # Global status for lifecycle tracking
    global_status = Column(
        SQLEnum(GlobalStatus, native_enum=True),
        nullable=False,
        default=GlobalStatus.Active,
    )

    # Ineligibility reason: required when status is set to Ineligible
    ineligibility_reason = Column(String(1000), nullable=True)

    __table_args__ = (
        # Unique constraint: email_hash per organization
        UniqueConstraint(
            "organization_id", "email_hash", name="uq_candidates_org_email"
        ),
        # Partial index: candidates by organization and status (excluding soft-deleted)
        Index(
            "idx_candidates_org_status",
            "organization_id",
            "global_status",
            postgresql_where="deleted_at IS NULL",
        ),
        # Partial index: candidates by organization and name_hash (excluding soft-deleted)
        Index(
            "idx_candidates_name_hash",
            "organization_id",
            "name_hash",
            postgresql_where="deleted_at IS NULL",
        ),
    )
