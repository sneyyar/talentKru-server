"""Tests for survey background scheduler."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.surveys.models import CandidateFeedbackSurvey, SurveyStatus
from app.modules.surveys.scheduler import _send_reminders, _expire_old_surveys


@pytest.mark.asyncio
async def test_send_reminders_selects_surveys_7_days_old_no_reminder(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Should send reminders for surveys 7+ days old without reminder sent."""
    from app.modules.surveys.models import CandidateFeedbackSurveyToken

    now = datetime.now(timezone.utc)
    eight_days_ago = now - timedelta(days=8)

    # Create survey 8 days old with no reminder sent
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.SENT.value,
        created_at=eight_days_ago,
        expires_at=now + timedelta(days=22),
        first_reminder_sent_at=None,
    )
    db_session.add(survey)
    await db_session.flush()

    # Create token
    token = CandidateFeedbackSurveyToken(
        candidate_feedback_survey_token_id=uuid4(),
        candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
        token_hash="test_hash",
        created_at=eight_days_ago,
        expires_at=now + timedelta(days=22),
        is_active=True,
    )
    db_session.add(token)
    await db_session.flush()

    # Run reminders
    with patch("app.modules.surveys.scheduler.publish_event", new_callable=AsyncMock):
        await _send_reminders(db_session)

    # Verify first_reminder_sent_at is set
    await db_session.refresh(survey)
    assert survey.first_reminder_sent_at is not None
    assert survey.first_reminder_sent_at.date() == now.date()


@pytest.mark.asyncio
async def test_send_reminders_skips_surveys_less_than_7_days_old(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Should skip surveys less than 7 days old."""
    from app.modules.surveys.models import CandidateFeedbackSurveyToken

    now = datetime.now(timezone.utc)
    five_days_ago = now - timedelta(days=5)

    # Create survey 5 days old with no reminder sent
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.SENT.value,
        created_at=five_days_ago,
        expires_at=now + timedelta(days=25),
        first_reminder_sent_at=None,
    )
    db_session.add(survey)
    await db_session.flush()

    # Create token
    token = CandidateFeedbackSurveyToken(
        candidate_feedback_survey_token_id=uuid4(),
        candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
        token_hash="test_hash",
        created_at=five_days_ago,
        expires_at=now + timedelta(days=25),
        is_active=True,
    )
    db_session.add(token)
    await db_session.flush()

    # Run reminders
    with patch("app.modules.surveys.scheduler.publish_event", new_callable=AsyncMock):
        await _send_reminders(db_session)

    # Verify first_reminder_sent_at is NOT set
    await db_session.refresh(survey)
    assert survey.first_reminder_sent_at is None


@pytest.mark.asyncio
async def test_send_reminders_skips_already_reminded(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Should skip surveys already reminded."""
    from app.modules.surveys.models import CandidateFeedbackSurveyToken

    now = datetime.now(timezone.utc)
    eight_days_ago = now - timedelta(days=8)
    two_days_ago = now - timedelta(days=2)

    # Create survey 8 days old with reminder already sent
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.SENT.value,
        created_at=eight_days_ago,
        expires_at=now + timedelta(days=22),
        first_reminder_sent_at=two_days_ago,
    )
    db_session.add(survey)
    await db_session.flush()

    original_reminder_time = survey.first_reminder_sent_at

    # Run reminders
    with patch("app.modules.surveys.scheduler.publish_event", new_callable=AsyncMock):
        await _send_reminders(db_session)

    # Verify first_reminder_sent_at is unchanged
    await db_session.refresh(survey)
    assert survey.first_reminder_sent_at == original_reminder_time


@pytest.mark.asyncio
async def test_expire_old_surveys_marks_30_day_old_as_expired(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Should expire surveys 30+ days old with status Sent."""
    from app.modules.surveys.models import CandidateFeedbackSurveyToken

    now = datetime.now(timezone.utc)
    thirty_one_days_ago = now - timedelta(days=31)

    # Create survey 31 days old with status SENT
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.SENT.value,
        created_at=thirty_one_days_ago,
        expires_at=now - timedelta(days=1),  # Expired based on expires_at
    )
    db_session.add(survey)
    await db_session.flush()

    # Create token
    token = CandidateFeedbackSurveyToken(
        candidate_feedback_survey_token_id=uuid4(),
        candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
        token_hash="test_hash",
        created_at=thirty_one_days_ago,
        expires_at=now - timedelta(days=1),
        is_active=True,
    )
    db_session.add(token)
    await db_session.flush()

    # Run expiry
    await _expire_old_surveys(db_session)

    # Verify survey is marked as EXPIRED
    await db_session.refresh(survey)
    assert survey.status == SurveyStatus.EXPIRED.value

    # Verify token is deactivated
    await db_session.refresh(token)
    assert token.is_active is False


@pytest.mark.asyncio
async def test_expire_old_surveys_skips_unexpired(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Should skip surveys that haven't reached expiry."""
    from app.modules.surveys.models import CandidateFeedbackSurveyToken

    now = datetime.now(timezone.utc)
    twenty_days_ago = now - timedelta(days=20)
    future = now + timedelta(days=10)

    # Create survey 20 days old but not yet expired (expires_at in future)
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.SENT.value,
        created_at=twenty_days_ago,
        expires_at=future,
    )
    db_session.add(survey)
    await db_session.flush()

    # Create token
    token = CandidateFeedbackSurveyToken(
        candidate_feedback_survey_token_id=uuid4(),
        candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
        token_hash="test_hash",
        created_at=twenty_days_ago,
        expires_at=future,
        is_active=True,
    )
    db_session.add(token)
    await db_session.flush()

    original_status = survey.status

    # Run expiry
    await _expire_old_surveys(db_session)

    # Verify survey status is unchanged
    await db_session.refresh(survey)
    assert survey.status == original_status

    # Verify token is still active
    await db_session.refresh(token)
    assert token.is_active is True


@pytest.mark.asyncio
async def test_expire_old_surveys_skips_non_sent_status(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Should only expire surveys with status SENT."""
    from app.modules.surveys.models import CandidateFeedbackSurveyToken

    now = datetime.now(timezone.utc)
    thirty_one_days_ago = now - timedelta(days=31)
    expired_time = now - timedelta(days=1)

    # Create survey 31 days old but with status COMPLETED
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.COMPLETED.value,
        created_at=thirty_one_days_ago,
        expires_at=expired_time,
    )
    db_session.add(survey)
    await db_session.flush()

    original_status = survey.status

    # Run expiry
    await _expire_old_surveys(db_session)

    # Verify survey status is unchanged
    await db_session.refresh(survey)
    assert survey.status == original_status


@pytest.mark.asyncio
async def test_expire_old_surveys_skips_deleted(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Should skip soft-deleted surveys."""
    from app.modules.surveys.models import CandidateFeedbackSurveyToken

    now = datetime.now(timezone.utc)
    thirty_one_days_ago = now - timedelta(days=31)
    expired_time = now - timedelta(days=1)

    # Create survey 31 days old but soft-deleted
    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.SENT.value,
        created_at=thirty_one_days_ago,
        expires_at=expired_time,
        deleted_at=now,
    )
    db_session.add(survey)
    await db_session.flush()

    original_status = survey.status

    # Run expiry
    await _expire_old_surveys(db_session)

    # Verify survey status is unchanged
    await db_session.refresh(survey)
    assert survey.status == original_status
