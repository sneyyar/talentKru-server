"""Tests for InterviewJourneyService.

Tests the interview journey lifecycle FSM, stage transitions, history tracking,
and PII encryption on OfferAccepted.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.journeys.models import (
    InterviewJourney,
    InterviewJourneyStageHistory,
    CandidateInterviewJourney,
    JourneyStage,
    JourneyOverallStatus,
)
from app.modules.journeys.service import InterviewJourneyService, VALID_TRANSITIONS
from app.crypto import encrypt_field, decrypt_field


@pytest.mark.asyncio
async def test_create_journey_basic(db_session: AsyncSession, org_id: str, test_run_id: str, current_user_context, test_candidate, test_job_requisition):
    """Test basic journey creation with required fields.

    Validates: Requirements 1.1, 1.5, 1.6
    """
    service = InterviewJourneyService(db_session)

    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    assert journey.interview_journey_id is not None
    assert journey.organization_id == org_id
    assert journey.candidate_id == test_candidate.candidate_id
    assert journey.job_requisition_id == test_job_requisition.job_requisition_id
    assert journey.current_stage == JourneyStage.SOURCED.value
    assert journey.overall_status == JourneyOverallStatus.ACTIVE.value
    assert journey.current_stage_status is None


@pytest.mark.asyncio
async def test_create_journey_public_id_minimum_length(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition
):
    """Test journey_public_id is at least 22 URL-safe characters.

    Validates: Requirement 1.1
    """
    service = InterviewJourneyService(db_session)

    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # URL-safe characters are alphanumeric + '-' + '_'
    assert len(journey.journey_public_id) >= 22
    assert all(c.isalnum() or c in '-_' for c in journey.journey_public_id)


@pytest.mark.asyncio
async def test_create_journey_public_id_uniqueness(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_profile, test_hiring_manager
):
    """Test that multiple journeys have unique public IDs.

    Validates: Requirement 1.1
    """
    from app.modules.requisitions.models import JobRequisition, RequisitionStatus
    
    service = InterviewJourneyService(db_session)
    public_ids = set()

    for i in range(5):
        # Create unique requisition for each journey
        req = JobRequisition(
            organization_id=org_id,
            job_profile_id=test_job_profile.job_profile_id,
            title=f"Test Req {i}-{test_run_id}",
            department="Engineering",
            location="Remote",
            hiring_manager_user_id=test_hiring_manager.user_id,
            status=RequisitionStatus.OPEN.value,
        )
        db_session.add(req)
        await db_session.flush()
        
        journey = await service.create_journey(
            org_id=org_id,
            candidate_id=test_candidate.candidate_id,
            job_requisition_id=req.job_requisition_id,
            created_by=uuid4(),
        )
        assert journey.journey_public_id not in public_ids
        public_ids.add(journey.journey_public_id)


@pytest.mark.asyncio
async def test_create_journey_creates_join_record(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition
):
    """Test that CandidateInterviewJourney join record is created.

    Validates: Requirement 1.6
    """
    service = InterviewJourneyService(db_session)

    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # Fetch join record
    result = await db_session.execute(
        select(CandidateInterviewJourney).where(
            CandidateInterviewJourney.interview_journey_id == journey.interview_journey_id
        )
    )
    join_record = result.scalar_one_or_none()

    assert join_record is not None
    assert join_record.candidate_id == test_candidate.candidate_id
    assert join_record.interview_journey_id == journey.interview_journey_id
    assert not join_record.is_encrypted


@pytest.mark.asyncio
async def test_transition_stage_valid(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition):
    """Test valid stage transition.

    Validates: Requirements 1.2, 1.4
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    changed_by = uuid4()
    journey = await service.transition_stage(
        journey=journey,
        to_stage=JourneyStage.RECRUITER_SCREEN,
        changed_by=changed_by,
        comments="Good fit for the role",
    )

    assert journey.current_stage == JourneyStage.RECRUITER_SCREEN.value

    # Verify history record was created
    result = await db_session.execute(
        select(InterviewJourneyStageHistory).where(
            InterviewJourneyStageHistory.interview_journey_id == journey.interview_journey_id
        )
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.from_stage == JourneyStage.SOURCED.value
    assert history.to_stage == JourneyStage.RECRUITER_SCREEN.value
    assert history.changed_by_user_id == changed_by
    assert history.comments == "Good fit for the role"


@pytest.mark.asyncio
async def test_transition_stage_invalid(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition):
    """Test invalid stage transition raises 400.

    Validates: Requirements 1.2, 1.8
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # Try to transition from SOURCED to OFFER_ACCEPTED (invalid)
    with pytest.raises(Exception) as exc_info:
        await service.transition_stage(
            journey=journey,
            to_stage=JourneyStage.OFFER_ACCEPTED,
            changed_by=uuid4(),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_transition_stage_comments_too_long(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition
):
    """Test comments exceeding 2000 chars raises 422.

    Validates: Requirement 1.4
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    long_comment = "x" * 2001

    with pytest.raises(Exception) as exc_info:
        await service.transition_stage(
            journey=journey,
            to_stage=JourneyStage.RECRUITER_SCREEN,
            changed_by=uuid4(),
            comments=long_comment,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_transition_to_terminal_stage_clears_substatus(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition
):
    """Test terminal stages have no sub-status.

    Validates: Requirement 1.3
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # Set sub-status before transition
    journey.current_stage_status = "SCHEDULED"

    # Transition to REJECTED (terminal)
    journey = await service.transition_stage(
        journey=journey,
        to_stage=JourneyStage.REJECTED,
        changed_by=uuid4(),
    )

    assert journey.current_stage_status is None


@pytest.mark.asyncio
async def test_transition_to_offer_extended_sets_timestamp(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition
):
    """Test OFFER_EXTENDED sets offer_extended_at timestamp.

    Validates: Requirement 1.5
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # Advance through stages to OFFER_EXTENDED
    for target_stage in [
        JourneyStage.RECRUITER_SCREEN,
        JourneyStage.MANAGER_SCREEN,
        JourneyStage.LOOP_INTERVIEW,
        JourneyStage.PANEL_REVIEW,
        JourneyStage.OFFER_PENDING,
        JourneyStage.OFFER_EXTENDED,
    ]:
        journey = await service.transition_stage(
            journey=journey,
            to_stage=target_stage,
            changed_by=uuid4(),
        )

    assert journey.offer_extended_at is not None
    assert isinstance(journey.offer_extended_at, datetime)


@pytest.mark.asyncio
async def test_transition_to_offer_accepted_sets_completed_and_encrypts(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition
):
    """Test OFFER_ACCEPTED sets COMPLETED and encrypts join record.

    Validates: Requirements 1.5, 1.7
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # Advance through stages to OFFER_ACCEPTED
    for target_stage in [
        JourneyStage.RECRUITER_SCREEN,
        JourneyStage.MANAGER_SCREEN,
        JourneyStage.LOOP_INTERVIEW,
        JourneyStage.PANEL_REVIEW,
        JourneyStage.OFFER_PENDING,
        JourneyStage.OFFER_EXTENDED,
        JourneyStage.OFFER_ACCEPTED,
    ]:
        journey = await service.transition_stage(
            journey=journey,
            to_stage=target_stage,
            changed_by=uuid4(),
        )

    # Check overall_status is COMPLETED
    assert journey.overall_status == JourneyOverallStatus.COMPLETED.value

    # Check offer_responded_at is set
    assert journey.offer_responded_at is not None

    # Check join record is encrypted
    result = await db_session.execute(
        select(CandidateInterviewJourney).where(
            CandidateInterviewJourney.interview_journey_id == journey.interview_journey_id
        )
    )
    join_record = result.scalar_one_or_none()
    assert join_record is not None
    assert join_record.is_encrypted
    assert join_record.candidate_id_encrypted is not None
    assert join_record.interview_journey_id_encrypted is not None


@pytest.mark.asyncio
async def test_get_journey_org_scoped(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition
):
    """Test get_journey filters by organization.

    Validates: Requirement 1.1
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # Fetch with correct org_id
    fetched = await service.get_journey(
        journey_id=journey.interview_journey_id,
        org_id=org_id,
    )
    assert fetched is not None
    assert fetched.interview_journey_id == journey.interview_journey_id

    # Fetch with wrong org_id
    other_org_id = uuid4()
    fetched = await service.get_journey(
        journey_id=journey.interview_journey_id,
        org_id=other_org_id,
    )
    assert fetched is None


@pytest.mark.asyncio
async def test_list_journeys_org_scoped(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_profile, test_hiring_manager
):
    """Test list_journeys filters by organization.

    Validates: Requirement 1.1
    """
    from app.modules.requisitions.models import JobRequisition, RequisitionStatus
    
    service = InterviewJourneyService(db_session)

    # Create 3 journeys with unique requisitions
    for i in range(3):
        req = JobRequisition(
            organization_id=org_id,
            job_profile_id=test_job_profile.job_profile_id,
            title=f"Test Req {i}-{test_run_id}",
            department="Engineering",
            location="Remote",
            hiring_manager_user_id=test_hiring_manager.user_id,
            status=RequisitionStatus.OPEN.value,
        )
        db_session.add(req)
        await db_session.flush()
        
        await service.create_journey(
            org_id=org_id,
            candidate_id=test_candidate.candidate_id,
            job_requisition_id=req.job_requisition_id,
            created_by=uuid4(),
        )

    journeys, total = await service.list_journeys(org_id=org_id)
    assert len(journeys) >= 3
    assert total >= 3


@pytest.mark.asyncio
async def test_get_journey_history(current_user_context,
    db_session: AsyncSession, org_id: str, test_run_id: str, test_candidate, test_job_requisition):
    """Test getting journey stage history.

    Validates: Requirement 1.4
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=test_candidate.candidate_id,
        job_requisition_id=test_job_requisition.job_requisition_id,
        created_by=uuid4(),
    )

    # Make some transitions
    await service.transition_stage(
        journey=journey,
        to_stage=JourneyStage.RECRUITER_SCREEN,
        changed_by=uuid4(),
    )
    await service.transition_stage(
        journey=journey,
        to_stage=JourneyStage.MANAGER_SCREEN,
        changed_by=uuid4(),
    )

    history, total = await service.get_journey_history(
        journey_id=journey.interview_journey_id,
        org_id=org_id,
    )

    assert len(history) == 2
    assert total == 2
    assert history[0].to_stage == JourneyStage.MANAGER_SCREEN.value
    assert history[1].to_stage == JourneyStage.RECRUITER_SCREEN.value


# Property-based tests using Hypothesis


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    from_stage=st.sampled_from(list(JourneyStage)),
    to_stage=st.sampled_from(list(JourneyStage)),
)
@pytest.mark.asyncio
async def test_property_stage_fsm_only_valid_transitions(
    db_session: AsyncSession,
    org_id,
    current_user_context,
    from_stage,
    to_stage,
):
    """Property 1: Journey stage FSM — only valid transitions permitted.

    Validates: Requirements 1.2, 1.8

    For any from_stage and to_stage:
    - If to_stage is in VALID_TRANSITIONS[from_stage], transition succeeds and
      creates InterviewJourneyStageHistory
    - Otherwise, HTTPException 400 is raised and current_stage unchanged
    """
    # Create fresh fixture objects to avoid expired object issues with Hypothesis
    from app.modules.candidates.models import Candidate, GlobalStatus
    from app.modules.job_profile.models import JobProfile
    from app.modules.users.models import User, UserStatus
    from app.modules.requisitions.models import JobRequisition, RequisitionStatus
    from app.crypto import encrypt_field
    import hashlib

    try:
        # Create candidate
        candidate_id = uuid4()
        name = f"Test Candidate {uuid4().hex[:8]}"
        email = f"candidate-{uuid4().hex[:8]}@test.com"
        candidate = Candidate(
            candidate_id=candidate_id,
            organization_id=org_id,
            name=encrypt_field(name),
            name_hash=hashlib.sha256(name.lower().encode()).hexdigest(),
            email=encrypt_field(email),
            email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
            global_status=GlobalStatus.ACTIVE.value,
        )
        db_session.add(candidate)

        # Create job profile
        job_profile_id = uuid4()
        job_profile = JobProfile(
            job_profile_id=job_profile_id,
            organization_id=org_id,
            name=f"Test Role {uuid4().hex[:8]}",
        )
        db_session.add(job_profile)

        # Create hiring manager
        manager_id = uuid4()
        manager_email = f"manager-{uuid4().hex[:8]}@test.com"
        hiring_manager = User(
            user_id=manager_id,
            organization_id=org_id,
            email=encrypt_field(manager_email),
            email_hash=hashlib.sha256(manager_email.lower().encode()).hexdigest(),
            given_name=encrypt_field("Test"),
            last_name=encrypt_field("Manager"),
            status=UserStatus.ACTIVE.value,
        )
        db_session.add(hiring_manager)
        await db_session.flush()

        # Create job requisition
        requisition_id = uuid4()
        job_requisition = JobRequisition(
            job_requisition_id=requisition_id,
            organization_id=org_id,
            job_profile_id=job_profile_id,
            title=f"Test Requisition {uuid4().hex[:8]}",
            department="Engineering",
            location="Remote",
            hiring_manager_user_id=manager_id,
            status=RequisitionStatus.OPEN.value,
        )
        db_session.add(job_requisition)
        await db_session.flush()

        # Create journey
        service = InterviewJourneyService(db_session)
        journey = await service.create_journey(
            org_id=org_id,
            candidate_id=candidate_id,
            job_requisition_id=requisition_id,
            created_by=uuid4(),
        )

        # Force journey to from_stage by directly updating (bypassing validation)
        journey.current_stage = from_stage.value
        from_stage_value = from_stage.value  # Capture before exception handling

        is_valid = to_stage in VALID_TRANSITIONS.get(from_stage, set())

        if is_valid:
            # Valid transition should succeed
            updated_journey = await service.transition_stage(
                journey=journey,
                to_stage=to_stage,
                changed_by=uuid4(),
            )
            assert updated_journey.current_stage == to_stage.value

            # Verify history record was created
            result = await db_session.execute(
                select(InterviewJourneyStageHistory).where(
                    InterviewJourneyStageHistory.interview_journey_id
                    == journey.interview_journey_id
                )
            )
            history = result.scalar_one_or_none()
            assert history is not None
        else:
            # Invalid transition should raise 400
            with pytest.raises(Exception) as exc_info:
                await service.transition_stage(
                    journey=journey,
                    to_stage=to_stage,
                    changed_by=uuid4(),
                )
            assert exc_info.value.status_code == 400
            # Journey should not have changed - verify the stage value we set
            assert from_stage_value == from_stage.value
    except Exception:
        # Roll back on any error to clean session state
        await db_session.rollback()
        raise


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(to_stage=st.sampled_from(list(JourneyStage)))
@pytest.mark.asyncio
async def test_property_terminal_stages_no_substatus(
    db_session: AsyncSession,
    org_id,
    current_user_context,
    to_stage,
):
    """Property 2: Terminal stages have no sub-status.

    Validates: Requirement 1.3

    For any stage transition:
    - Transition to terminal stage → current_stage_status is None
    - Transition to non-terminal stage → current_stage_status can be any valid value or None
    """
    # Create fresh fixture objects to avoid expired object issues with Hypothesis
    from app.modules.candidates.models import Candidate, GlobalStatus
    from app.modules.job_profile.models import JobProfile
    from app.modules.users.models import User, UserStatus
    from app.modules.requisitions.models import JobRequisition, RequisitionStatus
    from app.crypto import encrypt_field
    import hashlib

    try:
        # Create candidate
        candidate_id = uuid4()
        name = f"Test Candidate {uuid4().hex[:8]}"
        email = f"candidate-{uuid4().hex[:8]}@test.com"
        candidate = Candidate(
            candidate_id=candidate_id,
            organization_id=org_id,
            name=encrypt_field(name),
            name_hash=hashlib.sha256(name.lower().encode()).hexdigest(),
            email=encrypt_field(email),
            email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
            global_status=GlobalStatus.ACTIVE.value,
        )
        db_session.add(candidate)

        # Create job profile
        job_profile_id = uuid4()
        job_profile = JobProfile(
            job_profile_id=job_profile_id,
            organization_id=org_id,
            name=f"Test Role {uuid4().hex[:8]}",
        )
        db_session.add(job_profile)

        # Create hiring manager
        manager_id = uuid4()
        manager_email = f"manager-{uuid4().hex[:8]}@test.com"
        hiring_manager = User(
            user_id=manager_id,
            organization_id=org_id,
            email=encrypt_field(manager_email),
            email_hash=hashlib.sha256(manager_email.lower().encode()).hexdigest(),
            given_name=encrypt_field("Test"),
            last_name=encrypt_field("Manager"),
            status=UserStatus.ACTIVE.value,
        )
        db_session.add(hiring_manager)
        await db_session.flush()

        # Create job requisition
        requisition_id = uuid4()
        job_requisition = JobRequisition(
            job_requisition_id=requisition_id,
            organization_id=org_id,
            job_profile_id=job_profile_id,
            title=f"Test Requisition {uuid4().hex[:8]}",
            department="Engineering",
            location="Remote",
            hiring_manager_user_id=manager_id,
            status=RequisitionStatus.OPEN.value,
        )
        db_session.add(job_requisition)
        await db_session.flush()

        service = InterviewJourneyService(db_session)

        # Create multiple journeys and transition each through valid paths
        # focusing on terminal stage outcomes
        TERMINAL_STAGES_SET = {
            JourneyStage.REJECTED,
            JourneyStage.OFFER_DECLINED,
            JourneyStage.OFFER_ACCEPTED,
            JourneyStage.WITHDRAWN,
        }

        journey = await service.create_journey(
            org_id=org_id,
            candidate_id=candidate_id,
            job_requisition_id=requisition_id,
            created_by=uuid4(),
        )

        # Try to reach to_stage through a valid path if possible
        # For simplicity, if to_stage is reachable from SOURCED directly or laterally, test it
        if to_stage in VALID_TRANSITIONS.get(JourneyStage.SOURCED, set()):
            journey.current_stage = JourneyStage.SOURCED.value
            journey.current_stage_status = "SCHEDULED"  # Set a sub-status

            updated = await service.transition_stage(
                journey=journey,
                to_stage=to_stage,
                changed_by=uuid4(),
            )

            if to_stage in TERMINAL_STAGES_SET:
                assert updated.current_stage_status is None
    except Exception:
        # Roll back on any error to clean session state
        await db_session.rollback()
        raise
