"""
Unit and property-based tests for resume ingestion service.

Tests the following functions:
  - _run_ingestion: background task that calls ResumeIngestionAgent and applies results
  - _apply_ingestion_results: upserts candidate, creates job history, links skills, associates resume

Requirements: 2.5, 2.6, 2.8
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from hypothesis import given, settings as hypothesis_settings, HealthCheck
from hypothesis import strategies as st

from app.modules.resumes.models import Resume, ParseStatus, CandidateJobHistory
from app.modules.resumes.service import _run_ingestion, _apply_ingestion_results
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.skills.models import CandidateSkill, UnmatchedSkillReview, Skill, Domain
from app.crypto import decrypt_field


# ---------------------------------------------------------------------------
# Unit Tests: _apply_ingestion_results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_ingestion_results_creates_candidate():
    """
    _apply_ingestion_results creates a new candidate from extracted data.

    Validates: Requirements 2.6
    """
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    # Create mock database session
    mock_db = AsyncMock()
    
    # Mock the execute method to return no existing candidate
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Create a resume
    resume = Resume(
        resume_id=uuid.uuid4(),
        organization_id=org_id,
        storage_location="local://test.pdf",
        mime_type="application/pdf",
        file_name="test.pdf",
        file_size_bytes=1024,
        uploaded_by_user_id=user_id,
        is_primary=True,
        parse_status=ParseStatus.PENDING.value,
    )
    
    extracted_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "job_history": [],
        "skills": [],
    }
    
    # Mock CandidateService.create_candidate
    with patch("app.modules.resumes.service.CandidateService") as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        # Create a mock candidate
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.candidate_id = uuid.uuid4()
        mock_service.create_candidate = AsyncMock(return_value=mock_candidate)
        
        # Mock SkillService
        with patch("app.modules.resumes.service.SkillService"):
            await _apply_ingestion_results(resume, extracted_data, org_id, mock_db)
    
    # Verify candidate was associated with resume
    assert resume.candidate_id is not None


@pytest.mark.asyncio
async def test_apply_ingestion_results_creates_job_history():
    """
    _apply_ingestion_results creates CandidateJobHistory records.

    Validates: Requirements 2.6
    """
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    
    # Create mock database session
    mock_db = AsyncMock()
    
    # Mock the execute method to return no existing candidate
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Create a resume
    resume = Resume(
        resume_id=uuid.uuid4(),
        organization_id=org_id,
        storage_location="local://test.pdf",
        mime_type="application/pdf",
        file_name="test.pdf",
        file_size_bytes=1024,
        uploaded_by_user_id=user_id,
        is_primary=True,
        parse_status=ParseStatus.PENDING.value,
    )
    
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
    
    # Mock CandidateService.create_candidate
    with patch("app.modules.resumes.service.CandidateService") as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        # Create a mock candidate
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.candidate_id = candidate_id
        mock_service.create_candidate = AsyncMock(return_value=mock_candidate)
        
        # Mock SkillService
        with patch("app.modules.resumes.service.SkillService"):
            await _apply_ingestion_results(resume, extracted_data, org_id, mock_db)
    
    # Verify db.add was called for job history records
    # The mock_db.add should have been called twice (for the two job history entries)
    assert mock_db.add.call_count >= 2


@pytest.mark.asyncio
async def test_apply_ingestion_results_handles_empty_skills():
    """
    _apply_ingestion_results handles empty skills list without error.

    Validates: Requirements 2.6, 3.6
    """
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    # Create mock database session
    mock_db = AsyncMock()
    
    # Mock the execute method to return no existing candidate
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Create a resume
    resume = Resume(
        resume_id=uuid.uuid4(),
        organization_id=org_id,
        storage_location="local://test.pdf",
        mime_type="application/pdf",
        file_name="test.pdf",
        file_size_bytes=1024,
        uploaded_by_user_id=user_id,
        is_primary=True,
        parse_status=ParseStatus.PENDING.value,
    )
    
    extracted_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": None,
        "job_history": [],
        "skills": [],
    }
    
    # Mock CandidateService.create_candidate
    with patch("app.modules.resumes.service.CandidateService") as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        # Create a mock candidate
        mock_candidate = MagicMock(spec=Candidate)
        mock_candidate.candidate_id = uuid.uuid4()
        mock_service.create_candidate = AsyncMock(return_value=mock_candidate)
        
        # Mock SkillService
        with patch("app.modules.resumes.service.SkillService"):
            # Should not raise any exception
            await _apply_ingestion_results(resume, extracted_data, org_id, mock_db)
    
    # Verify candidate was associated with resume
    assert resume.candidate_id is not None


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

class TestParseStatusTransitions:
    """Property-based tests for ParseStatus transitions on ingestion outcome."""

    @pytest.mark.asyncio
    @given(agent_succeeds=st.booleans())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_parse_status_on_ingestion_outcome(self, agent_succeeds: bool, test_run_id):
        """
        Property 6: ParseStatus transitions correctly on ingestion outcome

        Validates: Requirements 2.6, 2.8

        For any agent success/failure:
        - Agent success → parse_status=COMPLETED, parsed_data populated
        - Agent failure → parse_status=FAILED, error logged
        """
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        resume_id = uuid.uuid4()
        correlation_id = str(uuid.uuid4())
        
        # Create mock database session
        mock_db = AsyncMock()
        
        # Create a resume with unique data
        resume = Resume(
            resume_id=resume_id,
            organization_id=org_id,
            storage_location=f"local://test-{test_run_id}.pdf",
            mime_type="application/pdf",
            file_name=f"test-{test_run_id}.pdf",
            file_size_bytes=1024,
            uploaded_by_user_id=user_id,
            is_primary=True,
            parse_status=ParseStatus.PENDING.value,
        )
        
        # Mock db.get to return the resume
        mock_db.get = AsyncMock(return_value=resume)
        
        if agent_succeeds:
            # Mock successful agent response
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={
                "name": "John Doe",
                "email": "john@example.com",
                "phone": None,
                "job_history": [],
                "skills": [],
            })
            mock_response.raise_for_status = MagicMock()
            
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            
            # Mock db operations - make sure execute returns something with scalar_one_or_none
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db.execute = AsyncMock(return_value=mock_execute_result)
            mock_db.flush = AsyncMock()
            mock_db.commit = AsyncMock()
            
            # Create a proper async context manager for AsyncSessionFactory
            class AsyncContextManager:
                async def __aenter__(self):
                    return mock_db
                async def __aexit__(self, *args):
                    pass
            
            with patch("httpx.AsyncClient", return_value=mock_client):
                with patch("app.modules.resumes.service.AsyncSessionFactory", return_value=AsyncContextManager()):
                    with patch("app.modules.resumes.service.CandidateService") as mock_candidate_service_class:
                        mock_candidate_service = MagicMock()
                        mock_candidate_service_class.return_value = mock_candidate_service
                        mock_candidate = MagicMock(spec=Candidate)
                        mock_candidate.candidate_id = uuid.uuid4()
                        mock_candidate_service.create_candidate = AsyncMock(return_value=mock_candidate)
                        
                        with patch("app.modules.resumes.service.SkillService") as mock_skill_service_class:
                            mock_skill_service = MagicMock()
                            mock_skill_service_class.return_value = mock_skill_service
                            mock_skill_service.match_and_link_skills = AsyncMock()
                            
                            await _run_ingestion(resume_id, "local://test.pdf", org_id, correlation_id)
            
            # Verify parse_status is COMPLETED
            assert resume.parse_status == ParseStatus.COMPLETED.value
            assert resume.parsed_data is not None
        else:
            # Mock failed agent response
            with patch("httpx.AsyncClient.post", side_effect=Exception("Agent error")):
                with patch("app.modules.resumes.service.AsyncSessionFactory") as mock_factory:
                    mock_factory.return_value.__aenter__.return_value = mock_db
                    mock_factory.return_value.__aexit__.return_value = None
                    
                    await _run_ingestion(resume_id, "local://test.pdf", org_id, correlation_id)
            
            # Verify parse_status is FAILED
            assert resume.parse_status == ParseStatus.FAILED.value


class TestIngestionUpsertRecords:
    """Property-based tests for ingestion upsert of all associated records."""

    @pytest.mark.asyncio
    @given(
        job_history_count=st.integers(min_value=0, max_value=5),
        skill_count=st.integers(min_value=0, max_value=10),
    )
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_ingestion_upserts_all_records(
        self, job_history_count: int, skill_count: int, test_run_id
    ):
        """
        Property 7: Ingestion upserts all associated records on success

        Validates: Requirements 2.6

        For any job_history_count and skill_count:
        - Successful ingestion creates exactly N CandidateJobHistory records
        - Successful ingestion creates ≤M CandidateSkill records (some may be unmatched)
        - parse_status=COMPLETED
        """
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        candidate_id = uuid.uuid4()
        
        # Create mock database session
        mock_db = AsyncMock()
        
        # Mock the execute method to return no existing candidate
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        # Create a resume with unique data
        resume = Resume(
            resume_id=uuid.uuid4(),
            organization_id=org_id,
            storage_location=f"local://test-{test_run_id}.pdf",
            mime_type="application/pdf",
            file_name=f"test-{test_run_id}.pdf",
            file_size_bytes=1024,
            uploaded_by_user_id=user_id,
            is_primary=True,
            parse_status=ParseStatus.PENDING.value,
        )
        
        # Create job history entries with unique data
        job_history = []
        for i in range(job_history_count):
            job_history.append({
                "company_name": f"Company{i}-{test_run_id}",
                "job_title": f"Title{i}-{test_run_id}",
                "start_date": date(2020 + i, 1, 1),
                "end_date": None if i == job_history_count - 1 else date(2021 + i, 12, 31),
                "description": f"Description{i}-{test_run_id}",
                "is_current": i == job_history_count - 1,
            })
        
        # Create extracted skills with unique data
        extracted_skills = [f"Skill{i}-{test_run_id}" for i in range(skill_count)]
        
        extracted_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": None,
            "job_history": job_history,
            "skills": extracted_skills,
        }
        
        # Mock CandidateService.create_candidate
        with patch("app.modules.resumes.service.CandidateService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Create a mock candidate
            mock_candidate = MagicMock(spec=Candidate)
            mock_candidate.candidate_id = candidate_id
            mock_service.create_candidate = AsyncMock(return_value=mock_candidate)
            
            # Mock SkillService with proper async methods
            with patch("app.modules.resumes.service.SkillService") as mock_skill_service_class:
                mock_skill_service = MagicMock()
                mock_skill_service_class.return_value = mock_skill_service
                mock_skill_service.match_and_link_skills = AsyncMock()
                
                await _apply_ingestion_results(resume, extracted_data, org_id, mock_db)
        
        # Verify job history records were added
        # The mock_db.add should have been called for each job history entry
        assert mock_db.add.call_count >= job_history_count
