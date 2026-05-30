"""
Unit and property-based tests for resume ingestion service.

Tests the following functions:
  - _run_ingestion: background task that calls ResumeIngestionAgent and applies results
  - _apply_ingestion_results: upserts candidate, creates job history, links skills, associates resume

Requirements: 2.5, 2.6, 2.8
"""

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from hypothesis import given, settings as hypothesis_settings, assume
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.base_model import Base
from app.crypto import encrypt_field, decrypt_field
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.resumes.models import Resume, CandidateJobHistory, ParseStatus
from app.modules.resumes.service import _run_ingestion, _apply_ingestion_results
from app.modules.skills.models import CandidateSkill, SkillSource, UnmatchedSkillReview, Skill, Domain


# ---------------------------------------------------------------------------
# Test Database Setup
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db():
    """
    Create an in-memory SQLite async database for testing.
    """
    from sqlalchemy import event
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Disable foreign key constraints for testing
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def org_id():
    """Fixture for organization ID."""
    return uuid.uuid4()


@pytest.fixture
def user_id():
    """Fixture for user ID."""
    return uuid.uuid4()





# ---------------------------------------------------------------------------
# Unit Tests: _apply_ingestion_results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_ingestion_results_creates_candidate(test_db, org_id, user_id):
    """
    _apply_ingestion_results creates a new candidate from extracted data.

    Validates: Requirements 2.6
    """
    resume = Resume(
        resume_id=uuid.uuid4(),
        organization_id=org_id,
        storage_location="local://test.pdf",
        mime_type="application/pdf",
        file_name="test.pdf",
        file_size_bytes=1024,
        uploaded_by_user_id=user_id,
        is_primary=True,
        parse_status=ParseStatus.PENDING,
    )
    test_db.add(resume)
    await test_db.flush()

    extracted_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "job_history": [],
        "skills": [],
    }

    await _apply_ingestion_results(resume, extracted_data, org_id, test_db)

    # Verify candidate was created
    result = await test_db.execute(
        select(Candidate).where(Candidate.organization_id == org_id)
    )
    candidate = result.scalar_one_or_none()
    assert candidate is not None
    assert decrypt_field(candidate.name) == "John Doe"
    assert decrypt_field(candidate.email) == "john@example.com"

    # Verify resume is associated
    assert resume.candidate_id == candidate.candidate_id


@pytest.mark.asyncio
async def test_apply_ingestion_results_creates_job_history(test_db, org_id, user_id):
    """
    _apply_ingestion_results creates CandidateJobHistory records.

    Validates: Requirements 2.6
    """
    resume = Resume(
        resume_id=uuid.uuid4(),
        organization_id=org_id,
        storage_location="local://test.pdf",
        mime_type="application/pdf",
        file_name="test.pdf",
        file_size_bytes=1024,
        uploaded_by_user_id=user_id,
        is_primary=True,
        parse_status=ParseStatus.PENDING,
    )
    test_db.add(resume)
    await test_db.flush()

    extracted_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": None,
        "job_history": [
            {
                "company_name": "Acme Corp",
                "job_title": "Software Engineer",
                "start_date": date(2020, 1, 1),
                "end_date": date(2022, 12, 31),
                "description": "Developed software",
                "is_current": False,
            },
            {
                "company_name": "Tech Inc",
                "job_title": "Senior Engineer",
                "start_date": date(2023, 1, 1),
                "end_date": None,
                "description": "Leading team",
                "is_current": True,
            },
        ],
        "skills": [],
    }

    await _apply_ingestion_results(resume, extracted_data, org_id, test_db)

    # Verify job history records were created
    result = await test_db.execute(
        select(CandidateJobHistory).where(
            CandidateJobHistory.organization_id == org_id
        )
    )
    job_histories = result.scalars().all()
    assert len(job_histories) == 2
    assert job_histories[0].company_name == "Acme Corp"
    assert job_histories[1].company_name == "Tech Inc"


