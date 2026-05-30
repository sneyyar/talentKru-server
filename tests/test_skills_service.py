"""
Unit and property-based tests for SkillService.

Tests the following service methods:
  - create_domain: name uniqueness (409 on conflict)
  - create_skill: (domain_id, name) uniqueness (409 on conflict)
  - match_and_link_skills: case-insensitive matching, unmatched review, zero skills no-op
  - add_candidate_skill: proficiency_rank 1–5, years_of_experience 0–50, duplicate check

Requirements: 3.1, 3.2, 3.4, 3.5, 3.6
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from hypothesis import given, settings, strategies as st
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.base_model import Base
from app.modules.skills.models import (
    Domain,
    Skill,
    CandidateSkill,
    SkillSource,
    UnmatchedSkillReview,
)
from app.modules.skills.service import (
    create_domain,
    create_skill,
    match_and_link_skills,
    add_candidate_skill,
)


# ---------------------------------------------------------------------------
# Test Database Setup
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    """
    Create an in-memory SQLite async database for testing.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Unit Tests: create_domain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_domain_success(test_db):
    """
    create_domain successfully creates a new domain with unique name.

    Validates: Requirements 3.1
    """
    domain = await create_domain(test_db, "Python")

    assert domain.domain_id is not None
    assert domain.name == "Python"
    assert domain.deleted_at is None

    # Verify it was persisted
    result = await test_db.execute(
        select(Domain).where(Domain.domain_id == domain.domain_id)
    )
    persisted = result.scalar_one_or_none()
    assert persisted is not None
    assert persisted.name == "Python"


@pytest.mark.asyncio
async def test_create_domain_duplicate_name(test_db):
    """
    create_domain raises 409 when domain name already exists.

    Validates: Requirements 3.1
    """
    await create_domain(test_db, "Python")

    with pytest.raises(HTTPException) as exc_info:
        await create_domain(test_db, "Python")

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Unit Tests: create_skill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_skill_success(test_db):
    """
    create_skill successfully creates a new skill within a domain.

    Validates: Requirements 3.1
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")

    assert skill.skill_id is not None
    assert skill.domain_id == domain.domain_id
    assert skill.name == "Django"
    assert skill.deleted_at is None


@pytest.mark.asyncio
async def test_create_skill_duplicate_in_domain(test_db):
    """
    create_skill raises 409 when (domain_id, name) already exists.

    Validates: Requirements 3.1
    """
    domain = await create_domain(test_db, "Python")
    await create_skill(test_db, domain.domain_id, "Django")

    with pytest.raises(HTTPException) as exc_info:
        await create_skill(test_db, domain.domain_id, "Django")

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_skill_same_name_different_domain(test_db):
    """
    create_skill allows same skill name in different domains.

    Validates: Requirements 3.1
    """
    domain1 = await create_domain(test_db, "Python")
    domain2 = await create_domain(test_db, "JavaScript")

    skill1 = await create_skill(test_db, domain1.domain_id, "Testing")
    skill2 = await create_skill(test_db, domain2.domain_id, "Testing")

    assert skill1.skill_id != skill2.skill_id
    assert skill1.domain_id == domain1.domain_id
    assert skill2.domain_id == domain2.domain_id


# ---------------------------------------------------------------------------
# Unit Tests: add_candidate_skill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_candidate_skill_success(test_db):
    """
    add_candidate_skill successfully adds a skill to a candidate.

    Validates: Requirements 3.2
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")

    candidate_id = uuid.uuid4()
    candidate_skill = await add_candidate_skill(
        test_db,
        candidate_id=candidate_id,
        skill_id=skill.skill_id,
        proficiency_rank=3,
        years_of_experience=5,
    )

    assert candidate_skill.candidate_skill_id is not None
    assert candidate_skill.candidate_id == candidate_id
    assert candidate_skill.skill_id == skill.skill_id
    assert candidate_skill.proficiency_rank == 3
    assert candidate_skill.years_of_experience == 5
    assert candidate_skill.source == SkillSource.MANUAL


