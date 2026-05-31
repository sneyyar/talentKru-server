"""
JobProfile ORM models.

Inherits Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).

Requirement 4.1: Job Profile and Job Posting Management
- Stores JobProfile entities with required and desired skills
- Supports skill designation (required or desired) with proficiency levels
"""

import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.base_model import AuditMixin, Base, VersionMixin


class SkillDesignation(str, enum.Enum):
    """Skill designation enumeration for job profiles.
    
    Requirement 4.1: Designation values for skills in job profiles.
    """

    REQUIRED = "required"
    DESIRED = "desired"


class JobProfile(Base, AuditMixin, VersionMixin):
    """
    JobProfile entity.

    Requirements: 4.1, 7.1, 7.5
    
    Stores job profile definitions with:
    - Organization scoping
    - Name for the job profile
    - Associated required and desired skills
    """

    __tablename__ = "job_profiles"

    job_profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Org-scoping — required by the org-scoped query helper
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.organization_id"), nullable=False
    )
    
    # Job profile name
    name = Column(String(200), nullable=False)


class JobProfileSkill(Base, AuditMixin):
    """
    Job profile skill entity.
    
    Requirements: 4.1
    
    Links skills to job profiles with:
    - Designation (required or desired)
    - Required proficiency rank (1-5)
    """

    __tablename__ = "job_profile_skills"

    job_profile_skill_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    job_profile_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("job_profiles.job_profile_id"), 
        nullable=False
    )
    
    skill_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("skills.skill_id"), 
        nullable=False
    )
    
    # Designation: required or desired
    designation = Column(
        SQLEnum(SkillDesignation, native_enum=True),
        nullable=False,
        default=SkillDesignation.REQUIRED,
    )  # type: ignore[var-annotated]
    
    # Required proficiency rank: 1-5
    required_proficiency_rank = Column(Integer, nullable=False)

    __table_args__ = (
        # Unique constraint: one skill per job profile
        UniqueConstraint(
            "job_profile_id", "skill_id", name="uq_job_profile_skills"
        ),
        # Check constraint: proficiency rank must be 1-5
        CheckConstraint(
            "required_proficiency_rank >= 1 AND required_proficiency_rank <= 5",
            name="ck_job_profile_skills_proficiency_rank",
        ),
    )
