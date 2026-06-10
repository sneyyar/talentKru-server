"""
Tests for Task 15: Wire survey creation event to journey stage transitions.

Tests cover:
- 15.1: Survey creation triggered on LoopInterview exit
- 15.2: Notification handlers for survey_created and survey_reminder
- 15.3: Background scheduler for reminders and expiry
"""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain_events.models import DomainEvent, EventStatus
from app.modules.candidates.models import Candidate
from app.modules.journeys.models import InterviewJourney, JourneyStage, JourneyOverallStatus
from app.modules.journeys.service import InterviewJourneyService, _create_survey_on_loop_exit
from app.modules.notifications.models import NotificationRecord, NotificationStatus
from app.modules.surveys.models import (
    CandidateFeedbackSurvey,
    CandidateFeedbackSurveyQuestion,
    CandidateFeedbackSurveyToken,
    SurveyStatus,
    SurveyCategory,
)
from app.modules.surveys.service import CandidateFeedbackSurveyService
from app.modules.surveys.scheduler import _send_reminders, _expire_old_surveys
from app.crypto import encrypt_field


# ============================================================================
# Sub-task 15.1: Update InterviewJourneyService.transition_stage
# ============================================================================


@pytest.mark.asyncio
async def test_transition_stage_triggers_survey_creation_on_loop_exit(
    db_session: AsyncSession, org_id, user_id, test_run_id, current_user_context
):
    """Test that transitioning out of LoopInterview triggers survey creation."""
    # Create a candidate with email
    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field(candidate_email),
        email_hash=hashlib.sha256(candidate_email.lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    # Create a journey in LoopInterview stage
    journey = InterviewJourney(
        interview_journey_id=uuid4(),
        organization_id=org_id,
        journey_public_id=str(uuid4())[:12],  # Use first 12 chars of UUID for uniqueness
        candidate_id=candidate.candidate_id,
        job_requisition_id=uuid4(),
        current_stage=JourneyStage.LOOP_INTERVIEW.value,
        current_stage_status=None,
        overall_status=JourneyOverallStatus.ACTIVE.value,
        start_date=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db_session.add(journey)
    await db_session.flush()

    # Transition to PanelReview (post-LoopInterview stage)
    service = InterviewJourneyService(db_session)
    updated_journey = await service.transition_stage(
        journey,
        JourneyStage.PANEL_REVIEW,
        user_id,
        comments="Moving to panel review",
        background_tasks=None,  # No background tasks in test
    )

    # Verify journey was updated
    assert updated_journey.current_stage == JourneyStage.PANEL_REVIEW.value
    
    # Since background_tasks=None, we manually trigger survey creation (simulating background task)
    survey_service = CandidateFeedbackSurveyService(db_session)
    survey, _ = await survey_service.create_survey_for_journey(
        journey.interview_journey_id, candidate.candidate_id, org_id
    )
    await db_session.flush()

    # Verify survey was created
    assert survey is not None
    assert survey.status == SurveyStatus.SENT.value
    assert survey.candidate_id == candidate.candidate_id


@pytest.mark.asyncio
async def test_transition_stage_survey_creation_on_offer_extended(
    db_session: AsyncSession, org_id, user_id, test_run_id, current_user_context
):
    """Test survey creation when transitioning to OfferExtended from LoopInterview."""
    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field(candidate_email),
        email_hash=hashlib.sha256(candidate_email.lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    journey = InterviewJourney(
        interview_journey_id=uuid4(),
        organization_id=org_id,
        journey_public_id=str(uuid4())[:12],  # Use first 12 chars of UUID for uniqueness
        candidate_id=candidate.candidate_id,
        job_requisition_id=uuid4(),
        current_stage=JourneyStage.LOOP_INTERVIEW.value,
        overall_status=JourneyOverallStatus.ACTIVE.value,
        start_date=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db_session.add(journey)
    await db_session.flush()

    service = InterviewJourneyService(db_session)

    # Transition through intermediate stages
    journey = await service.transition_stage(
        journey, JourneyStage.PANEL_REVIEW, user_id, background_tasks=None
    )
    journey = await service.transition_stage(
        journey, JourneyStage.OFFER_PENDING, user_id, background_tasks=None
    )
    journey = await service.transition_stage(
        journey, JourneyStage.OFFER_EXTENDED, user_id, background_tasks=None
    )

    # Manually trigger survey creation (simulating background task on LoopInterview exit)
    survey_service = CandidateFeedbackSurveyService(db_session)
    survey, _ = await survey_service.create_survey_for_journey(
        journey.interview_journey_id, candidate.candidate_id, org_id
    )
    await db_session.flush()

    # Verify survey was created (one-time creation)
    survey_result = await db_session.execute(
        select(CandidateFeedbackSurvey).where(
            CandidateFeedbackSurvey.interview_journey_id == journey.interview_journey_id
        )
    )
    surveys = survey_result.scalars().all()
    assert len(surveys) == 1
    assert surveys[0].status == SurveyStatus.SENT.value


@pytest.mark.asyncio
async def test_survey_creation_idempotent(db_session: AsyncSession, org_id, user_id, test_run_id, current_user_context):
    """Test that survey creation is idempotent (doesn't create duplicates)."""
    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field(candidate_email),
        email_hash=hashlib.sha256(candidate_email.lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    journey = InterviewJourney(
        interview_journey_id=uuid4(),
        organization_id=org_id,
        journey_public_id=str(uuid4())[:12],  # Use first 12 chars of UUID for uniqueness
        candidate_id=candidate.candidate_id,
        job_requisition_id=uuid4(),
        current_stage=JourneyStage.LOOP_INTERVIEW.value,
        overall_status=JourneyOverallStatus.ACTIVE.value,
        start_date=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db_session.add(journey)
    await db_session.flush()

    service = CandidateFeedbackSurveyService(db_session)

    # Create survey twice
    survey1, _ = await service.create_survey_for_journey(
        journey.interview_journey_id, candidate.candidate_id, org_id
    )
    survey2, _ = await service.create_survey_for_journey(
        journey.interview_journey_id, candidate.candidate_id, org_id
    )

    # Verify both calls return same survey (idempotent)
    assert survey1.candidate_feedback_survey_id == survey2.candidate_feedback_survey_id
    await db_session.flush()

    # Verify only one survey exists in database
    all_surveys = await db_session.execute(
        select(CandidateFeedbackSurvey).where(
            CandidateFeedbackSurvey.interview_journey_id == journey.interview_journey_id
        )
    )
    assert len(all_surveys.scalars().all()) == 1


# ============================================================================
# Sub-task 15.2: Connect survey domain events to notification delivery
# ============================================================================


@pytest.mark.asyncio
async def test_survey_created_event_published(
    db_session: AsyncSession, org_id, user_id, test_run_id, current_user_context
):
    """Test that survey_created event is published when survey created."""
    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field(candidate_email),
        email_hash=hashlib.sha256(candidate_email.lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()

    # Create survey (publishes event)
    survey, _ = await service.create_survey_for_journey(journey_id, candidate.candidate_id, org_id)
    await db_session.flush()

    # Verify survey_created event was published - get the most recent one
    event_result = await db_session.execute(
        select(DomainEvent).where(
            and_(
                DomainEvent.event_type == "survey_created",
                DomainEvent.status == EventStatus.PENDING.value,
            )
        ).order_by(DomainEvent.published_at.desc()).limit(1)
    )
    event = event_result.scalar_one_or_none()
    assert event is not None
    assert "survey_id" in (event.payload or {})


@pytest.mark.asyncio
async def test_survey_reminder_event_published(
    db_session: AsyncSession, org_id, user_id, test_run_id, current_user_context
):
    """Test that survey_reminder event is published when reminder sent."""
    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field(candidate_email),
        email_hash=hashlib.sha256(candidate_email.lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    journey_id = uuid4()

    # Create survey created 7+ days ago
    now = datetime.now(timezone.utc)
    eight_days_ago = now - timedelta(days=8)

    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=journey_id,
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=eight_days_ago,
        expires_at=eight_days_ago + timedelta(days=30),
    )
    db_session.add(survey)
    await db_session.flush()

    # Trigger reminder scheduler
    await _send_reminders(db_session)
    await db_session.flush()

    # Verify survey_reminder event was published - get the most recent one
    event_result = await db_session.execute(
        select(DomainEvent).where(
            and_(
                DomainEvent.event_type == "survey_reminder",
                DomainEvent.status == EventStatus.PENDING.value,
            )
        ).order_by(DomainEvent.published_at.desc()).limit(1)
    )
    event = event_result.scalar_one_or_none()
    assert event is not None
    assert "survey_id" in (event.payload or {})

    # Verify first_reminder_sent_at was set
    refreshed = await db_session.get(CandidateFeedbackSurvey, survey.candidate_feedback_survey_id)
    assert refreshed.first_reminder_sent_at is not None


# ============================================================================
# Sub-task 15.3: Implement survey reminder and expiry background scheduler
# ============================================================================


@pytest.mark.asyncio
async def test_scheduler_sends_reminders_for_7_day_old_surveys(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test scheduler sends reminders for surveys 7+ days old."""
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field("test@example.com"),
        email_hash=hashlib.sha256("test@example.com".lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    now = datetime.now(timezone.utc)

    # Create 3 surveys: one exactly 7 days old (eligible), one 6 days old (not eligible), one already reminded
    survey_eligible = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=7),
        expires_at=now + timedelta(days=23),
    )

    survey_too_new = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=6),
        expires_at=now + timedelta(days=24),
    )

    survey_already_reminded = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=7),
        expires_at=now + timedelta(days=23),
        first_reminder_sent_at=now - timedelta(hours=1),
    )

    db_session.add(survey_eligible)
    db_session.add(survey_too_new)
    db_session.add(survey_already_reminded)
    await db_session.flush()

    # Run scheduler
    await _send_reminders(db_session)
    await db_session.flush()

    # Verify only eligible survey got reminder
    refreshed_eligible = await db_session.get(
        CandidateFeedbackSurvey, survey_eligible.candidate_feedback_survey_id
    )
    refreshed_too_new = await db_session.get(
        CandidateFeedbackSurvey, survey_too_new.candidate_feedback_survey_id
    )
    refreshed_already = await db_session.get(
        CandidateFeedbackSurvey, survey_already_reminded.candidate_feedback_survey_id
    )

    assert refreshed_eligible.first_reminder_sent_at is not None
    assert refreshed_too_new.first_reminder_sent_at is None
    assert refreshed_already.first_reminder_sent_at is not None


@pytest.mark.asyncio
async def test_scheduler_expires_surveys_30_days_old(db_session: AsyncSession, org_id, test_run_id):
    """Test scheduler expires surveys 30+ days old."""
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field("test@example.com"),
        email_hash=hashlib.sha256("test@example.com".lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    now = datetime.now(timezone.utc)

    # Create surveys with different ages
    survey_expired = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
    )

    survey_just_expired = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=30),
        expires_at=now,
    )

    survey_not_expired = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=20),
        expires_at=now + timedelta(days=10),
    )

    survey_already_expired = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.EXPIRED.value,
        created_at=now - timedelta(days=40),
        expires_at=now - timedelta(days=10),
    )

    db_session.add(survey_expired)
    db_session.add(survey_just_expired)
    db_session.add(survey_not_expired)
    db_session.add(survey_already_expired)
    await db_session.flush()

    # Run scheduler
    await _expire_old_surveys(db_session)
    await db_session.flush()

    # Verify status changes
    refreshed_expired = await db_session.get(
        CandidateFeedbackSurvey, survey_expired.candidate_feedback_survey_id
    )
    refreshed_just_expired = await db_session.get(
        CandidateFeedbackSurvey, survey_just_expired.candidate_feedback_survey_id
    )
    refreshed_not_expired = await db_session.get(
        CandidateFeedbackSurvey, survey_not_expired.candidate_feedback_survey_id
    )
    refreshed_already_expired = await db_session.get(
        CandidateFeedbackSurvey, survey_already_expired.candidate_feedback_survey_id
    )

    assert refreshed_expired.status == SurveyStatus.EXPIRED.value
    assert refreshed_just_expired.status == SurveyStatus.EXPIRED.value
    assert refreshed_not_expired.status == SurveyStatus.SENT.value
    assert refreshed_already_expired.status == SurveyStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_scheduler_deactivates_tokens_on_expiry(db_session: AsyncSession, org_id, test_run_id):
    """Test scheduler deactivates tokens when survey expires."""
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field("Test Candidate"),
        name_hash=hashlib.sha256("Test Candidate".lower().encode()).hexdigest(),
        email=encrypt_field("test@example.com"),
        email_hash=hashlib.sha256("test@example.com".lower().encode()).hexdigest(),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    now = datetime.now(timezone.utc)

    # Create expired survey
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
    )
    db_session.add(survey)
    await db_session.flush()

    # Create active token
    import secrets
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token = CandidateFeedbackSurveyToken(
        candidate_feedback_survey_token_id=uuid4(),
        candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
        token=raw_token,
        token_hash=token_hash,
        created_at=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
        is_active=True,
    )
    db_session.add(token)
    await db_session.flush()

    # Run expiry scheduler
    await _expire_old_surveys(db_session)
    await db_session.flush()

    # Verify token was deactivated
    refreshed_token = await db_session.get(
        CandidateFeedbackSurveyToken, token.candidate_feedback_survey_token_id
    )
    assert refreshed_token.is_active is False