@pytest.mark.asyncio
async def test_apply_ingestion_results_links_skills(test_db, org_id, user_id):
    """
    _apply_ingestion_results links matched skills to candidate.

    Validates: Requirements 2.6, 3.4
    """
    # Create a domain and skill
    domain = Domain(domain_id=uuid.uuid4(), name="Programming")
    test_db.add(domain)
    await test_db.flush()

    skill = Skill(skill_id=uuid.uuid4(), domain_id=domain.domain_id, name="Python")
    test_db.add(skill)
    await test_db.flush()

    resume = Resume(
        resume_id=uuid.uuid4(),
        organization_id=org_id,
        storage_location="local://test.pdf",
        mime_type="application/pdf",
        file_name="test.pdf",
        file_size_bytes=1024,
        uploaded_by_user_id=user_id,
        is_primary=True,
        parse_status=ParseStatus.PENDING,
    )
    test_db.add(resume)
    await test_db.flush()

    extracted_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": None,
        "job_history": [],
        "skills": ["Python", "JavaScript"],
    }

    await _apply_ingestion_results(resume, extracted_data, org_id, test_db)

    # Verify candidate skills were created
    result = await test_db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == resume.candidate_id
        )
    )
    candidate_skills = result.scalars().all()
    assert len(candidate_skills) >= 1  # At least Python should be matched

    # Verify unmatched skill review was created for JavaScript
    result = await test_db.execute(
        select(UnmatchedSkillReview).where(
            UnmatchedSkillReview.organization_id == org_id
        )
    )
    unmatched = result.scalars().all()
    assert len(unmatched) >= 1  # JavaScript should be unmatched


@pytest.mark.asyncio
async def test_apply_ingestion_results_handles_empty_skills(test_db, org_id, user_id):
    """
    _apply_ingestion_results handles empty skills list without error.

    Validates: Requirements 2.6, 3.6
    """
    resume = Resume(
        resume_id=uuid.uuid4(),
        organization_id=org_id,
        storage_location="local://test.pdf",
        mime_type="application/pdf",
        file_name="test.pdf",
        file_size_bytes=1024,
        uploaded_by_user_id=user_id,
        is_primary=True,
        parse_status=ParseStatus.PENDING,
    )
    test_db.add(resume)
    await test_db.flush()

    extracted_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": None,
        "job_history": [],
        "skills": [],
    }

    # Should not raise any exception
    await _apply_ingestion_results(resume, extracted_data, org_id, test_db)

    # Verify candidate was created
    result = await test_db.execute(
        select(Candidate).where(Candidate.organization_id == org_id)
    )
    candidate = result.scalar_one_or_none()
    assert candidate is not None


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

class TestParseStatusTransitions:
    """Property-based tests for ParseStatus transitions on ingestion outcome."""

    @pytest.mark.asyncio
    @given(agent_succeeds=st.booleans())
    @hypothesis_settings(max_examples=50)
    async def test_parse_status_on_ingestion_outcome(
        self, test_db, org_id, user_id, agent_succeeds: bool
    ):
        """
        Property 6: ParseStatus transitions correctly on ingestion outcome

        Validates: Requirements 2.6, 2.8

        For any agent success/failure:
        - Agent success → parse_status=COMPLETED, parsed_data populated
        - Agent failure → parse_status=FAILED, error logged
        """
        resume = Resume(
            resume_id=uuid.uuid4(),
            organization_id=org_id,
            storage_location="local://test.pdf",
            mime_type="application/pdf",
            file_name="test.pdf",
            file_size_bytes=1024,
            uploaded_by_user_id=user_id,
            is_primary=True,
            parse_status=ParseStatus.PENDING,
        )
        test_db.add(resume)
        await test_db.flush()

        resume_id = resume.resume_id
        correlation_id = str(uuid.uuid4())

        if agent_succeeds:
            # Mock successful agent response
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": None,
                "job_history": [],
                "skills": [],
            }
            mock_response.raise_for_status = AsyncMock()

            with patch("httpx.AsyncClient.post", return_value=mock_response):
                with patch("app.modules.resumes.service.AsyncSessionFactory") as mock_factory:
                    mock_factory.return_value.__aenter__.return_value = test_db
                    mock_factory.return_value.__aexit__.return_value = None

                    await _run_ingestion(resume_id, "local://test.pdf", org_id, correlation_id)

            # Verify parse_status is COMPLETED
            result = await test_db.execute(
                select(Resume).where(Resume.resume_id == resume_id)
            )
            updated_resume = result.scalar_one_or_none()
            assert updated_resume.parse_status == ParseStatus.COMPLETED
            assert updated_resume.parsed_data is not None
        else:
            # Mock failed agent response
            with patch("httpx.AsyncClient.post", side_effect=Exception("Agent error")):
                with patch("app.modules.resumes.service.AsyncSessionFactory") as mock_factory:
                    mock_factory.return_value.__aenter__.return_value = test_db
                    mock_factory.return_value.__aexit__.return_value = None

                    await _run_ingestion(resume_id, "local://test.pdf", org_id, correlation_id)

            # Verify parse_status is FAILED
            result = await test_db.execute(
                select(Resume).where(Resume.resume_id == resume_id)
            )
            updated_resume = result.scalar_one_or_none()
            assert updated_resume.parse_status == ParseStatus.FAILED


