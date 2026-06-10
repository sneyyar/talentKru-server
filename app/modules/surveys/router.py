"""Candidate feedback survey router."""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.modules.surveys.schemas import (
    SurveyFormResponse,
    SurveyQuestionResponse,
    SurveySubmitRequest,
    SurveySubmitResponse,
)
from app.modules.surveys.service import CandidateFeedbackSurveyService
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/surveys", tags=["surveys"])


@router.get(
    "/{token}",
    response_model=SurveyFormResponse,
    status_code=status.HTTP_200_OK,
    summary="Get survey form and questions",
    description=(
        "Retrieve a candidate feedback survey and its questions by token. "
        "No authentication required beyond token validation. "
        "Returns 410 if survey is expired or already completed."
    ),
)
async def get_survey(
    token: str,
    db: AsyncSession = Depends(get_db_session),
) -> SurveyFormResponse:
    """
    Get survey form and questions by token.

    Unauthenticated endpoint; returns 200 with survey form and questions
    or 410 if invalid/expired/completed.

    Requirements: 9.12, 9.13
    """
    service = CandidateFeedbackSurveyService(db)

    try:
        survey, questions = await service.get_survey_by_token(token)
    except HTTPException:
        raise

    # Build response
    question_responses = [
        SurveyQuestionResponse(
            candidate_feedback_survey_question_id=q.candidate_feedback_survey_question_id,
            question_text=q.question_text,
            category=q.category,
            is_required=q.is_required,
            display_order=q.display_order,
        )
        for q in questions
    ]

    return SurveyFormResponse(
        candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
        questions=question_responses,
    )


@router.post(
    "/{token}/submit",
    response_model=SurveySubmitResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit survey responses",
    description=(
        "Submit completed survey responses by token. "
        "Unauthenticated endpoint; validates token and responses. "
        "Returns 409 if survey already completed, 410 if expired."
    ),
)
async def submit_survey(
    token: str,
    request: SurveySubmitRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SurveySubmitResponse:
    """
    Submit survey responses.

    Unauthenticated endpoint; accepts {answers: {question_id: rating, ...}, additional_comments: string}.
    Returns 200 on success, 409 if already completed, 410 if expired.

    Requirements: 9.14, 9.15
    """
    service = CandidateFeedbackSurveyService(db)

    try:
        await service.submit_survey(token, request.answers, request.additional_comments)
    except HTTPException:
        raise

    logger.info(
        "survey_submission_successful",
        n_answers=len(request.answers),
    )

    return SurveySubmitResponse(
        success=True,
        message="Thank you for completing the survey.",
    )



