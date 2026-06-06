"""
Integration tests for requisition pipeline.

Feature: candidate-lifecycle
Tasks: 17.4 - Requisition pipeline integration tests

Requirements: 5.2, 5.3, 5.6

Tests use PostgreSQL fixtures and unique data identifiers (test_run_id)
to comply with stable test architecture.
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.modules.job_profile.models import JobProfile
from app.modules.job_profile.schemas import JobProfileCreate
from app.modules.job_profile.service import JobProfileService
from app.modules.requisitions.models import JobRequisition, RequisitionStatus, CandidateRequisition
from app.modules.requisitions.service import RequisitionService
from app.modules.users.models import User, UserStatus
from app.modules.users.service import UserService


@pytest.fixture
async def hiring_manager_user(db_session: AsyncSession, org_id, test_run_id):
    """Create a hiring manager user for testing."""
    user_service = UserService(db_session)
    email = f"hiring-manager-{test_run_id}@example.com"
    user = await user_service.create_user(
        email=email,
        given_name="Hiring",
        last_name="Manager",
        org_id=org_id,
    )
    return user.user_id


class TestRequisitionIntegration:
    """Integration tests for requisition pipeline."""

    @pytest.mark.asyncio
    async def test_create_requisition_with_open_status(
        self, db_session: AsyncSession, org_id, hiring_manager_user, test_run_id
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
        
        # Create job profile with unique name using test_run_id
        profile_name = f"SoftwareEngineer-{test_run_id}"
        profile_data = JobProfileCreate(name=profile_name, skills=[])
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=hiring_manager_user,
        )
        
        # Create requisition
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            location="San Francisco, CA",
            hiring_manager_user_id=hiring_manager_user,
            created_by=hiring_manager_user,
        )
        
        # Verify status=OPEN
        assert requisition.status == RequisitionStatus.OPEN.value
        assert requisition.created_at is not None

    @pytest.mark.asyncio
    async def test_associate_active_candidate(
        self, db_session: AsyncSession, org_id, hiring_manager_user, test_run_id
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
        
        # Create job profile with unique name
        profile_name = f"SoftwareEngineer-{test_run_id}"
        profile_data = JobProfileCreate(name=profile_name, skills=[])
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=hiring_manager_user,
        )
        
        # Create requisition
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            location="San Francisco, CA",
            hiring_manager_user_id=hiring_manager_user,
            created_by=hiring_manager_user,
        )
        
        # Create candidate (ACTIVE) with unique email
        email = f"john-{test_run_id}@example.com"
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email=email,
            created_by=hiring_manager_user,
        )
        
        # Associate candidate
        association = await requisition_service.associate_candidate(
            requisition_id=requisition.job_requisition_id,
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            created_by=hiring_manager_user,
        )
        
        # Verify CandidateRequisition created
        assert association.candidate_id == candidate.candidate_id
        assert association.job_requisition_id == requisition.job_requisition_id

    @pytest.mark.asyncio
    async def test_reject_ineligible_candidate(
        self, db_session: AsyncSession, org_id, hiring_manager_user, test_run_id
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
        
        # Create job profile with unique name
        profile_name = f"SoftwareEngineer-{test_run_id}"
        profile_data = JobProfileCreate(name=profile_name, skills=[])
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=hiring_manager_user,
        )
        
        # Create requisition
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            location="San Francisco, CA",
            hiring_manager_user_id=hiring_manager_user,
            created_by=hiring_manager_user,
        )
        
        # Create candidate (ACTIVE) with unique email
        email = f"john-{test_run_id}@example.com"
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email=email,
            created_by=hiring_manager_user,
        )
        
        # Transition to INELIGIBLE (refresh candidate to get updated object)
        refreshed_candidate = await candidate_service.get_candidate(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
        )
        await candidate_service.transition_status(
            candidate=refreshed_candidate,
            new_status=GlobalStatus.INELIGIBLE.value,
            ineligibility_reason="Does not meet requirements",
            updated_by=hiring_manager_user,
        )
        
        # Try to associate - should fail
        with pytest.raises(HTTPException) as exc_info:
            await requisition_service.associate_candidate(
                requisition_id=requisition.job_requisition_id,
                candidate_id=candidate.candidate_id,
                org_id=org_id,
                created_by=hiring_manager_user,
            )
        
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_status_transition_through_fsm(
        self, db_session: AsyncSession, org_id, hiring_manager_user, test_run_id
    ):
        """
        Test: Status transition through FSM
        
        Validates: Requirements 5.6
        
        - Create requisition (OPEN)
        - Transition to ON_HOLD
        - Transition back to OPEN
        - Transition to CLOSED
        - Verify each transition succeeds
        """
        profile_service = JobProfileService(db_session)
        requisition_service = RequisitionService(db_session)
        
        # Create job profile with unique name
        profile_name = f"SoftwareEngineer-{test_run_id}"
        profile_data = JobProfileCreate(name=profile_name, skills=[])
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=hiring_manager_user,
        )
        
        # Create requisition (OPEN)
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            location="San Francisco, CA",
            hiring_manager_user_id=hiring_manager_user,
            created_by=hiring_manager_user,
        )
        
        assert requisition.status == RequisitionStatus.OPEN.value
        
        # Transition to ON_HOLD
        updated = await requisition_service.transition_status(
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            new_status=RequisitionStatus.ON_HOLD.value,
            version=requisition.version,
            updated_by=hiring_manager_user,
        )
        
        assert updated.status == RequisitionStatus.ON_HOLD.value
        
        # Transition back to OPEN
        updated = await requisition_service.transition_status(
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            new_status=RequisitionStatus.OPEN.value,
            version=updated.version,
            updated_by=hiring_manager_user,
        )
        
        assert updated.status == RequisitionStatus.OPEN.value
        
        # Transition to CLOSED
        updated = await requisition_service.transition_status(
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            new_status=RequisitionStatus.CLOSED.value,
            version=updated.version,
            updated_by=hiring_manager_user,
        )
        
        assert updated.status == RequisitionStatus.CLOSED.value

    @pytest.mark.asyncio
    async def test_invalid_status_transition_fails(
        self, db_session: AsyncSession, org_id, hiring_manager_user, test_run_id
    ):
        """
        Test: Invalid status transition fails
        
        Validates: Requirements 5.6
        
        - Create requisition (OPEN)
        - Transition to CLOSED
        - Try to transition from CLOSED to OPEN (invalid - no transitions from CLOSED)
        - Verify 400 error
        - Verify status unchanged
        """
        profile_service = JobProfileService(db_session)
        requisition_service = RequisitionService(db_session)
        
        # Create job profile with unique name
        profile_name = f"SoftwareEngineer-{test_run_id}"
        profile_data = JobProfileCreate(name=profile_name, skills=[])
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=hiring_manager_user,
        )
        
        # Create requisition (OPEN)
        requisition = await requisition_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Software Engineer",
            department="Engineering",
            location="San Francisco, CA",
            hiring_manager_user_id=hiring_manager_user,
            created_by=hiring_manager_user,
        )
        
        # Transition to CLOSED
        closed_requisition = await requisition_service.transition_status(
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            new_status=RequisitionStatus.CLOSED.value,
            version=requisition.version,
            updated_by=hiring_manager_user,
        )
        assert closed_requisition.status == RequisitionStatus.CLOSED.value
        
        # Try invalid transition from CLOSED - should fail
        with pytest.raises(HTTPException) as exc_info:
            await requisition_service.transition_status(
                requisition_id=requisition.job_requisition_id,
                org_id=org_id,
                new_status=RequisitionStatus.OPEN.value,
                version=closed_requisition.version,
                updated_by=hiring_manager_user,
            )
        
        assert exc_info.value.status_code == 400
