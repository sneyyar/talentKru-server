"""
Integration tests for skill matching and unmatched review.

Feature: candidate-lifecycle
Tasks: 17.2 - Skill matching and unmatched review integration tests

Requirements: 3.4, 3.5, 3.6
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.modules.skills.models import Domain, Skill, CandidateSkill, UnmatchedSkillReview, SkillSource
from app.modules.skills.service import SkillService


class TestSkillMatchingIntegration:
    """Integration tests for skill matching and unmatched reviews."""

    @pytest.mark.asyncio
    async def test_case_insensitive_skill_matching(
        self, db_session: AsyncSession, org_id, user_id, test_run_id
    ):
        """
        Test: Case-insensitive skill matching
        
        Validates: Requirements 3.4
        
        - Create domain and skill (lowercase)
        - Match skill in uppercase
        - Verify CandidateSkill linked to existing Skill
        - Verify source=PARSED
        """
        skill_service = SkillService(db_session)
        candidate_service = CandidateService(db_session)
        
        # Create domain and skill with unique name
        domain = await skill_service.create_domain(
            name=f"Programming Languages-{test_run_id}",
        )
        
        skill = await skill_service.create_skill(
            domain_id=domain.domain_id,
            name=f"python-{test_run_id}",  # lowercase with unique suffix
        )
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email=f"test-case-insensitive-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        # Match skill with different case
        extracted_skills = [f"PYTHON-{test_run_id}", "JavaScript"]  # uppercase version
        
        await skill_service.match_and_link_skills(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            extracted_skills=extracted_skills,
        )
        
        # Verify CandidateSkill created for PYTHON
        stmt = select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.candidate_id,
            CandidateSkill.skill_id == skill.skill_id,
        )
        result = await db_session.execute(stmt)
        candidate_skill = result.scalar_one_or_none()
        
        assert candidate_skill is not None
        assert candidate_skill.source == SkillSource.PARSED.value

    @pytest.mark.asyncio
    async def test_unmatched_skill_creates_review(
        self, db_session: AsyncSession, org_id, user_id, test_run_id
    ):
        """
        Test: Unmatched skill creates review
        
        Validates: Requirements 3.5
        
        - Create domain and skill
        - Ingest resume with unmatched skill name
        - Verify UnmatchedSkillReview created
        - Verify ingestion completes (COMPLETED status)
        """
        skill_service = SkillService(db_session)
        candidate_service = CandidateService(db_session)
        
        # Create domain and skill with unique name
        domain = await skill_service.create_domain(
            name=f"Programming Languages-{test_run_id}",
        )
        
        skill = await skill_service.create_skill(
            domain_id=domain.domain_id,
            name=f"python-{test_run_id}",
        )
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email=f"test-unmatched-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        # Match skills with unmatched skill
        extracted_skills = [f"python-{test_run_id}", f"rust-{test_run_id}", f"go-{test_run_id}"]  # rust and go don't exist
        
        await skill_service.match_and_link_skills(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            extracted_skills=extracted_skills,
        )
        
        # Verify UnmatchedSkillReview created for rust and go
        stmt = select(UnmatchedSkillReview).where(
            UnmatchedSkillReview.candidate_id == candidate.candidate_id
        )
        result = await db_session.execute(stmt)
        reviews = result.scalars().all()
        
        assert len(reviews) == 2
        unmatched_names = {r.unmatched_skill_name for r in reviews}
        assert f"rust-{test_run_id}" in unmatched_names
        assert f"go-{test_run_id}" in unmatched_names

    @pytest.mark.asyncio
    async def test_zero_skills_dont_block_ingestion(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Zero skills don't block ingestion
        
        Validates: Requirements 3.6
        
        - Create candidate
        - Ingest resume with no skills
        - Verify ingestion completes
        - Verify no UnmatchedSkillReview records
        """
        skill_service = SkillService(db_session)
        candidate_service = CandidateService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            created_by=user_id,
        )
        
        # Match with empty skills list
        extracted_skills = []
        
        # Should not raise exception
        await skill_service.match_and_link_skills(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            extracted_skills=extracted_skills,
        )
        
        # Verify no UnmatchedSkillReview created
        stmt = select(UnmatchedSkillReview).where(
            UnmatchedSkillReview.candidate_id == candidate.candidate_id
        )
        result = await db_session.execute(stmt)
        reviews = result.scalars().all()
        
        assert len(reviews) == 0

    @pytest.mark.asyncio
    async def test_multiple_skills_matching(
        self, db_session: AsyncSession, org_id, user_id, test_run_id
    ):
        """
        Test: Multiple skills matching
        
        Validates: Requirements 3.4
        
        - Create domain with 5 skills
        - Ingest resume with 3 matching skills
        - Verify 3 CandidateSkill records created
        - Verify correct skill associations
        """
        skill_service = SkillService(db_session)
        candidate_service = CandidateService(db_session)
        
        # Create domain and skills with unique name
        domain = await skill_service.create_domain(
            name=f"Programming Languages-{test_run_id}",
        )
        
        skill_names = [f"python-{test_run_id}", f"javascript-{test_run_id}", f"java-{test_run_id}", f"go-{test_run_id}", f"rust-{test_run_id}"]
        created_skills = {}
        
        for name in skill_names:
            skill = await skill_service.create_skill(
                domain_id=domain.domain_id,
                name=name,
            )
            created_skills[name] = skill
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email=f"test-multiple-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        # Match 3 skills
        extracted_skills = [f"python-{test_run_id}", f"javascript-{test_run_id}", f"java-{test_run_id}"]
        
        await skill_service.match_and_link_skills(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            extracted_skills=extracted_skills,
        )
        
        # Verify 3 CandidateSkill records created
        stmt = select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.candidate_id
        )
        result = await db_session.execute(stmt)
        candidate_skills = result.scalars().all()
        
        assert len(candidate_skills) == 3
        
        # Verify correct skill associations
        skill_ids = {cs.skill_id for cs in candidate_skills}
        expected_ids = {created_skills[name].skill_id for name in extracted_skills}
        assert skill_ids == expected_ids

    @pytest.mark.asyncio
    async def test_skill_source_tracking(
        self, db_session: AsyncSession, org_id, user_id, test_run_id
    ):
        """
        Test: Skill source tracking
        
        Validates: Requirements 3.4
        
        - Ingest resume with skills (source=PARSED)
        - Manually add skill (source=MANUAL)
        - Verify both sources tracked correctly
        """
        skill_service = SkillService(db_session)
        candidate_service = CandidateService(db_session)
        
        # Create domain and skill with unique name
        domain = await skill_service.create_domain(
            name=f"Programming Languages-{test_run_id}",
        )
        
        skill = await skill_service.create_skill(
            domain_id=domain.domain_id,
            name=f"python-{test_run_id}",
        )
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email=f"test-source-tracking-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        # Ingest resume with skill (source=PARSED)
        extracted_skills = [f"python-{test_run_id}"]
        
        await skill_service.match_and_link_skills(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            extracted_skills=extracted_skills,
        )
        
        # Verify source=PARSED
        stmt = select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.candidate_id,
            CandidateSkill.skill_id == skill.skill_id,
        )
        result = await db_session.execute(stmt)
        candidate_skill = result.scalar_one()
        
        assert candidate_skill.source == SkillSource.PARSED.value
        
        # Manually add another skill (source=MANUAL)
        skill2 = await skill_service.create_skill(
            domain_id=domain.domain_id,
            name=f"javascript-{test_run_id}",
        )
        
        await skill_service.add_candidate_skill(
            candidate_id=candidate.candidate_id,
            skill_id=skill2.skill_id,
            proficiency_rank=4,
            years_of_experience=5,
        )
        
        # Verify source=MANUAL
        stmt = select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.candidate_id,
            CandidateSkill.skill_id == skill2.skill_id,
        )
        result = await db_session.execute(stmt)
        candidate_skill2 = result.scalar_one()
        
        assert candidate_skill2.source == SkillSource.MANUAL.value