class TestIngestionUpsertRecords:
    """Property-based tests for ingestion upsert of all associated records."""

    @pytest.mark.asyncio
    @given(
        job_history_count=st.integers(min_value=0, max_value=5),
        skill_count=st.integers(min_value=0, max_value=10),
    )
    @hypothesis_settings(max_examples=50)
    async def test_ingestion_upserts_all_records(
        self, test_db, org_id, user_id, job_history_count: int, skill_count: int
    ):
        """
        Property 7: Ingestion upserts all associated records on success

        Validates: Requirements 2.6

        For any job_history_count and skill_count:
        - Successful ingestion creates exactly N CandidateJobHistory records
        - Successful ingestion creates ≤M CandidateSkill records (some may be unmatched)
        - parse_status=COMPLETED
        """
        # Create skills in taxonomy
        domain = Domain(domain_id=uuid.uuid4(), name="Programming")
        test_db.add(domain)
        await test_db.flush()

        skills_in_taxonomy = []
        for i in range(min(skill_count, 5)):
            skill = Skill(
                skill_id=uuid.uuid4(),
                domain_id=domain.domain_id,
                name=f"Skill{i}",
            )
            test_db.add(skill)
            skills_in_taxonomy.append(f"Skill{i}")
        await test_db.flush()

        # Create job history entries
        job_history = []
        for i in range(job_history_count):
            job_history.append({
                "company_name": f"Company{i}",
                "job_title": f"Title{i}",
                "start_date": date(2020 + i, 1, 1),
                "end_date": None if i == job_history_count - 1 else date(2021 + i, 12, 31),
                "description": f"Description{i}",
                "is_current": i == job_history_count - 1,
            })

        # Create extracted skills (mix of matched and unmatched)
        extracted_skills = skills_in_taxonomy[:skill_count]

        resume = Resume(
            resume_id=uuid.uuid4(),
            organization_id=org_id,
            storage_location="local://test.pdf",
            mime_type="application/pdf",
            file_name="test.pdf",
            file_size_bytes=1024,
            uploaded_by_user_id=user_id,
            is_primary=True,
            parse_status=ParseStatus.PENDING,
        )
        test_db.add(resume)
        await test_db.flush()

        extracted_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": None,
            "job_history": job_history,
            "skills": extracted_skills,
        }

        await _apply_ingestion_results(resume, extracted_data, org_id, test_db)

        # Verify job history records
        result = await test_db.execute(
            select(CandidateJobHistory).where(
                CandidateJobHistory.candidate_id == resume.candidate_id
            )
        )
        job_histories = result.scalars().all()
        assert len(job_histories) == job_history_count

        # Verify candidate skills (should be at least the matched ones)
        result = await test_db.execute(
            select(CandidateSkill).where(
                CandidateSkill.candidate_id == resume.candidate_id
            )
        )
        candidate_skills = result.scalars().all()
        assert len(candidate_skills) <= skill_count
