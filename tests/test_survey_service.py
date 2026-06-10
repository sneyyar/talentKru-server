"""Candidate feedback survey service tests."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.surveys.models import (
    CandidateFeedbackSurvey,
    CandidateFeedbackSurveyAnswer,
    CandidateFeedbackSurveyQuestion,
    CandidateFeedbackSurveyResponse,
    CandidateFeedbackSurveyToken,
    SurveyStatus,
    SurveyCategory,
)
from app.modules.surveys.service import CandidateFeedbackSurveyService


@pytest.mark.asyncio
async def test_create_survey_for_journey_creates_token_with_min_length(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Survey token should have ≥43 URL-safe characters."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    assert survey is not None
    assert survey.status == SurveyStatus.SENT.value
    assert len(raw_token) >= 43


@pytest.mark.asyncio
async def test_create_survey_for_journey_sets_expires_at_to_30_days(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Survey should expire 30 days from creation."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    before_creation = datetime.now(timezone.utc)
    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)
    after_creation = datetime.now(timezone.utc)

    expected_expiry = before_creation + timedelta(days=30)
    # Allow 1 second tolerance
    assert (survey.expires_at - expected_expiry).total_seconds() < 1


@pytest.mark.asyncio
async def test_create_survey_for_journey_idempotent(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Creating survey twice for same journey should skip second creation."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    survey1, token1 = await service.create_survey_for_journey(journey_id, candidate_id, org_id)
    survey2, token2 = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    assert survey1.candidate_feedback_survey_id == survey2.candidate_feedback_survey_id


@pytest.mark.asyncio
async def test_get_survey_by_token_invalid_token_returns_401(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Invalid token should raise 401."""
    service = CandidateFeedbackSurveyService(db_session)

    with pytest.raises(Exception) as exc_info:
        await service.get_survey_by_token("invalid-token-xyz")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_survey_by_token_expired_survey_returns_410(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Expired survey should return 410."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    # Create survey
    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    # Mark survey as expired
    survey.status = SurveyStatus.EXPIRED.value
    await db_session.flush()

    # Try to get survey
    with pytest.raises(Exception) as exc_info:
        await service.get_survey_by_token(raw_token)

    assert exc_info.value.status_code == status.HTTP_410_GONE


@pytest.mark.asyncio
async def test_get_survey_by_token_completed_survey_returns_410(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Completed survey should return 410."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    # Create survey
    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    # Mark survey as completed
    survey.status = SurveyStatus.COMPLETED.value
    await db_session.flush()

    # Try to get survey
    with pytest.raises(Exception) as exc_info:
        await service.get_survey_by_token(raw_token)

    assert exc_info.value.status_code == status.HTTP_410_GONE


@pytest.mark.asyncio
async def test_submit_survey_validates_rating_range(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Ratings must be 0-10."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    # Create survey
    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    # Create a question
    q1 = CandidateFeedbackSurveyQuestion(
        candidate_feedback_survey_question_id=uuid4(),
        organization_id=org_id,
        display_order=1,
        question_text="Test question",
        category=SurveyCategory.APPLICATION.value,
        is_required=True,
    )
    db_session.add(q1)
    await db_session.flush()

    # Try to submit with invalid rating (> 10)
    with pytest.raises(Exception) as exc_info:
        await service.submit_survey(raw_token, {str(q1.candidate_feedback_survey_question_id): 11})

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_submit_survey_validates_comments_length(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Additional comments must not exceed 2000 chars."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    # Create survey
    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    # Create a question
    q1 = CandidateFeedbackSurveyQuestion(
        candidate_feedback_survey_question_id=uuid4(),
        organization_id=org_id,
        display_order=1,
        question_text="Test question",
        category=SurveyCategory.APPLICATION.value,
        is_required=True,
    )
    db_session.add(q1)
    await db_session.flush()

    # Try to submit with comments > 2000 chars
    long_comments = "x" * 2001
    with pytest.raises(Exception) as exc_info:
        await service.submit_survey(raw_token, {str(q1.candidate_feedback_survey_question_id): 5}, long_comments)

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_submit_survey_twice_raises_409(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Submitting twice should raise 409 conflict."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    # Create survey
    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    # Create a question
    q1 = CandidateFeedbackSurveyQuestion(
        candidate_feedback_survey_question_id=uuid4(),
        organization_id=org_id,
        display_order=1,
        question_text="Q1",
        category=SurveyCategory.APPLICATION.value,
        is_required=True,
    )
    db_session.add(q1)
    await db_session.flush()

    # First submission
    await service.submit_survey(raw_token, {str(q1.candidate_feedback_survey_question_id): 5})

    # Second submission should fail
    with pytest.raises(Exception) as exc_info:
        await service.submit_survey(raw_token, {str(q1.candidate_feedback_survey_question_id): 8})

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_expire_surveys_marks_old_surveys_as_expired(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Surveys past expiry should be marked as EXPIRED."""
    service = CandidateFeedbackSurveyService(db_session)
    
    # Create survey with past expiry
    now = datetime.now(timezone.utc)
    past_expiry = now - timedelta(days=1)

    survey = CandidateFeedbackSurvey(
        candidate_feedback_survey_id=uuid4(),
        organization_id=org_id,
        interview_journey_id=uuid4(),
        candidate_id=uuid4(),
        status=SurveyStatus.SENT.value,
        created_at=now - timedelta(days=31),
        expires_at=past_expiry,
    )
    db_session.add(survey)
    await db_session.flush()

    # Run expiry
    await service.expire_surveys()

    # Check survey is expired
    refreshed_survey = await db_session.get(CandidateFeedbackSurvey, survey.candidate_feedback_survey_id)
    assert refreshed_survey.status == SurveyStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_get_survey_questions_returns_ordered_by_display_order(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Survey questions should be ordered by display_order."""
    service = CandidateFeedbackSurveyService(db_session)

    # Create questions in random order
    q3 = CandidateFeedbackSurveyQuestion(
        candidate_feedback_survey_question_id=uuid4(),
        organization_id=org_id,
        display_order=3,
        question_text="Q3",
        category=SurveyCategory.OFFER_EXPERIENCE.value,
        is_required=True,
    )
    q1 = CandidateFeedbackSurveyQuestion(
        candidate_feedback_survey_question_id=uuid4(),
        organization_id=org_id,
        display_order=1,
        question_text="Q1",
        category=SurveyCategory.APPLICATION.value,
        is_required=True,
    )
    q2 = CandidateFeedbackSurveyQuestion(
        candidate_feedback_survey_question_id=uuid4(),
        organization_id=org_id,
        display_order=2,
        question_text="Q2",
        category=SurveyCategory.RECRUITER_EXPERIENCE.value,
        is_required=False,
    )
    db_session.add(q3)
    db_session.add(q1)
    db_session.add(q2)
    await db_session.flush()

    # Get questions
    questions = await service.get_survey_questions(org_id)

    assert len(questions) == 3
    assert questions[0].display_order == 1
    assert questions[1].display_order == 2
    assert questions[2].display_order == 3
