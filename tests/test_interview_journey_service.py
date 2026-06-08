"""Tests for InterviewJourneyService.

Tests the interview journey lifecycle FSM, stage transitions, history tracking,
and PII encryption on OfferAccepted.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from hypothesis import given, strategies as st
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
async def test_create_journey_basic(db_session: AsyncSession, org_id: str, test_run_id: str):
    """Test basic journey creation with required fields.

    Validates: Requirements 1.1, 1.5, 1.6
    """
    service = InterviewJourneyService(db_session)
    candidate_id = uuid4()
    requisition_id = uuid4()
    created_by = uuid4()

    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=candidate_id,
        job_requisition_id=requisition_id,
        created_by=created_by,
    )

    assert journey.interview_journey_id is not None
    assert journey.organization_id == org_id
    assert journey.candidate_id == candidate_id
    assert journey.job_requisition_id == requisition_id
    assert journey.current_stage == JourneyStage.SOURCED.value
    assert journey.overall_status == JourneyOverallStatus.ACTIVE.value
    assert journey.current_stage_status is None


@pytest.mark.asyncio
async def test_create_journey_public_id_minimum_length(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test journey_public_id is at least 22 URL-safe characters.

    Validates: Requirement 1.1
    """
    service = InterviewJourneyService(db_session)
    candidate_id = uuid4()
    requisition_id = uuid4()

    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=candidate_id,
        job_requisition_id=requisition_id,
        created_by=uuid4(),
    )

    # URL-safe characters are alphanumeric + '-' + '_'
    assert len(journey.journey_public_id) >= 22
    assert all(c.isalnum() or c in '-_' for c in journey.journey_public_id)


@pytest.mark.asyncio
async def test_create_journey_public_id_uniqueness(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test that multiple journeys have unique public IDs.

    Validates: Requirement 1.1
    """
    service = InterviewJourneyService(db_session)
    public_ids = set()

    for _ in range(5):
        journey = await service.create_journey(
            org_id=org_id,
            candidate_id=uuid4(),
            job_requisition_id=uuid4(),
            created_by=uuid4(),
        )
        assert journey.journey_public_id not in public_ids
        public_ids.add(journey.journey_public_id)


@pytest.mark.asyncio
async def test_create_journey_creates_join_record(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test that CandidateInterviewJourney join record is created.

    Validates: Requirement 1.6
    """
    service = InterviewJourneyService(db_session)
    candidate_id = uuid4()
    requisition_id = uuid4()

    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=candidate_id,
        job_requisition_id=requisition_id,
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
    assert join_record.candidate_id == candidate_id
    assert join_record.interview_journey_id == journey.interview_journey_id
    assert not join_record.is_encrypted


@pytest.mark.asyncio
async def test_transition_stage_valid(db_session: AsyncSession, org_id: str, test_run_id: str):
    """Test valid stage transition.

    Validates: Requirements 1.2, 1.4
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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
async def test_transition_stage_invalid(db_session: AsyncSession, org_id: str, test_run_id: str):
    """Test invalid stage transition raises 400.

    Validates: Requirements 1.2, 1.8
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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
async def test_transition_stage_comments_too_long(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test comments exceeding 2000 chars raises 422.

    Validates: Requirement 1.4
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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
async def test_transition_to_terminal_stage_clears_substatus(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test terminal stages have no sub-status.

    Validates: Requirement 1.3
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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
async def test_transition_to_offer_extended_sets_timestamp(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test OFFER_EXTENDED sets offer_extended_at timestamp.

    Validates: Requirement 1.5
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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
async def test_transition_to_offer_accepted_sets_completed_and_encrypts(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test OFFER_ACCEPTED sets COMPLETED and encrypts join record.

    Validates: Requirements 1.5, 1.7
    """
    service = InterviewJourneyService(db_session)
    candidate_id = uuid4()
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=candidate_id,
        job_requisition_id=uuid4(),
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
async def test_get_journey_org_scoped(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test get_journey filters by organization.

    Validates: Requirement 1.1
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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
async def test_list_journeys_org_scoped(
    db_session: AsyncSession, org_id: str, test_run_id: str
):
    """Test list_journeys filters by organization.

    Validates: Requirement 1.1
    """
    service = InterviewJourneyService(db_session)
    candidate_id = uuid4()

    # Create 3 journeys
    for _ in range(3):
        await service.create_journey(
            org_id=org_id,
            candidate_id=candidate_id,
            job_requisition_id=uuid4(),
            created_by=uuid4(),
        )

    journeys, total = await service.list_journeys(org_id=org_id)
    assert len(journeys) >= 3
    assert total >= 3


@pytest.mark.asyncio
async def test_get_journey_history(db_session: AsyncSession, org_id: str, test_run_id: str):
    """Test getting journey stage history.

    Validates: Requirement 1.4
    """
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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


@given(
    from_stage=st.sampled_from(list(JourneyStage)),
    to_stage=st.sampled_from(list(JourneyStage)),
)
@pytest.mark.asyncio
async def test_property_stage_fsm_only_valid_transitions(
    db_session: AsyncSession,
    org_id: str,
    test_run_id: str,
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
    service = InterviewJourneyService(db_session)
    journey = await service.create_journey(
        org_id=org_id,
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
        created_by=uuid4(),
    )

    # Force journey to from_stage by directly updating (bypassing validation)
    journey.current_stage = from_stage.value

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
        # Journey should not have changed
        assert journey.current_stage == from_stage.value


@given(to_stage=st.sampled_from(list(JourneyStage)))
@pytest.mark.asyncio
async def test_property_terminal_stages_no_substatus(
    db_session: AsyncSession,
    org_id: str,
    test_run_id: str,
    to_stage,
):
    """Property 2: Terminal stages have no sub-status.

    Validates: Requirement 1.3

    For any stage transition:
    - Transition to terminal stage → current_stage_status is None
    - Transition to non-terminal stage → current_stage_status can be any valid value or None
    """
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
        candidate_id=uuid4(),
        job_requisition_id=uuid4(),
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
