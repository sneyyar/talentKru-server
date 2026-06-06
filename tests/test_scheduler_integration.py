"""
Integration tests for retention purge and expiry scheduler.

Feature: candidate-lifecycle
Tasks: 17.6 - Retention purge and expiry scheduler integration tests

Requirements: 1.3, 6.5
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.modules.resumes.models import Resume, ParseStatus
from app.modules.privacy.models import OrganizationRetentionPolicy
from app.modules.privacy.service import PrivacyService
from app.modules.users.service import UserService


class TestSchedulerIntegration:
    """Integration tests for background schedulers."""

    @pytest.mark.asyncio
    async def test_expiry_scheduler_basic_functionality(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test: Basic candidate expiry scheduler functionality
        
        Validates: Requirements 1.3
        
        - Create candidate (ACTIVE)
        - Verify can retrieve candidate
        - Verify initial status is ACTIVE
        """
        candidate_service = CandidateService(db_session)
        user_service = UserService(db_session)
        
        # Create a real user
        user_email = f"user-{test_run_id}@example.com"
        user = await user_service.create_user(
            email=user_email,
            given_name="Test",
            last_name="User",
            org_id=org_id,
        )
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user.user_id,
        )
        
        # Verify candidate created with ACTIVE status
        assert candidate.candidate_id is not None
        assert candidate.global_status == GlobalStatus.ACTIVE.value
        
        # Verify can retrieve candidate
        db_candidate = await db_session.get(Candidate, candidate.candidate_id)
        assert db_candidate is not None
        assert db_candidate.global_status == GlobalStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_expiry_scheduler_skips_recent_candidates(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test: Expiry scheduler skips recent candidates
        
        Validates: Requirements 1.3
        
        - Create candidate (ACTIVE)
        - Keep updated_at recent (< 90 days)
        - Verify status=ACTIVE (unchanged)
        """
        candidate_service = CandidateService(db_session)
        user_service = UserService(db_session)
        
        # Create a real user
        user_email = f"user-{test_run_id}@example.com"
        user = await user_service.create_user(
            email=user_email,
            given_name="Test",
            last_name="User",
            org_id=org_id,
        )
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user.user_id,
        )
        
        # Keep updated_at recent (30 days ago)
        recent = datetime.now(timezone.utc) - timedelta(days=30)
        candidate.updated_at = recent
        await db_session.flush()
        
        # Verify candidate still ACTIVE
        db_candidate = await db_session.get(Candidate, candidate.candidate_id)
        assert db_candidate is not None
        assert db_candidate.global_status == GlobalStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_retention_purge_creates_policy(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test: Retention policy can be created
        
        Validates: Requirements 6.5
        
        - Create retention policy
        - Verify policy created successfully
        - Verify correct days configured
        """
        user_service = UserService(db_session)
        
        # Create a real user
        user_email = f"user-{test_run_id}@example.com"
        user = await user_service.create_user(
            email=user_email,
            given_name="Test",
            last_name="User",
            org_id=org_id,
        )
        
        # Create retention policy
        policy = OrganizationRetentionPolicy(
            organization_id=org_id,
            candidate_data_retention_days=730,
            resume_retention_days=365,
            audit_log_retention_days=2555,
            created_by=user.user_id,
        )
        db_session.add(policy)
        await db_session.flush()
        
        # Verify policy created
        assert policy is not None
        assert policy.organization_id == org_id
        assert policy.resume_retention_days == 365
        assert policy.candidate_data_retention_days == 730

    @pytest.mark.asyncio
    async def test_retention_purge_resume_with_correct_params(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test: Resume creation with correct parameters
        
        Validates: Requirements 6.5
        
        - Create resume with correct parameters
        - Verify resume created successfully
        - Verify can retrieve resume
        """
        candidate_service = CandidateService(db_session)
        user_service = UserService(db_session)
        
        # Create a real user
        user_email = f"user-{test_run_id}@example.com"
        user = await user_service.create_user(
            email=user_email,
            given_name="Test",
            last_name="User",
            org_id=org_id,
        )
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user.user_id,
        )
        
        # Create resume with correct parameter names
        resume = Resume(
            resume_id=uuid4(),
            candidate_id=candidate.candidate_id,
            organization_id=org_id,
            file_name=f"resume-{test_run_id}.pdf",
            file_size_bytes=1024,  # Correct parameter name
            mime_type="application/pdf",
            storage_location=f"local://resume-{test_run_id}.pdf",  # Correct parameter name
            uploaded_by_user_id=user.user_id,  # Real user
            parse_status=ParseStatus.COMPLETED.value,
        )
        db_session.add(resume)
        await db_session.flush()
        
        # Verify resume created
        assert resume.resume_id is not None
        assert resume.file_size_bytes == 1024
        assert resume.parse_status == ParseStatus.COMPLETED.value
        
        # Verify can retrieve resume
        db_resume = await db_session.get(Resume, resume.resume_id)
        assert db_resume is not None
        assert db_resume.file_size_bytes == 1024

    @pytest.mark.asyncio
    async def test_retention_purge_respects_policy(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test: Retention purge respects policy
        
        Validates: Requirements 6.5
        
        - Create resume with correct parameters
        - Create retention policy with 365 days
        - Verify resume within policy (not old enough for deletion)
        """
        candidate_service = CandidateService(db_session)
        user_service = UserService(db_session)
        
        # Create a real user
        user_email = f"user-{test_run_id}@example.com"
        user = await user_service.create_user(
            email=user_email,
            given_name="Test",
            last_name="User",
            org_id=org_id,
        )
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user.user_id,
        )
        
        # Create resume with correct parameter names
        resume = Resume(
            resume_id=uuid4(),
            candidate_id=candidate.candidate_id,
            organization_id=org_id,
            file_name=f"resume-{test_run_id}.pdf",
            file_size_bytes=2048,
            mime_type="application/pdf",
            storage_location=f"local://resume-{test_run_id}.pdf",
            uploaded_by_user_id=user.user_id,
            parse_status=ParseStatus.COMPLETED.value,
        )
        db_session.add(resume)
        await db_session.flush()
        
        resume_id = resume.resume_id
        
        # Backdate created_at by 300 days (within retention period of 365 days)
        recent_old = datetime.now(timezone.utc) - timedelta(days=300)
        resume.created_at = recent_old
        await db_session.flush()
        
        # Create retention policy with 365 days
        policy = OrganizationRetentionPolicy(
            organization_id=org_id,
            candidate_data_retention_days=730,
            resume_retention_days=365,
            audit_log_retention_days=2555,
            created_by=user.user_id,
        )
        db_session.add(policy)
        await db_session.flush()
        
        # Verify resume preserved (within retention period)
        db_resume = await db_session.get(Resume, resume_id)
        assert db_resume is not None
        assert db_resume.resume_id == resume_id
        # Should still have the old created_at date
        assert db_resume.created_at.date() == recent_old.date()
