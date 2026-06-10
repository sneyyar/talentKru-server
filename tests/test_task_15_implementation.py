"""Task 15: Wire survey creation event to journey stage transitions.

Tests for:
- 15.1 Update InterviewJourneyService.transition_stage
- 15.2 Connect survey domain events to notification delivery
- 15.3 Implement survey reminder and expiry background scheduler

Requirements: 9.7, 9.9, 9.10, 9.11, 9.17, 9.18, 9.26
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain_events.models import DomainEvent
from app.modules.journeys.models import (
    InterviewJourney,
    JourneyStage,
    JourneyOverallStatus,
)
from app.modules.journeys.service import InterviewJourneyService
from app.modules.surveys.models import CandidateFeedbackSurvey, SurveyStatus
from app.modules.surveys.service import CandidateFeedbackSurveyService
from app.domain_events.handlers import (
    _handle_survey_created,
    _handle_survey_reminder,
)


@pytest.mark.asyncio
async def test_journey_transition_out_of_loop_creates_survey_event(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Subtask 15.1: Verify transition_stage publishes survey_created event when exiting LoopInterview.

    When transitioning from LoopInterview to PanelReview (or any post-LoopInterview stage),
    system should publish survey_created event with background task.

    Requirements: 9.7
    """
    from fastapi import BackgroundTasks

    # Create a journey with candidate and requisition
    journey_id = uuid4()
    candidate_id = uuid4()
    requisition_id = uuid4()

    journey = InterviewJourney(
        interview_journey_id=journey_id,
        organization_id=org_id,
        journey_public_id=f"public-{test_run_id}",
        candidate_id=candidate_id,
        job_requisition_id=requisition_id,
        current_stage=JourneyStage.LOOP_INTERVIEW.value,
        overall_status=JourneyOverallStatus.ACTIVE.value,
        start_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(journey)
    await db_session.flush()

    service = InterviewJourneyService(db_session)
    background_tasks = BackgroundTasks()

    # Mock the background task addition to verify it's called
    original_add_task = background_tasks.add_task

    task_added = False
    task_name = None

    def mock_add_task(func, *args, **kwargs):
        nonlocal task_added, task_name
        task_added = True
        task_name = func.__name__
        return original_add_task(func, *args, **kwargs)

    background_tasks.add_task = mock_add_task

    # Transition from LoopInterview to PanelReview
    updated_journey = await service.transition_stage(
        journey,
        JourneyStage.PANEL_REVIEW,
        uuid4(),  # changed_by
        background_tasks=background_tasks,
    )

    # Verify stage changed
    assert updated_journey.current_stage == JourneyStage.PANEL_REVIEW.value

    # Verify survey creation task was added (Requirement 9.7)
    assert task_added, "Background task should be added for survey creation"
    assert task_name == "_create_survey_on_loop_exit"


@pytest.mark.asyncio
async def test_journey_transition_to_offer_extended_creates_survey_event(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Verify transition to OfferExtended also triggers survey creation.

    All stages after LoopInterview should trigger survey creation: PanelReview,
    OfferPending, OfferExtended, OfferAccepted, OfferDeclined, Rejected, Withdrawn.

    Requirements: 9.7
    """
    from fastapi import BackgroundTasks

    journey_id = uuid4()
    candidate_id = uuid4()
    requisition_id = uuid4()

    journey = InterviewJourney(
        interview_journey_id=journey_id,
        organization_id=org_id,
        journey_public_id=f"public-{test_run_id}",
        candidate_id=candidate_id,
        job_requisition_id=requisition_id,
        current_stage=JourneyStage.LOOP_INTERVIEW.value,
        overall_status=JourneyOverallStatus.ACTIVE.value,
        start_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(journey)
    await db_session.flush()

    service = InterviewJourneyService(db_session)
    background_tasks = BackgroundTasks()

    task_names = []

    def mock_add_task(func, *args, **kwargs):
        task_names.append(func.__name__)
        return background_tasks.add_task.__wrapped__(func, *args, **kwargs)

    background_tasks.add_task = mock_add_task

    # Transition to OfferExtended
    updated_journey = await service.transition_stage(
        journey,
        JourneyStage.OFFER_EXTENDED,
        uuid4(),
        background_tasks=background_tasks,
    )

    # Should trigger survey task
    assert "_create_survey_on_loop_exit" in task_names


@pytest.mark.asyncio
async def test_survey_created_event_handler_calls_notification_service(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Subtask 15.2: Verify survey_created handler calls NotificationService with survey template.

    Requirements: 9.9, 9.17
    """
    # Create a candidate
    from app.modules.candidates.models import Candidate
    from app.crypto import encrypt_field

    candidate_id = uuid4()
    candidate_email = f"candidate-{test_run_id}@example.com"

    candidate = Candidate(
        candidate_id=candidate_id,
        organization_id=org_id,
        first_name="John",
        last_name="Doe",
        email_encrypted=encrypt_field(candidate_email),
        global_status="ACTIVE",
    )
    db_session.add(candidate)

    # Create a survey
    survey_id = uuid4()
    journey_id = uuid4()

    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=survey_id,
        organization_id=org_id,
        interview_journey_id=journey_id,
        candidate_id=candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add(survey)
    await db_session.flush()

    # Mock NotificationService.deliver
    with patch(
        "app.domain_events.handlers.NotificationService.deliver", new_callable=AsyncMock
    ) as mock_deliver:
        # Create event
        event = DomainEvent(
            event_id=uuid4(),
            event_type="survey_created",
            aggregate_id=str(survey_id),
            payload={
                "survey_id": str(survey_id),
                "candidate_id": str(candidate_id),
                "org_id": str(org_id),
            },
        )

        # Handle event
        await _handle_survey_created(event, correlation_id=None)

        # Verify NotificationService.deliver was called with use_survey_template=True
        mock_deliver.assert_called_once()
        call_kwargs = mock_deliver.call_args[1]
        assert call_kwargs.get("use_survey_template") is True
        assert call_kwargs.get("event_type") == "survey_invitation"


@pytest.mark.asyncio
async def test_survey_reminder_event_handler_calls_notification_service(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Subtask 15.2: Verify survey_reminder handler calls NotificationService with survey template.

    Requirements: 9.10, 9.18
    """
    from app.modules.candidates.models import Candidate
    from app.crypto import encrypt_field

    candidate_id = uuid4()
    candidate_email = f"candidate-{test_run_id}@example.com"

    candidate = Candidate(
        candidate_id=candidate_id,
        organization_id=org_id,
        first_name="Jane",
        last_name="Smith",
        email_encrypted=encrypt_field(candidate_email),
        global_status="ACTIVE",
    )
    db_session.add(candidate)

    # Create a survey
    survey_id = uuid4()
    journey_id = uuid4()

    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=survey_id,
        organization_id=org_id,
        interview_journey_id=journey_id,
        candidate_id=candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
        expires_at=datetime.now(timezone.utc) + timedelta(days=22),
    )
    db_session.add(survey)
    await db_session.flush()

    # Mock NotificationService.deliver
    with patch(
        "app.domain_events.handlers.NotificationService.deliver", new_callable=AsyncMock
    ) as mock_deliver:
        # Create event
        event = DomainEvent(
            event_id=uuid4(),
            event_type="survey_reminder",
            aggregate_id=str(survey_id),
            payload={
                "survey_id": str(survey_id),
                "candidate_id": str(candidate_id),
                "org_id": str(org_id),
            },
        )

        # Handle event
        await _handle_survey_reminder(event, correlation_id=None)

        # Verify NotificationService.deliver was called with use_survey_template=True
        mock_deliver.assert_called_once()
        call_kwargs = mock_deliver.call_args[1]
        assert call_kwargs.get("use_survey_template") is True
        assert call_kwargs.get("event_type") == "survey_reminder"


@pytest.mark.asyncio
async def test_survey_scheduler_send_reminders_for_7day_old_surveys(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Subtask 15.3: Verify scheduler sends reminders for surveys 7+ days old with no reminder sent.

    Requirements: 9.10, 9.26
    """
    from app.modules.surveys.scheduler import _send_reminders

    candidate_id = uuid4()

    # Create a survey created 7+ days ago, no reminder sent yet
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
        expires_at=datetime.now(timezone.utc) + timedelta(days=22),
        first_reminder_sent_at=None,  # No reminder sent yet
    )
    db_session.add(survey)
    await db_session.flush()

    # Mock publish_event to verify event is published
    with patch("app.modules.surveys.scheduler.publish_event", new_callable=AsyncMock) as mock_publish:
        await _send_reminders(db_session)

        # Verify event was published
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "survey_reminder"
        assert str(survey.candidate_feedback_survey_id) in str(call_args)

    # Verify first_reminder_sent_at was updated
    await db_session.refresh(survey)
    assert survey.first_reminder_sent_at is not None


@pytest.mark.asyncio
async def test_survey_scheduler_expires_30day_old_surveys(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Subtask 15.3: Verify scheduler expires surveys 30+ days old with status Sent.

    Requirements: 9.11, 9.26
    """
    from app.modules.surveys.scheduler import _expire_old_surveys

    candidate_id = uuid4()

    # Create a survey older than 30 days
    expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=31),
        expires_at=expires_at,
    )
    db_session.add(survey)
    await db_session.flush()

    survey_id = survey.candidate_feedback_survey_id

    # Run expiry scheduler
    await _expire_old_surveys(db_session)

    # Verify survey status is now EXPIRED
    result = await db_session.execute(
        select(CandidateFeedbackSurvey).where(
            CandidateFeedbackSurvey.candidate_feedback_survey_id == survey_id
        )
    )
    expired_survey = result.scalar_one_or_none()
    assert expired_survey is not None
    assert expired_survey.status == SurveyStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_survey_scheduler_skips_surveys_less_than_7_days(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Subtask 15.3: Verify scheduler skips surveys less than 7 days old.

    Requirements: 9.10, 9.26
    """
    from app.modules.surveys.scheduler import _send_reminders

    candidate_id = uuid4()

    # Create a survey created only 3 days ago
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
        expires_at=datetime.now(timezone.utc) + timedelta(days=27),
        first_reminder_sent_at=None,
    )
    db_session.add(survey)
    await db_session.flush()

    initial_reminder_sent_at = survey.first_reminder_sent_at

    # Run reminder scheduler
    await _send_reminders(db_session)

    # Verify first_reminder_sent_at was NOT updated
    await db_session.refresh(survey)
    assert survey.first_reminder_sent_at == initial_reminder_sent_at


@pytest.mark.asyncio
async def test_survey_scheduler_skips_already_reminded(
    db_session: AsyncSession,
    test_run_id: str,
    org_id,
):
    """
    Subtask 15.3: Verify scheduler skips surveys that already have a reminder sent.

    Requirements: 9.10, 9.26
    """
    from app.modules.surveys.scheduler import _send_reminders

    candidate_id = uuid4()
    reminder_sent_time = datetime.now(timezone.utc) - timedelta(hours=1)

    # Create a survey that already has a reminder sent
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
        expires_at=datetime.now(timezone.utc) + timedelta(days=22),
        first_reminder_sent_at=reminder_sent_time,  # Already sent
    )
    db_session.add(survey)
    await db_session.flush()

    # Mock publish_event
    with patch("app.modules.surveys.scheduler.publish_event", new_callable=AsyncMock) as mock_publish:
        await _send_reminders(db_session)

        # Verify event was NOT published (no additional reminders)
        mock_publish.assert_not_called()

    # Verify first_reminder_sent_at unchanged
    await db_session.refresh(survey)
    assert survey.first_reminder_sent_at == reminder_sent_time
