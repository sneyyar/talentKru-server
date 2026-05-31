"""
Skills taxonomy ORM models.

Provides:
- SkillSource(str, enum.Enum): MANUAL, PARSED, INFERRED
- Domain(Base, AuditMixin): skill domain/category
- Skill(Base, AuditMixin): individual skill with domain association
- CandidateSkill(Base, AuditMixin): candidate proficiency and experience
- RequisitionRequiredSkill(Base, AuditMixin): job requisition skill requirements
- UnmatchedSkillReview(Base, AuditMixin): flagged unmatched skills for manual review

Requirements: 3.1, 3.2, 3.3
"""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.base_model import AuditMixin, Base


class SkillSource(str, enum.Enum):
    """Source of skill data: manual entry, parsed from resume, or inferred."""

    MANUAL = "manual"
    PARSED = "parsed"
    INFERRED = "inferred"


class Domain(Base, AuditMixin):
    """
    Skill domain/category entity.

    Requirements: 3.1
    """

    __tablename__ = "domains"

    domain_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)

    # Relationships
    skills = relationship("Skill", back_populates="domain")


class Skill(Base, AuditMixin):
    """
    Individual skill entity with domain association.

    Requirements: 3.1
    """

    __tablename__ = "skills"

    skill_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(
        UUID(as_uuid=True), ForeignKey("domains.domain_id"), nullable=False
    )
    name = Column(String(100), nullable=False)

    # Relationships
    domain = relationship("Domain", back_populates="skills")
    candidate_skills = relationship("CandidateSkill", back_populates="skill")
    requisition_required_skills = relationship(
        "RequisitionRequiredSkill", back_populates="skill"
    )

    __table_args__ = (
        UniqueConstraint("domain_id", "name", name="uq_skills_domain_name"),
    )


class CandidateSkill(Base, AuditMixin):
    """
    Candidate skill proficiency and experience tracking.

    Requirements: 3.2
    """

    __tablename__ = "candidate_skills"

    candidate_skill_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), nullable=False)
    skill_id = Column(
        UUID(as_uuid=True), ForeignKey("skills.skill_id"), nullable=False
    )
    proficiency_rank = Column(Integer, nullable=False)
    years_of_experience = Column(Integer, nullable=False)
    source = Column(
        SQLEnum(SkillSource, native_enum=True),
        nullable=False,
        default=SkillSource.MANUAL,
    )

    # Relationships
    skill = relationship("Skill", back_populates="candidate_skills")

    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "skill_id", name="uq_candidate_skills_candidate_skill"
        ),
        CheckConstraint(
            "proficiency_rank >= 1 AND proficiency_rank <= 5",
            name="ck_candidate_skills_proficiency_rank",
        ),
        CheckConstraint(
            "years_of_experience >= 0 AND years_of_experience <= 50",
            name="ck_candidate_skills_years_of_experience",
        ),
    )


class RequisitionRequiredSkill(Base, AuditMixin):
    """
    Job requisition required skill with proficiency level and weight.

    Requirements: 3.3
    """

    __tablename__ = "requisition_required_skills"

    requisition_required_skill_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_requisition_id = Column(UUID(as_uuid=True), nullable=False)
    skill_id = Column(
        UUID(as_uuid=True), ForeignKey("skills.skill_id"), nullable=False
    )
    required_proficiency_rank = Column(Integer, nullable=False)
    weight = Column(Integer, nullable=False)

    # Relationships
    skill = relationship("Skill", back_populates="requisition_required_skills")

    __table_args__ = (
        UniqueConstraint(
            "job_requisition_id",
            "skill_id",
            name="uq_requisition_required_skills_requisition_skill",
        ),
        CheckConstraint(
            "required_proficiency_rank >= 1 AND required_proficiency_rank <= 5",
            name="ck_requisition_required_skills_proficiency_rank",
        ),
        CheckConstraint(
            "weight >= 1 AND weight <= 10",
            name="ck_requisition_required_skills_weight",
        ),
    )


class UnmatchedSkillReview(Base, AuditMixin):
    """
    Flagged unmatched skills from resume parsing for manual taxonomy review.

    Requirements: 3.3
    """

    __tablename__ = "unmatched_skill_reviews"

    unmatched_skill_review_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id = Column(UUID(as_uuid=True), nullable=False)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    unmatched_skill_name = Column(String(200), nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
