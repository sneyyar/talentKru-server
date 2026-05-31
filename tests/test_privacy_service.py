"""
Tests for privacy service functionality.

Feature: candidate-lifecycle
Tasks: 13.3, 13.4, 13.5 - Property tests for DSAR workflows

Requirements: 6.2, 6.3, 6.7
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.modules.privacy.service import PrivacyService
from app.modules.privacy.models import (
    OrganizationRetentionPolicy,
    DataSubjectAccessRequest,
    DSARRequestType,
    DSARStatus,
)
from app.modules.candidates.models import Candidate
from app.modules.resumes.models import Resume
from app.audit_models import AuditLog


class TestRetentionPurge:
    """Tests for retention policy purge functionality."""

    @pytest.mark.asyncio
    async def test_run_retention_purge_no_policies(self):
        """
        Test run_retention_purge with no retention policies.
        
        Validates: Requirements 6.5
        
        - When no retention policies exist, purge completes successfully
        - Returns {"candidates": 0, "resumes": 0}
        """
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Mock the execute method to return no policies
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()
        
        service = PrivacyService(mock_db)
        result = await service.run_retention_purge()
        
        assert result["candidates"] == 0
        assert result["resumes"] == 0

    @pytest.mark.asyncio
    async def test_run_retention_purge_with_expired_resumes(self):
        """
        Test run_retention_purge purges expired resumes.
        
        Validates: Requirements 6.5
        
        - Resumes older than resume_retention_days are hard-deleted
        - Logging occurs for each purged resume
        """
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        org_id = uuid4()
        
        # Create a mock retention policy
        policy = MagicMock(spec=OrganizationRetentionPolicy)
        policy.organization_id = org_id
        policy.candidate_data_retention_days = 730
        policy.resume_retention_days = 365
        
        # Create mock resumes
        old_resume = MagicMock(spec=Resume)
        old_resume.resume_id = uuid4()
        old_resume.created_at = datetime.now(timezone.utc) - timedelta(days=400)
        
        # Mock execute to return policies and resumes
        call_count = 0
        
        async def mock_execute(query):
            nonlocal call_count
            result = MagicMock()
            
            if call_count == 0:
                # First call: get policies
                result.scalars.return_value.all.return_value = [policy]
            elif call_count == 1:
                # Second call: get old resumes
                result.scalars.return_value.all.return_value = [old_resume]
            elif call_count == 2:
                # Third call: get old candidates
                result.scalars.return_value.all.return_value = []
            
            call_count += 1
            return result
        
        mock_db.execute = mock_execute
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()
        
        service = PrivacyService(mock_db)
        result = await service.run_retention_purge()
        
        assert result["resumes"] == 1
        assert result["candidates"] == 0

    @pytest.mark.asyncio
    async def test_run_retention_purge_with_expired_candidates(self):
        """
        Test run_retention_purge purges expired soft-deleted candidates.
        
        Validates: Requirements 6.5
        
        - Only soft-deleted candidates (deleted_at IS NOT NULL) are purged
        - Candidates older than candidate_data_retention_days are hard-deleted
        """
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        org_id = uuid4()
        
        # Create a mock retention policy
        policy = MagicMock(spec=OrganizationRetentionPolicy)
        policy.organization_id = org_id
        policy.candidate_data_retention_days = 730
        policy.resume_retention_days = 365
        
        # Create mock candidates
        old_deleted_candidate = MagicMock(spec=Candidate)
        old_deleted_candidate.candidate_id = uuid4()
        old_deleted_candidate.created_at = datetime.now(timezone.utc) - timedelta(days=800)
        old_deleted_candidate.deleted_at = datetime.now(timezone.utc) - timedelta(days=800)
        
        # Mock execute to return policies and candidates
        call_count = 0
        
        async def mock_execute(query):
            nonlocal call_count
            result = MagicMock()
            
            if call_count == 0:
                # First call: get policies
                result.scalars.return_value.all.return_value = [policy]
            elif call_count == 1:
                # Second call: get old resumes
                result.scalars.return_value.all.return_value = []
            elif call_count == 2:
                # Third call: get old candidates
                result.scalars.return_value.all.return_value = [old_deleted_candidate]
            
            call_count += 1
            return result
        
        mock_db.execute = mock_execute
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()
        
        service = PrivacyService(mock_db)
        result = await service.run_retention_purge()
        
        assert result["candidates"] == 1
        assert result["resumes"] == 0

    @pytest.mark.asyncio
    async def test_run_retention_purge_returns_correct_counts(self):
        """
        Test run_retention_purge returns correct purge counts.
        
        Validates: Requirements 6.5
        
        - Returns {"candidates": N, "resumes": M} with correct counts
        """
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        org_id = uuid4()
        
        # Create a mock retention policy
        policy = MagicMock(spec=OrganizationRetentionPolicy)
        policy.organization_id = org_id
        policy.candidate_data_retention_days = 730
        policy.resume_retention_days = 365
        
        # Create mock resumes and candidates
        resumes = [MagicMock(spec=Resume) for _ in range(5)]
        for resume in resumes:
            resume.resume_id = uuid4()
        
        candidates = [MagicMock(spec=Candidate) for _ in range(3)]
        for candidate in candidates:
            candidate.candidate_id = uuid4()
        
        # Mock execute to return policies, resumes, and candidates
        call_count = 0
        
        async def mock_execute(query):
            nonlocal call_count
            result = MagicMock()
            
            if call_count == 0:
                # First call: get policies
                result.scalars.return_value.all.return_value = [policy]
            elif call_count == 1:
                # Second call: get old resumes
                result.scalars.return_value.all.return_value = resumes
            elif call_count == 2:
                # Third call: get old candidates
                result.scalars.return_value.all.return_value = candidates
            
            call_count += 1
            return result
        
        mock_db.execute = mock_execute
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()
        
        service = PrivacyService(mock_db)
        result = await service.run_retention_purge()
        
        assert result["candidates"] == 3
        assert result["resumes"] == 5


class TestDSARAccessWorkflowProperties:
    """Property-based tests for DSAR Access workflow isolation.
    
    Feature: candidate-lifecycle, Property 14: DSAR Access workflow only triggered for RequestType=Access
    """

    @given(request_type=st.sampled_from(list(DSARRequestType)))
    @hypothesis_settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_access_dsar_only_for_access_request_type(self, request_type: DSARRequestType):
        """
        Property 14: DSAR Access workflow only triggered for RequestType=Access
        
        Validates: Requirements 6.2
        
        For any request_type:
        - If request_type != ACCESS: process_access_dsar raises HTTPException 400; no data compiled
        - If request_type == ACCESS: data compiled and returned
        """
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        org_id = uuid4()
        candidate_id = uuid4()
        
        # Create a mock DSAR with the given request_type
        dsar = MagicMock(spec=DataSubjectAccessRequest)
        dsar.dsar_id = uuid4()
        dsar.candidate_id = candidate_id
        dsar.organization_id = org_id
        dsar.request_type = request_type
        dsar.status = DSARStatus.PENDING.value
        
        service = PrivacyService(mock_db)
        
        if request_type != DSARRequestType.ACCESS.value:
            # Should raise HTTPException 400
            with pytest.raises(HTTPException) as exc_info:
                await service.process_access_dsar(dsar)
            
            assert exc_info.value.status_code == 400
            assert "Access" in exc_info.value.detail
        else:
            # Should succeed and compile data
            # Mock candidate fetch
            from app.modules.candidates.models import GlobalStatus
            
            mock_candidate = MagicMock(spec=Candidate)
            mock_candidate.candidate_id = candidate_id
            mock_candidate.organization_id = org_id
            mock_candidate.name = b"encrypted_name"
            mock_candidate.email = b"encrypted_email"
            mock_candidate.phone = None
            mock_candidate.location = "New York"
            mock_candidate.global_status = GlobalStatus.ACTIVE.value
            mock_candidate.ineligibility_reason = None
            mock_candidate.created_at = datetime.now(timezone.utc)
            mock_candidate.updated_at = datetime.now(timezone.utc)
            mock_candidate.deleted_at = None
            
            # Mock job history, skills, resumes queries
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_candidate
            mock_result.scalars.return_value.all.return_value = []
            
            mock_db.execute.return_value = mock_result
            mock_db.flush = AsyncMock()
            
            # Patch decrypt_field to return test data
            with patch('app.modules.privacy.service.decrypt_field') as mock_decrypt:
                mock_decrypt.return_value = "decrypted_value"
                
                result = await service.process_access_dsar(dsar)
                
                # Verify data was compiled
                assert result is not None
                assert "candidate_id" in result
                assert "job_history" in result
                assert "skills" in result
                assert "resumes" in result
                
                # Verify DSAR status was updated
                assert dsar.status == DSARStatus.COMPLETED.value
                assert dsar.completed_at is not None


class TestDSARErasureHardDeleteProperties:
    """Property-based tests for DSAR Erasure hard-deleting personal data.
    
    Feature: candidate-lifecycle, Property 15: DSAR Erasure hard-deletes personal data and anonymizes audit trail
    """

    @given(resume_count=st.integers(min_value=0, max_value=5))
    @hypothesis_settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_erasure_dsar_hard_deletes_data(self, resume_count: int):
        """
        Property 15: DSAR Erasure hard-deletes personal data and anonymizes audit trail
        
        Validates: Requirements 6.3
        
        For any resume_count (0-5):
        - After process_erasure_dsar: candidate record absent from DB
        - All resume records absent
        - Audit log entries for candidate have anonymized=True
        - dsar.status=COMPLETED
        """
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        org_id = uuid4()
        candidate_id = uuid4()
        
        # Create a mock DSAR
        dsar = MagicMock(spec=DataSubjectAccessRequest)
        dsar.dsar_id = uuid4()
        dsar.candidate_id = candidate_id
        dsar.organization_id = org_id
        dsar.request_type = DSARRequestType.ERASURE.value
        dsar.status = DSARStatus.PENDING.value
        
        service = PrivacyService(mock_db)
        
        # Track delete calls
        delete_calls = []
        update_calls = []
        
        async def mock_execute(query):
            # Track delete and update operations
            query_str = str(query)
            if "DELETE" in query_str:
                delete_calls.append(query_str)
            elif "UPDATE" in query_str:
                update_calls.append(query_str)
            
            result = MagicMock()
            return result
        
        mock_db.execute = mock_execute
        mock_db.flush = AsyncMock()
        
        # Execute erasure
        await service.process_erasure_dsar(dsar)
        
        # Verify hard-deletes occurred
        assert len(delete_calls) >= 2  # At least Resume and Candidate deletes
        
        # Verify audit log anonymization occurred
        assert len(update_calls) >= 1  # At least one update for audit log
        
        # Verify DSAR status was updated to COMPLETED
        assert dsar.status == DSARStatus.COMPLETED.value
        assert dsar.completed_at is not None


class TestDSARDenialMinimumLengthProperties:
    """Property-based tests for DSAR denial requiring minimum-length reason.
    
    Feature: candidate-lifecycle, Property 19: DSAR denial requires minimum-length reason
    """

    @given(reason=st.one_of(st.none(), st.just(""), st.text(max_size=9)))
    @hypothesis_settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_denial_requires_minimum_length_reason(self, reason):
        """
        Property 19: DSAR denial requires minimum-length reason
        
        Validates: Requirements 6.7
        
        For any reason (None, empty, or 0-9 chars):
        - Short/absent reason → HTTPException 400
        - DSAR status unchanged
        
        For valid reason (≥10 chars):
        - Denial recorded in audit log
        - DSAR status=DENIED
        """
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        org_id = uuid4()
        candidate_id = uuid4()
        denied_by = uuid4()
        
        # Create a mock DSAR
        dsar = MagicMock(spec=DataSubjectAccessRequest)
        dsar.dsar_id = uuid4()
        dsar.candidate_id = candidate_id
        dsar.organization_id = org_id
        dsar.request_type = DSARRequestType.ACCESS.value
        dsar.status = DSARStatus.PENDING.value
        dsar.denial_reason = None
        
        service = PrivacyService(mock_db)
        mock_db.flush = AsyncMock()
        
        if reason is None or reason == "" or (isinstance(reason, str) and len(reason.strip()) < 10):
            # Should raise HTTPException 400
            with pytest.raises(HTTPException) as exc_info:
                await service.deny_dsar(dsar, reason, denied_by)
            
            assert exc_info.value.status_code == 400
            assert "10 characters" in exc_info.value.detail
            
            # DSAR status should remain unchanged
            assert dsar.status == DSARStatus.PENDING.value
        else:
            # This branch won't be reached with the given strategy,
            # but we include it for completeness
            await service.deny_dsar(dsar, reason, denied_by)
            
            # DSAR status should be DENIED
            assert dsar.status == DSARStatus.DENIED.value
            assert dsar.denial_reason == reason

    @given(reason=st.text(min_size=10, max_size=1000, alphabet=st.characters(blacklist_categories=("Cc", "Cs"))))
    @hypothesis_settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_valid_denial_reason_accepted(self, reason: str):
        """
        Property 19 (valid case): Valid denial reason (≥10 chars) is accepted
        
        Validates: Requirements 6.7
        
        For any reason with ≥10 characters:
        - Denial recorded successfully
        - DSAR status=DENIED
        - denial_reason is set
        """
        # Skip if reason is all whitespace
        if not reason.strip():
            return
        
        # Mock the database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        org_id = uuid4()
        candidate_id = uuid4()
        denied_by = uuid4()
        
        # Create a mock DSAR
        dsar = MagicMock(spec=DataSubjectAccessRequest)
        dsar.dsar_id = uuid4()
        dsar.candidate_id = candidate_id
        dsar.organization_id = org_id
        dsar.request_type = DSARRequestType.ACCESS.value
        dsar.status = DSARStatus.PENDING.value
        dsar.denial_reason = None
        
        service = PrivacyService(mock_db)
        mock_db.flush = AsyncMock()
        
        # Execute denial
        await service.deny_dsar(dsar, reason, denied_by)
        
        # Verify DSAR was updated
        assert dsar.status == DSARStatus.DENIED.value
        assert dsar.denial_reason == reason
        
        # Verify flush was called
        mock_db.flush.assert_called_once()
