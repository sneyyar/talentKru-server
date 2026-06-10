"""Basic survey service tests to validate database operations."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.surveys.models import (
    CandidateFeedbackSurvey,
    CandidateFeedbackSurveyQuestion,
    CandidateFeedbackSurveyToken,
    SurveyStatus,
    SurveyCategory,
)
from app.modules.surveys.service import CandidateFeedbackSurveyService


@pytest.mark.asyncio
async def test_create_survey_basic(db_session: AsyncSession, org_id):
    """Basic survey creation test."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    # Verify survey created
    assert survey is not None
    assert survey.status == SurveyStatus.SENT.value
    assert survey.organization_id == org_id
    assert survey.interview_journey_id == journey_id
    assert survey.candidate_id == candidate_id

    # Verify token generated
    assert len(raw_token) >= 43

    # Verify token saved to database
    token_result = await db_session.execute(
        select(CandidateFeedbackSurveyToken).where(
            CandidateFeedbackSurveyToken.candidate_feedback_survey_id == survey.candidate_feedback_survey_id
        )
    )
    token_record = token_result.scalar_one()
    assert token_record is not None
    assert token_record.is_active is True


@pytest.mark.asyncio
async def test_submit_survey_basic(db_session: AsyncSession, org_id):
    """Basic survey submission test."""
    service = CandidateFeedbackSurveyService(db_session)
    journey_id = uuid4()
    candidate_id = uuid4()

    # Create survey
    survey, raw_token = await service.create_survey_for_journey(journey_id, candidate_id, org_id)

    # Create questions
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

    # Submit survey
    response = await service.submit_survey(
        raw_token,
        {str(q1.candidate_feedback_survey_question_id): 7},
        additional_comments="Great!",
    )

    # Verify response created
    assert response is not None
    assert response.additional_comments == "Great!"

    # Verify survey marked as completed
    refreshed = await db_session.get(CandidateFeedbackSurvey, survey.candidate_feedback_survey_id)
    assert refreshed.status == SurveyStatus.COMPLETED.value
    assert refreshed.completed_at is not None


@pytest.mark.asyncio
async def test_get_survey_questions_basic(db_session: AsyncSession, org_id):
    """Basic get survey questions test."""
    service = CandidateFeedbackSurveyService(db_session)

    # Create questions
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
    db_session.add(q1)
    db_session.add(q2)
    await db_session.flush()

    # Get questions
    questions = await service.get_survey_questions(org_id)

    # Verify
    assert len(questions) == 2
    assert questions[0].display_order == 1
    assert questions[1].display_order == 2
