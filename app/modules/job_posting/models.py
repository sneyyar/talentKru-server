"""
JobPosting ORM model.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).

Requirement 4.2: Job Posting Management
- Stores JobPosting entities with work locations, salary range, and sourcing channel
- Supports filtering by location, salary range overlap, and sourcing channel
"""

import uuid

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.base_model import AuditMixin, Base, VersionMixin


class JobPosting(Base, AuditMixin, VersionMixin):
    """
    JobPosting entity.

    Requirements: 4.2, 7.1, 7.5
    
    Stores job posting details with:
    - Organization scoping
    - Linked JobProfile
    - Job description
    - Work locations (array of strings)
    - Salary range (min/max with currency)
    - Sourcing channel
    - Partial index on salary range for efficient filtering
    """

    __tablename__ = "job_postings"

    job_posting_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Org-scoping — required by the org-scoped query helper
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.organization_id"), nullable=False
    )
    
    # Linked job profile
    job_profile_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("job_profiles.job_profile_id"), 
        nullable=False
    )
    
    # Job description
    description = Column(Text, nullable=False)
    
    # Work locations: array of location strings
    work_locations = Column(ARRAY(String), nullable=False, server_default="{}")
    
    # Salary range: numeric with 2 decimal places (12,2 precision)
    salary_min = Column(Numeric(12, 2), nullable=True)
    salary_max = Column(Numeric(12, 2), nullable=True)
    
    # Salary currency: ISO 4217 code (e.g., USD, EUR, GBP)
    salary_currency = Column(String(3), nullable=True)
    
    # Sourcing channel: where the job was posted (e.g., LinkedIn, Indeed, Internal)
    sourcing_channel = Column(String(100), nullable=True)

    __table_args__ = (
        # Partial index on salary range for efficient filtering (excluding soft-deleted)
        Index(
            "idx_job_postings_salary",
            "organization_id",
            "salary_min",
            "salary_max",
            postgresql_where="deleted_at IS NULL",
        ),
    )
