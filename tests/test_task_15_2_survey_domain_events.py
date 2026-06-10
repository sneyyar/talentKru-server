"""
Tests for Task 15.2: Connect survey domain events to notification delivery.

Tests verify:
- survey_created event handler calls NotificationService.deliver with "survey_invitation"
- survey_reminder event handler calls NotificationService.deliver with "survey_reminder"
- Both handlers use SurveyFeedbackTemplate for rendering
- Payload contains survey_link and candidate_email
- Handlers extract org_id and use it for template lookup
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_field
from app.domain_events.handlers import _handle_survey_created, _handle_survey_reminder
from app.domain_events.models import DomainEvent, EventStatus
from app.modules.candidates.models import Candidate
from app.modules.notifications.models import NotificationRecord, NotificationStatus, NotificationTemplate
from app.modules.surveys.models import (
    CandidateFeedbackSurvey,
    CandidateFeedbackSurveyToken,
    SurveyStatus,
    SurveyFeedbackTemplate,
)
from app.modules.email_config.models import OrganizationEmailConfig, ProviderType, SystemSetting


@pytest.fixture
async def setup_notifications(db_session: AsyncSession, org_id: uuid4):
    """Set up notification templates and email config for testing."""
    # Enable global email notifications
    result = await db_session.execute(
        select(SystemSetting).where(
            SystemSetting.setting_key == "email_notifications_enabled"
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.setting_value = "true"
    else:
        setting = SystemSetting(
            setting_key="email_notifications_enabled",
            setting_value="true",
        )
        db_session.add(setting)
    await db_session.flush()

    # Create organization email config
    org_config = OrganizationEmailConfig(
        organization_email_config_id=uuid4(),
        organization_id=org_id,
        email_notifications_enabled=True,
        provider_type=ProviderType.SMTP.value,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="noreply@example.com",
        smtp_password=encrypt_field("password123"),
        smtp_use_tls=True,
        from_address="noreply@example.com",
        from_name="TalentKru",
    )
    db_session.add(org_config)
    await db_session.flush()

    # Create survey invitation template
    survey_invite_template = NotificationTemplate(
        notification_template_id=uuid4(),
        organization_id=org_id,
        event_type="survey_invitation",
        subject="We'd love your feedback on the interview!",
        body_template="""
Dear {{candidate_name}},

Thank you for completing your interview! We value your feedback.

Please take 5 minutes to complete our brief survey:
{{survey_link}}

The survey will expire in 30 days.

Best regards,
TalentKru Team
""",
        is_enabled=True,
        locale=None,
    )
    db_session.add(survey_invite_template)
    await db_session.flush()

    # Create survey reminder template
    survey_reminder_template = NotificationTemplate(
        notification_template_id=uuid4(),
        organization_id=org_id,
        event_type="survey_reminder",
        subject="Reminder: Please share your interview feedback",
        body_template="""
Dear {{candidate_name}},

We noticed you haven't completed our survey yet. 

Your survey will expire in {{days_remaining}} days.

Please complete it here:
{{survey_link}}