@pytest.mark.asyncio
async def test_add_candidate_skill_invalid_proficiency_rank_low(test_db):
    """
    add_candidate_skill raises 422 when proficiency_rank < 1.

    Validates: Requirements 3.2
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")

    with pytest.raises(HTTPException) as exc_info:
        await add_candidate_skill(
            test_db,
            candidate_id=uuid.uuid4(),
            skill_id=skill.skill_id,
            proficiency_rank=0,
            years_of_experience=5,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "proficiency_rank" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_candidate_skill_invalid_proficiency_rank_high(test_db):
    """
    add_candidate_skill raises 422 when proficiency_rank > 5.

    Validates: Requirements 3.2
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")

    with pytest.raises(HTTPException) as exc_info:
        await add_candidate_skill(
            test_db,
            candidate_id=uuid.uuid4(),
            skill_id=skill.skill_id,
            proficiency_rank=6,
            years_of_experience=5,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "proficiency_rank" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_candidate_skill_invalid_years_low(test_db):
    """
    add_candidate_skill raises 422 when years_of_experience < 0.

    Validates: Requirements 3.2
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")

    with pytest.raises(HTTPException) as exc_info:
        await add_candidate_skill(
            test_db,
            candidate_id=uuid.uuid4(),
            skill_id=skill.skill_id,
            proficiency_rank=3,
            years_of_experience=-1,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "years_of_experience" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_candidate_skill_invalid_years_high(test_db):
    """
    add_candidate_skill raises 422 when years_of_experience > 50.

    Validates: Requirements 3.2
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")

    with pytest.raises(HTTPException) as exc_info:
        await add_candidate_skill(
            test_db,
            candidate_id=uuid.uuid4(),
            skill_id=skill.skill_id,
            proficiency_rank=3,
            years_of_experience=51,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "years_of_experience" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_candidate_skill_duplicate(test_db):
    """
    add_candidate_skill raises 409 when candidate already has the skill.

    Validates: Requirements 3.2
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")
    candidate_id = uuid.uuid4()

    await add_candidate_skill(
        test_db,
        candidate_id=candidate_id,
        skill_id=skill.skill_id,
        proficiency_rank=3,
        years_of_experience=5,
    )

    with pytest.raises(HTTPException) as exc_info:
        await add_candidate_skill(
            test_db,
            candidate_id=candidate_id,
            skill_id=skill.skill_id,
            proficiency_rank=4,
            years_of_experience=6,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "already has this skill" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Unit Tests: match_and_link_skills
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_and_link_skills_matched(test_db):
    """
    match_and_link_skills creates CandidateSkill for matched skills.

    Validates: Requirements 3.4
    """
    domain = await create_domain(test_db, "Python")
    skill = await create_skill(test_db, domain.domain_id, "Django")

    candidate_id = uuid.uuid4()
    org_id = uuid.uuid4()

    await match_and_link_skills(
        test_db,
        candidate_id=candidate_id,
        org_id=org_id,
        extracted_skills=["Django"],
    )

    result = await test_db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id,
            CandidateSkill.skill_id == skill.skill_id,
        )
    )
    candidate_skill = result.scalar_one_or_none()

    assert candidate_skill is not None
    assert candidate_skill.source == SkillSource.PARSED
    assert candidate_skill.proficiency_rank == 1
    assert candidate_skill.years_of_experience == 0


@pytest.mark.asyncio
async def test_match_and_link_skills_unmatched(test_db):
    """
    match_and_link_skills creates UnmatchedSkillReview for unmatched skills.

    Validates: Requirements 3.5
    """
    candidate_id = uuid.uuid4()
    org_id = uuid.uuid4()

    await match_and_link_skills(
        test_db,
        candidate_id=candidate_id,
        org_id=org_id,
        extracted_skills=["NonexistentSkill"],
    )

    result = await test_db.execute(
        select(UnmatchedSkillReview).where(
            UnmatchedSkillReview.candidate_id == candidate_id,
            UnmatchedSkillReview.unmatched_skill_name == "NonexistentSkill",
        )
    )
    review = result.scalar_one_or_none()

    assert review is not None
    assert review.organization_id == org_id
    assert review.resolved is False


@pytest.mark.asyncio
async def test_match_and_link_skills_zero_skills(test_db):
    """
    match_and_link_skills is a no-op when extracted_skills is empty.

    Validates: Requirements 3.6
    """
    candidate_id = uuid.uuid4()
    org_id = uuid.uuid4()

    # Should not raise any exception
    await match_and_link_skills(
        test_db,
        candidate_id=candidate_id,
        org_id=org_id,
        extracted_skills=[],
    )

    # Verify no records were created
    result = await test_db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id
        )
    )
    assert result.scalar_one_or_none() is None

    result = await test_db.execute(
        select(UnmatchedSkillReview).where(
            UnmatchedSkillReview.candidate_id == candidate_id
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_match_and_link_skills_mixed(test_db):
    """
    match_and_link_skills handles both matched and unmatched skills.

    Validates: Requirements 3.4, 3.5
    """
    domain = await create_domain(test_db, "Python")
    skill1 = await create_skill(test_db, domain.domain_id, "Django")
    skill2 = await create_skill(test_db, domain.domain_id, "Flask")

    candidate_id = uuid.uuid4()
    org_id = uuid.uuid4()

    await match_and_link_skills(
        test_db,
        candidate_id=candidate_id,
        org_id=org_id,
        extracted_skills=["Django", "UnknownSkill", "Flask"],
    )

    # Check matched skills
    result = await test_db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id
        )
    )
    candidate_skills = result.scalars().all()
    assert len(candidate_skills) == 2
    skill_ids = {cs.skill_id for cs in candidate_skills}
    assert skill1.skill_id in skill_ids
    assert skill2.skill_id in skill_ids

    # Check unmatched review
    result = await test_db.execute(
        select(UnmatchedSkillReview).where(
            UnmatchedSkillReview.candidate_id == candidate_id
        )
    )
    reviews = result.scalars().all()
    assert len(reviews) == 1
    assert reviews[0].unmatched_skill_name == "UnknownSkill"


# ---------------------------------------------------------------------------
# Property-Based Tests: Case-Insensitive Matching (Property 8)
# ---------------------------------------------------------------------------

@given(
    base_name=st.text(
        min_size=2,
        max_size=50,
        alphabet="abcdefghijklmnopqrstuvwxyz",
    ),
    case_variant=st.sampled_from(["lower", "upper", "title", "mixed"]),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_skill_matching_case_insensitive(base_name, case_variant):
    """
    **Validates: Requirements 3.4**

    Property 8: Skill matching is case-insensitive.

    For any skill name stored in the taxonomy, extracted skill names in any
    case variant (lower, upper, title, mixed) should match the stored skill
    and create a CandidateSkill record.
    """
    # Create fresh database for each example
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as test_db:
        # Create domain and skill with base_name in lowercase
        domain = await create_domain(test_db, "TestDomain")
        skill = await create_skill(test_db, domain.domain_id, base_name.lower())

        # Generate case variant
        if case_variant == "lower":
            extracted_name = base_name.lower()
        elif case_variant == "upper":
            extracted_name = base_name.upper()
        elif case_variant == "title":
            extracted_name = base_name.title()
        else:  # mixed
            # Create a mixed case variant
            chars = list(base_name)
            for i in range(0, len(chars), 2):
                chars[i] = chars[i].upper()
            extracted_name = "".join(chars)

        candidate_id = uuid.uuid4()
        org_id = uuid.uuid4()

        # Match and link
        await match_and_link_skills(
            test_db,
            candidate_id=candidate_id,
            org_id=org_id,
            extracted_skills=[extracted_name],
        )

        # Verify CandidateSkill was created
        result = await test_db.execute(
            select(CandidateSkill).where(
                CandidateSkill.candidate_id == candidate_id,
                CandidateSkill.skill_id == skill.skill_id,
            )
        )
        candidate_skill = result.scalar_one_or_none()

        assert candidate_skill is not None, (
            f"Expected CandidateSkill to be created for extracted name '{extracted_name}' "
            f"matching stored skill '{base_name.lower()}'"
        )
        assert candidate_skill.source == SkillSource.PARSED

    await engine.dispose()


# ---------------------------------------------------------------------------
# Property-Based Tests: Unmatched and Zero Skills (Property 9)
# ---------------------------------------------------------------------------

@given(
    skill_names=st.lists(
        st.text(min_size=1, max_size=50),
        min_size=0,
        max_size=10,
    )
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_unmatched_zero_skills_no_block(skill_names):
    """
    **Validates: Requirements 3.5, 3.6**

    Property 9: Unmatched or zero skills do not block ingestion.

    For any list of skill names (including empty list), match_and_link_skills
    completes without exception. For each non-existent skill name, an
    UnmatchedSkillReview is created. For empty list, no records are created.
    """
    # Create fresh database for each example
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as test_db:
        candidate_id = uuid.uuid4()
        org_id = uuid.uuid4()

        # Should not raise any exception
        await match_and_link_skills(
            test_db,
            candidate_id=candidate_id,
            org_id=org_id,
            extracted_skills=skill_names,
        )

        # Verify UnmatchedSkillReview records
        result = await test_db.execute(
            select(UnmatchedSkillReview).where(
                UnmatchedSkillReview.candidate_id == candidate_id
            )
        )
        reviews = result.scalars().all()

        if skill_names:
            # All skill names should have reviews (since no skills exist in taxonomy)
            assert len(reviews) == len(skill_names)
            review_names = {r.unmatched_skill_name for r in reviews}
            assert review_names == set(skill_names)
        else:
            # Empty list → no reviews
            assert len(reviews) == 0

        # Verify no CandidateSkill records were created
        result = await test_db.execute(
            select(CandidateSkill).where(
                CandidateSkill.candidate_id == candidate_id
            )
        )
        candidate_skills = result.scalars().all()
        assert len(candidate_skills) == 0

    await engine.dispose()
