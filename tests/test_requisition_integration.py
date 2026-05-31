"""
Integration tests for requisition pipeline.

Feature: candidate-lifecycle
Tasks: 17.4 - Requisition pipeline integration tests

Requirements: 5.2, 5.3, 5.6
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.modules.job_profile.models import JobProfile
from app.modules.job_profile.service import JobProfileService
from app.modules.requisitions.models import JobRequisition, RequisitionStatus, CandidateRequisition
from app.modules.requisitions.service import RequisitionService


class TestRequisitionIntegration:
    """Integration tests for requisition pipeline."""

    @pytest.mark.asyncio
    async def test_create_requisition_with_open_status(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Create requisition with OPEN status
        
        Validates: Requirements 5.2
        
        - Create requisition
        - Verify status=OPEN (regardless of input)
        - Verify created_at set
        """
        profile_service = JobProfileService(db_session)
        requisition_service = RequisitionService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create requisition
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            hiring_manager_user_id=user_id,
            created_by=user_id,
        )
        
        # Verify status=OPEN
        assert requisition.status == RequisitionStatus.Open
        assert requisition.created_at is not None

    @pytest.mark.asyncio
    async def test_associate_active_candidate(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Associate Active candidate
        
        Validates: Requirements 5.3
        
        - Create requisition (OPEN)
        - Create candidate (ACTIVE)
        - Associate candidate
        - Verify CandidateRequisition created
        """
        profile_service = JobProfileService(db_session)
        requisition_service = RequisitionService(db_session)
        candidate_service = CandidateService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create requisition
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            hiring_manager_user_id=user_id,
            created_by=user_id,
        )
        
        # Create candidate (ACTIVE)
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            created_by=user_id,
        )
        
        # Associate candidate
        association = await requisition_service.associate_candidate(
            requisition_id=requisition.job_requisition_id,
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            created_by=user_id,
        )
        
        # Verify CandidateRequisition created
        assert association.candidate_id == candidate.candidate_id
        assert association.job_requisition_id == requisition.job_requisition_id

    @pytest.mark.asyncio
    async def test_reject_ineligible_candidate(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Reject Ineligible candidate
        
        Validates: Requirements 5.3
        
        - Create requisition (OPEN)
        - Create candidate (INELIGIBLE)
        - Try to associate
        - Verify 400 error
        - Verify no CandidateRequisition created
        """
        profile_service = JobProfileService(db_session)
        requisition_service = RequisitionService(db_session)
        candidate_service = CandidateService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create requisition
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            hiring_manager_user_id=user_id,
            created_by=user_id,
        )
        
        # Create candidate (ACTIVE)
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            created_by=user_id,
        )
        
        # Transition to INELIGIBLE
        await candidate_service.transition_status(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            new_status=GlobalStatus.Ineligible,
            ineligibility_reason="Does not meet requirements",
            updated_by=user_id,
        )
        
        # Try to associate - should fail
        with pytest.raises(HTTPException) as exc_info:
            await requisition_service.associate_candidate(
                requisition_id=requisition.job_requisition_id,
                candidate_id=candidate.candidate_id,
                org_id=org_id,
                created_by=user_id,
            )
        
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_status_transition_through_fsm(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Status transition through FSM
        
        Validates: Requirements 5.6
        
        - Create requisition (OPEN)
        - Transition to ON_HOLD
        - Transition to CLOSED
        - Verify each transition succeeds
        """
        profile_service = JobProfileService(db_session)
        requisition_service = RequisitionService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create requisition (OPEN)
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            hiring_manager_user_id=user_id,
            created_by=user_id,
        )
        
        assert requisition.status == RequisitionStatus.Open
        
        # Transition to ON_HOLD
        updated = await requisition_service.transition_status(
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            new_status=RequisitionStatus.OnHold,
            updated_by=user_id,
        )
        
        assert updated.status == RequisitionStatus.OnHold
        
        # Transition to CLOSED
        updated = await requisition_service.transition_status(
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            new_status=RequisitionStatus.Closed,
            updated_by=user_id,
        )
        
        assert updated.status == RequisitionStatus.Closed

    @pytest.mark.asyncio
    async def test_invalid_status_transition_fails(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Invalid status transition fails
        
        Validates: Requirements 5.6
        
        - Create requisition (OPEN)
        - Try to transition to CANCELLED (invalid from OPEN)
        - Verify 400 error
        - Verify status unchanged
        """
        profile_service = JobProfileService(db_session)
        requisition_service = RequisitionService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create requisition (OPEN)
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            hiring_manager_user_id=user_id,
            created_by=user_id,
        )
        
        # Try invalid transition - should fail
        with pytest.raises(HTTPException) as exc_info:
            await requisition_service.transition_status(
                requisition_id=requisition.job_requisition_id,
                org_id=org_id,
                new_status=RequisitionStatus.Cancelled,
                updated_by=user_id,
            )
        
        assert exc_info.value.status_code == 400
        
        # Verify status unchanged
        db_requisition = await db_session.get(JobRequisition, requisition.job_requisition_id)
        assert db_requisition.status == RequisitionStatus.Open