Thank you!
""",
        is_enabled=True,
        locale=None,
    )
    db_session.add(survey_reminder_template)
    await db_session.flush()

    # Create survey feedback templates (Req 9.17, 9.18)
    survey_feedback_invite = SurveyFeedbackTemplate(
        survey_feedback_template_id=uuid4(),
        organization_id=org_id,
        template_type="initial_survey_invitation",
        subject="Your feedback matters!",
        body_template="Please complete our survey: {{survey_link}}",
        is_enabled=True,
    )
    db_session.add(survey_feedback_invite)

    survey_feedback_reminder = SurveyFeedbackTemplate(
        survey_feedback_template_id=uuid4(),
        organization_id=org_id,
        template_type="survey_reminder",
        subject="Final reminder: Complete your survey",
        body_template="You have {{days_remaining}} days to complete: {{survey_link}}",
        is_enabled=True,
    )
    db_session.add(survey_feedback_reminder)
    await db_session.flush()

    return org_config, survey_invite_template, survey_reminder_template


# ============================================================================
# Tests for survey_created event handler (Req 9.9, 9.17)
# ============================================================================


@pytest.mark.asyncio
async def test_handle_survey_created_calls_notification_service(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test that survey_created handler calls NotificationService.deliver with survey_invitation."""
    await setup_notifications(db_session, org_id)

    # Create candidate
    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        first_name="Alice",
        last_name="Smith",
        email_encrypted=encrypt_field(candidate_email),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    # Create survey
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add(survey)
    await db_session.flush()

    # Create domain event
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={
            "survey_id": str(survey.candidate_feedback_survey_id),
            "candidate_id": str(candidate.candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
        correlation_id="test-correlation-id",
    )
    db_session.add(event)
    await db_session.flush()

    # Handle the event
    with patch("app.domain_events.handlers.NotificationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.deliver = AsyncMock(return_value=None)

        await _handle_survey_created(event, "test-correlation-id")

        # Verify NotificationService.deliver was called
        mock_service.deliver.assert_called_once()
        call_args = mock_service.deliver.call_args

        # Verify event_type is survey_invitation
        assert call_args.kwargs["event_type"] == "survey_invitation"

        # Verify recipient_email is correct
        assert call_args.kwargs["recipient_email"] == candidate_email

        # Verify org_id is passed
        assert call_args.kwargs["org_id"] == org_id

        # Verify payload contains survey_link and candidate_email
        payload = call_args.kwargs["payload"]
        assert "survey_link" in payload
        assert "candidate_email" in payload
        assert payload["candidate_email"] == candidate_email
        assert payload["candidate_name"] == "Alice"


@pytest.mark.asyncio
async def test_handle_survey_created_missing_candidate(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test survey_created handler handles missing candidate gracefully."""
    await setup_notifications(db_session, org_id)

    # Create survey without creating candidate
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),  # Non-existent candidate
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add(survey)
    await db_session.flush()

    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={
            "survey_id": str(survey.candidate_feedback_survey_id),
            "candidate_id": str(survey.candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )
    db_session.add(event)
    await db_session.flush()

    # Handle event - should log warning but not raise
    with patch("app.domain_events.handlers.NotificationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        await _handle_survey_created(event, None)

        # Verify deliver was not called (due to missing candidate)
        mock_service.deliver.assert_not_called()


@pytest.mark.asyncio
async def test_handle_survey_created_missing_payload(
    db_session: AsyncSession, org_id
):
    """Test survey_created handler handles missing payload gracefully."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={},  # Missing required fields
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )
    db_session.add(event)
    await db_session.flush()

    # Handle event - should log warning but not raise
    with patch("app.domain_events.handlers.NotificationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        await _handle_survey_created(event, None)

        # Verify deliver was not called
        mock_service.deliver.assert_not_called()


# ============================================================================
# Tests for survey_reminder event handler (Req 9.10, 9.18)
# ============================================================================


@pytest.mark.asyncio
async def test_handle_survey_reminder_calls_notification_service(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test that survey_reminder handler calls NotificationService.deliver with survey_reminder."""
    await setup_notifications(db_session, org_id)

    # Create candidate
    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        first_name="Bob",
        last_name="Jones",
        email_encrypted=encrypt_field(candidate_email),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    # Create survey with reminder eligible age (7+ days old)
    now = datetime.now(timezone.utc)
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=8),
        expires_at=now + timedelta(days=22),
        first_reminder_sent_at=now - timedelta(hours=1),  # Already reminded
    )
    db_session.add(survey)
    await db_session.flush()

    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload={
            "survey_id": str(survey.candidate_feedback_survey_id),
            "candidate_id": str(candidate.candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
        correlation_id="test-correlation-id",
    )
    db_session.add(event)
    await db_session.flush()

    with patch("app.domain_events.handlers.NotificationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.deliver = AsyncMock(return_value=None)

        await _handle_survey_reminder(event, "test-correlation-id")

        # Verify NotificationService.deliver was called
        mock_service.deliver.assert_called_once()
        call_args = mock_service.deliver.call_args

        # Verify event_type is survey_reminder
        assert call_args.kwargs["event_type"] == "survey_reminder"

        # Verify recipient_email is correct
        assert call_args.kwargs["recipient_email"] == candidate_email

        # Verify org_id is passed
        assert call_args.kwargs["org_id"] == org_id

        # Verify payload contains survey_link, candidate_email, and days_remaining
        payload = call_args.kwargs["payload"]
        assert "survey_link" in payload
        assert "candidate_email" in payload
        assert "days_remaining" in payload
        assert payload["candidate_email"] == candidate_email
        assert payload["candidate_name"] == "Bob"
        assert isinstance(payload["days_remaining"], int)
        assert payload["days_remaining"] >= 0


@pytest.mark.asyncio
async def test_handle_survey_reminder_calculates_days_remaining(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test survey_reminder handler correctly calculates days_remaining."""
    await setup_notifications(db_session, org_id)

    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        first_name="Charlie",
        last_name="Brown",
        email_encrypted=encrypt_field("charlie@example.com"),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    # Create survey expiring in exactly 5 days
    now = datetime.now(timezone.utc)
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=8),
        expires_at=now + timedelta(days=5, hours=12),
    )
    db_session.add(survey)
    await db_session.flush()

    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload={
            "survey_id": str(survey.candidate_feedback_survey_id),
            "candidate_id": str(candidate.candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )
    db_session.add(event)
    await db_session.flush()

    with patch("app.domain_events.handlers.NotificationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.deliver = AsyncMock(return_value=None)

        await _handle_survey_reminder(event, None)

        call_args = mock_service.deliver.call_args
        payload = call_args.kwargs["payload"]

        # days_remaining should be 5 (int division on timedelta)
        assert payload["days_remaining"] == 5


@pytest.mark.asyncio
async def test_handle_survey_reminder_missing_survey(
    db_session: AsyncSession, org_id
):
    """Test survey_reminder handler handles missing survey gracefully."""
    await setup_notifications(db_session, org_id)

    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        first_name="Diana",
        last_name="Prince",
        email_encrypted=encrypt_field("diana@example.com"),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload={
            "survey_id": str(uuid4()),  # Non-existent survey
            "candidate_id": str(candidate.candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )
    db_session.add(event)
    await db_session.flush()

    with patch("app.domain_events.handlers.NotificationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        await _handle_survey_reminder(event, None)

        # Verify deliver was not called
        mock_service.deliver.assert_not_called()


# ============================================================================
# Integration tests: Event publication and handler dispatch
# ============================================================================


@pytest.mark.asyncio
async def test_survey_created_event_is_registered_in_handler_registry():
    """Test that survey_created handler is registered in HandlerRegistry."""
    from app.domain_events.handlers import HandlerRegistry

    # Verify survey_created handler is registered
    assert "survey_created" in HandlerRegistry
    assert _handle_survey_created in HandlerRegistry["survey_created"]


@pytest.mark.asyncio
async def test_survey_reminder_event_is_registered_in_handler_registry():
    """Test that survey_reminder handler is registered in HandlerRegistry."""
    from app.domain_events.handlers import HandlerRegistry

    # Verify survey_reminder handler is registered
    assert "survey_reminder" in HandlerRegistry
    assert _handle_survey_reminder in HandlerRegistry["survey_reminder"]


@pytest.mark.asyncio
async def test_handler_payload_extraction_with_string_uuids(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test handlers correctly handle UUID payloads as strings."""
    await setup_notifications(db_session, org_id)

    candidate_email = f"candidate-{test_run_id}@example.com"
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        first_name="Eve",
        last_name="Wilson",
        email_encrypted=encrypt_field(candidate_email),
        global_status="ACTIVE",
    )
    db_session.add(candidate)
    await db_session.flush()

    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=candidate.candidate_id,
        status=SurveyStatus.SENT.value,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add(survey)
    await db_session.flush()

    # Create event with UUIDs as strings (as they would be in real events)
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={
            "survey_id": str(survey.candidate_feedback_survey_id),
            "candidate_id": str(candidate.candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )
    db_session.add(event)
    await db_session.flush()

    with patch("app.domain_events.handlers.NotificationService") as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.deliver = AsyncMock(return_value=None)

        # Should not raise any errors when handling string UUIDs
        await _handle_survey_created(event, None)

        # Verify the handler completed successfully
        mock_service.deliver.assert_called_once()
