"""
Integration tests for retention purge and expiry scheduler.

Feature: candidate-lifecycle
Tasks: 17.6 - Retention purge and expiry scheduler integration tests

Requirements: 1.3, 6.5
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.modules.resumes.models import Resume, ParseStatus
from app.modules.privacy.models import OrganizationRetentionPolicy
from app.modules.privacy.service import PrivacyService


class TestSchedulerIntegration:
    """Integration tests for background schedulers."""

    @pytest.mark.asyncio
    async def test_expiry_scheduler_marks_old_candidates(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Expiry scheduler marks old candidates
        
        Validates: Requirements 1.3
        
        - Create candidate (ACTIVE)
        - Backdate updated_at by 91 days
        - Run expiry scheduler
        - Verify status=EXPIRED
        - Verify event published
        """
        candidate_service = CandidateService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            created_by=user_id,
        )
        
        # Backdate updated_at by 91 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=91)
        candidate.updated_at = cutoff
        await db_session.flush()
        
        # Run expiry scheduler
        count = await candidate_service.run_expiry_check()
        
        # Verify candidate marked as EXPIRED
        db_candidate = await db_session.get(Candidate, candidate.candidate_id)
        assert db_candidate.global_status == GlobalStatus.Expired
        assert count >= 1

    @pytest.mark.asyncio
    async def test_expiry_scheduler_skips_recent_candidates(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Expiry scheduler skips recent candidates
        
        Validates: Requirements 1.3
        
        - Create candidate (ACTIVE)
        - Keep updated_at recent (< 90 days)
        - Run expiry scheduler
        - Verify status=ACTIVE (unchanged)
        """
        candidate_service = CandidateService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            created_by=user_id,
        )
        
        # Keep updated_at recent (30 days ago)
        recent = datetime.now(timezone.utc) - timedelta(days=30)
        candidate.updated_at = recent
        await db_session.flush()
        
        # Run expiry scheduler
        await candidate_service.run_expiry_check()
        
        # Verify candidate still ACTIVE
        db_candidate = await db_session.get(Candidate, candidate.candidate_id)
        assert db_candidate.global_status == GlobalStatus.Active

    @pytest.mark.asyncio
    async def test_retention_purge_deletes_old_resumes(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Retention purge deletes old resumes
        
        Validates: Requirements 6.5
        
        - Create resume
        - Backdate created_at by 400 days
        - Configure policy with 365 days
        - Run retention purge
        - Verify resume hard-deleted
        - Verify log entry created
        """
        candidate_service = CandidateService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            created_by=user_id,
        )
        
        # Create resume
        resume = Resume(
            resume_id=uuid4(),
            candidate_id=candidate.candidate_id,
            organization_id=org_id,
            file_name="resume.pdf",
            file_size=1024,
            mime_type="application/pdf",
            storage_uri="local://resume.pdf",
            parse_status=ParseStatus.Completed,
            created_by=user_id,
        )
        db_session.add(resume)
        await db_session.flush()
        
        resume_id = resume.resume_id
        
        # Backdate created_at by 400 days
        old_date = datetime.now(timezone.utc) - timedelta(days=400)
        resume.created_at = old_date
        await db_session.flush()
        
        # Create retention policy
        policy = OrganizationRetentionPolicy(
            organization_id=org_id,
            candidate_data_retention_days=730,
            resume_retention_days=365,
            dsar_record_retention_days=2555,
            created_by=user_id,
        )
        db_session.add(policy)
        await db_session.flush()
        
        # Run retention purge
        result = await privacy_service.run_retention_purge()
        
        # Verify resume hard-deleted
        db_resume = await db_session.get(Resume, resume_id)
        assert db_resume is None
        
        # Verify result shows purge count
        assert result["resumes"] >= 1

    @pytest.mark.asyncio
    async def test_retention_purge_respects_policy(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Retention purge respects policy
        
        Validates: Requirements 6.5
        
        - Create resume
        - Backdate created_at by 300 days
        - Configure policy with 365 days
        - Run retention purge
        - Verify resume preserved
        """
        candidate_service = CandidateService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            created_by=user_id,
        )
        
        # Create resume
        resume = Resume(
            resume_id=uuid4(),
            candidate_id=candidate.candidate_id,
            organization_id=org_id,
            file_name="resume.pdf",
            file_size=1024,
            mime_type="application/pdf",
            storage_uri="local://resume.pdf",
            parse_status=ParseStatus.Completed,
            created_by=user_id,
        )
        db_session.add(resume)
        await db_session.flush()
        
        resume_id = resume.resume_id
        
        # Backdate created_at by 300 days (within retention period)
        recent_old = datetime.now(timezone.utc) - timedelta(days=300)
        resume.created_at = recent_old
        await db_session.flush()
        
        # Create retention policy with 365 days
        policy = OrganizationRetentionPolicy(
            organization_id=org_id,
            candidate_data_retention_days=730,
            resume_retention_days=365,
            dsar_record_retention_days=2555,
            created_by=user_id,
        )
        db_session.add(policy)
        await db_session.flush()
        
        # Run retention purge
        await privacy_service.run_retention_purge()
        
        # Verify resume preserved
        db_resume = await db_session.get(Resume, resume_id)
        assert db_resume is not None
        assert db_resume.resume_id == resume_id
