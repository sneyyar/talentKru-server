"""
Skills service layer.

Provides business logic for managing skill taxonomy (domains and skills),
matching extracted skills from resumes to the taxonomy, and managing
candidate skill proficiency records.

Requirements: 3.1, 3.2, 3.4, 3.5, 3.6
"""

from uuid import UUID, uuid4
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.decorators import transactional, read_only
from app.modules.skills.models import (
    Domain,
    Skill,
    CandidateSkill,
    SkillSource,
    UnmatchedSkillReview,
)
from app.observability.logging import get_logger

logger = get_logger(__name__)


class SkillService:
    """Service for managing skills and skill taxonomy."""

    def __init__(self, db: AsyncSession):
        """Initialize the service with a database session.
        
        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    @transactional()
    async def create_domain(
        self,
        name: str,
    ) -> Domain:
        """
        Create a new skill domain.

        Enforces name uniqueness across all domains (409 on conflict).

        Args:
            name: Unique domain name.

        Returns:
            The newly created Domain ORM instance.

        Raises:
            HTTPException(409): If a domain with this name already exists.

        Requirements: 3.1
        """
        # Check name uniqueness
        stmt = select(Domain).where(
            Domain.name == name,
            Domain.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A domain with this name already exists",
            )

        domain = Domain(domain_id=uuid4(), name=name)
        self.db.add(domain)
        await self.db.flush()
        return domain

    @transactional()
    async def create_skill(
        self,
        domain_id: UUID,
        name: str,
    ) -> Skill:
        """
        Create a new skill within a domain.

        Enforces (domain_id, name) uniqueness (409 on conflict).

        Args:
            domain_id: UUID of the parent domain.
            name: Unique skill name within the domain.

        Returns:
            The newly created Skill ORM instance.

        Raises:
            HTTPException(409): If a skill with this name already exists in the domain.

        Requirements: 3.1
        """
        # Check (domain_id, name) uniqueness
        stmt = select(Skill).where(
            Skill.domain_id == domain_id,
            Skill.name == name,
            Skill.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A skill with this name already exists in the domain",
            )

        skill = Skill(skill_id=uuid4(), domain_id=domain_id, name=name)
        self.db.add(skill)
        await self.db.flush()
        return skill

    @transactional(name="match_and_link_skills")
    async def match_and_link_skills(
        self,
        candidate_id: UUID,
        org_id: UUID,
        extracted_skills: list[str],
    ) -> None:
        """
        Match extracted skill names against the skill taxonomy and link to candidate.

        For each extracted skill name:
        - Performs case-insensitive lookup: SELECT Skill WHERE func.lower(Skill.name) == skill_name.lower().strip()
        - If matched: upserts CandidateSkill(source=PARSED) with default proficiency_rank=1, years_of_experience=0
        - If unmatched: inserts UnmatchedSkillReview and logs WARNING
        - If zero skills: no-op (ingestion still completes)

        Args:
            candidate_id: UUID of the candidate.
            org_id: UUID of the organization.
            extracted_skills: List of skill names extracted from resume.

        Requirements: 3.4, 3.5, 3.6
        """
        if not extracted_skills:
            # Zero skills → no-op
            return

        for skill_name in extracted_skills:
            # Case-insensitive match
            stmt = select(Skill).where(
                func.lower(Skill.name) == skill_name.lower().strip(),
                Skill.deleted_at.is_(None),
            )
            result = await self.db.execute(stmt)
            skill = result.first()
            if skill:
                skill = skill[0]  # Extract the Skill object from the tuple

            if skill:
                # Matched: upsert CandidateSkill
                existing_stmt = select(CandidateSkill).where(
                    CandidateSkill.candidate_id == candidate_id,
                    CandidateSkill.skill_id == skill.skill_id,
                    CandidateSkill.deleted_at.is_(None),
                )
                existing_result = await self.db.execute(existing_stmt)
                existing = existing_result.scalar_one_or_none()

                if not existing:
                    candidate_skill = CandidateSkill(
                        candidate_skill_id=uuid4(),
                        candidate_id=candidate_id,
                        skill_id=skill.skill_id,
                        proficiency_rank=1,
                        years_of_experience=0,
                        source=SkillSource.PARSED.value,
                    )
                    self.db.add(candidate_skill)
            else:
                # Unmatched: flag for review and log warning
                unmatched_review = UnmatchedSkillReview(
                    unmatched_skill_review_id=uuid4(),
                    candidate_id=candidate_id,
                    organization_id=org_id,
                    unmatched_skill_name=skill_name,
                )
                self.db.add(unmatched_review)
                logger.warning(
                    "unmatched_skill_from_resume",
                    candidate_id=str(candidate_id),
                    skill_name=skill_name,
                )

        await self.db.flush()

    @transactional()
    async def add_candidate_skill(
        self,
        candidate_id: UUID,
        skill_id: UUID,
        proficiency_rank: int,
        years_of_experience: int,
    ) -> CandidateSkill:
        """
        Add a skill to a candidate with proficiency and experience validation.

        Validates:
        - proficiency_rank: 1–5 (422 on violation)
        - years_of_experience: 0–50 (422 on violation)
        - Duplicate check: (candidate_id, skill_id) uniqueness (409 on conflict)

        Args:
            candidate_id: UUID of the candidate.
            skill_id: UUID of the skill.
            proficiency_rank: Proficiency level 1–5.
            years_of_experience: Years of experience 0–50.

        Returns:
            The newly created CandidateSkill ORM instance.

        Raises:
            HTTPException(422): If proficiency_rank or years_of_experience are out of range.
            HTTPException(409): If the candidate already has this skill.

        Requirements: 3.2
        """
        # Validate proficiency_rank
        if not (1 <= proficiency_rank <= 5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="proficiency_rank must be between 1 and 5",
            )

        # Validate years_of_experience
        if not (0 <= years_of_experience <= 50):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="years_of_experience must be between 0 and 50",
            )

        # Check duplicate
        stmt = select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id,
            CandidateSkill.skill_id == skill_id,
            CandidateSkill.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate already has this skill",
            )

        candidate_skill = CandidateSkill(
            candidate_skill_id=uuid4(),
            candidate_id=candidate_id,
            skill_id=skill_id,
            proficiency_rank=proficiency_rank,
            years_of_experience=years_of_experience,
            source=SkillSource.MANUAL.value,
        )
        self.db.add(candidate_skill)
        await self.db.flush()
        return candidate_skill
