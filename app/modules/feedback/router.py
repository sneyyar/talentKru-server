"""
Interview feedback router for collecting interviewer feedback on candidate performance.

Endpoints:
- POST /api/v1/feedback — Create manual feedback
- GET /api/v1/feedback/{feedback_id} — Get feedback with authorization
- PATCH /api/v1/feedback/{feedback_id} — Update feedback (draft only)
- PATCH /api/v1/feedback/{feedback_id}/submit — Submit feedback (finalize)
- POST /api/v1/feedback/transcript — Submit transcript for AI-generated feedback

Requirements: 3.1, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.feedback.models import InterviewFeedback
from app.modules.feedback.schemas import (
    FeedbackCreate,
    FeedbackUpdate,
    FeedbackResponse,
    TranscriptRequest,
)
from app.modules.feedback.service import InterviewFeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_interview_feedback",
    summary="Create interview feedback",
    description="Create manual interview feedback for a completed slot. "
    "Requires the requesting user to be the assigned interviewer on the slot. "
    "Feedback is created in DRAFT status and can be edited before submission. "
    "Requires Interviewer, Recruiter, or Administrator role. Returns 201 with feedback details.",
    responses={
        201: {"description": "Feedback created successfully", "model": FeedbackResponse},
        403: {"description": "Forbidden: User is not the assigned interviewer or insufficient role"},
        404: {"description": "Not found: Interview slot not found in organization"},
        422: {"description": "Validation error: Invalid competency ratings, narrative too long, or invalid recommendation"},
    },
)
async def create_interview_feedback(
    request: FeedbackCreate,
    principal: Principal = Depends(require_role("Interviewer", "Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    """
    Create manual interview feedback.

    Requirements: 3.1, 3.3, 3.6

    Args:
        request: Feedback creation request with competency ratings, narrative, and recommendation
        principal: Authenticated principal with organization context and user ID
        db: Database session

    Returns:
        FeedbackResponse with created feedback details

    Raises:
        HTTPException: 403 if not assigned interviewer, 404 if slot not found, 422 on validation failure
    """
    service = InterviewFeedbackService(db)

    try:
        feedback = await service.create_feedback(
            org_id=principal.organization_id,
            slot_id=request.slot_id,
            competency_ratings=request.competency_ratings,
            narrative=request.narrative,
            hiring_recommendation=request.hiring_recommendation,
            requesting_user_id=principal.user_id,
        )

        return FeedbackResponse.from_orm(feedback)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create interview feedback",
        ) from e


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_interview_feedback",
    summary="Get interview feedback",
    description="Retrieve interview feedback by ID with authorization checks. "
    "Authorized users: assigned interviewer, hiring manager for the requisition, or administrator. "
    "Returns 403 if user is not authorized. Returns 404 if feedback not found.",
    responses={
        200: {"description": "Feedback retrieved successfully", "model": FeedbackResponse},
        403: {"description": "Forbidden: User does not have permission to view this feedback"},
        404: {"description": "Not found: Feedback not found in organization"},
    },
)
async def get_interview_feedback(
    feedback_id: UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    """
    Get interview feedback with authorization.

    Requirements: 3.7

    Args:
        feedback_id: Feedback ID to retrieve
        principal: Authenticated principal with organization context and user ID
        db: Database session

    Returns:
        FeedbackResponse with feedback details if authorized

    Raises:
        HTTPException: 403 if not authorized, 404 if not found
    """
    service = InterviewFeedbackService(db)

    try:
        is_admin = "Administrator" in principal.roles or "SuperAdministrator" in principal.roles
        feedback = await service.get_feedback(
            org_id=principal.organization_id,
            feedback_id=feedback_id,
            requesting_user_id=principal.user_id,
            is_admin=is_admin,
        )

        return FeedbackResponse.from_orm(feedback)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interview feedback",
        ) from e


@router.patch(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_interview_feedback",
    summary="Update interview feedback",
    description="Update feedback in DRAFT status. "
    "Only the assigned interviewer can edit feedback. "
    "Once feedback is SUBMITTED, it cannot be modified (returns 409). "
    "Partial updates are supported (only provide fields to update). "
    "Requires Interviewer, Recruiter, or Administrator role. Returns 200 with updated feedback.",
    responses={
        200: {"description": "Feedback updated successfully", "model": FeedbackResponse},
        403: {"description": "Forbidden: User is not the assigned interviewer or insufficient role"},
        404: {"description": "Not found: Feedback not found in organization"},
        409: {"description": "Conflict: Feedback has been submitted and cannot be modified"},
        422: {"description": "Validation error: Invalid competency ratings, narrative too long, or invalid recommendation"},
    },
)
async def update_interview_feedback(
    feedback_id: UUID,
    request: FeedbackUpdate,
    principal: Principal = Depends(require_role("Interviewer", "Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    """
    Update interview feedback in DRAFT status.

    Requirements: 3.6, 3.8

    Args:
        feedback_id: Feedback ID to update
        request: Partial update request (only non-None fields are updated)
        principal: Authenticated principal with organization context and user ID
        db: Database session

    Returns:
        FeedbackResponse with updated feedback details

    Raises:
        HTTPException: 403 if not assigned interviewer, 404 if not found, 409 if submitted, 422 on validation failure
    """
    service = InterviewFeedbackService(db)

    try:
        feedback = await service.update_feedback(
            org_id=principal.organization_id,
            feedback_id=feedback_id,
            competency_ratings=request.competency_ratings,
            narrative=request.narrative,
            hiring_recommendation=request.hiring_recommendation,
            requesting_user_id=principal.user_id,
        )

        return FeedbackResponse.from_orm(feedback)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update interview feedback",
        ) from e


@router.patch(
    "/{feedback_id}/submit",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    operation_id="submit_interview_feedback",
    summary="Submit interview feedback",
    description="Submit feedback, changing status from DRAFT to SUBMITTED. "
    "Once submitted, feedback cannot be edited (further edits return 409). "
    "Only the assigned interviewer can submit. Requires Interviewer, Recruiter, or Administrator role. "
    "Returns 200 with finalized feedback.",
    responses={
        200: {"description": "Feedback submitted successfully", "model": FeedbackResponse},
        403: {"description": "Forbidden: User is not the assigned interviewer or insufficient role"},
        404: {"description": "Not found: Feedback not found in organization"},
        409: {"description": "Conflict: Feedback has already been submitted"},
    },
)
async def submit_interview_feedback(
    feedback_id: UUID,
    principal: Principal = Depends(require_role("Interviewer", "Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    """
    Submit interview feedback.

    Requirements: 3.9

    Args:
        feedback_id: Feedback ID to submit
        principal: Authenticated principal with organization context and user ID
        db: Database session

    Returns:
        FeedbackResponse with submitted feedback (status=SUBMITTED)

    Raises:
        HTTPException: 403 if not assigned interviewer, 404 if not found, 409 if already submitted
    """
    service = InterviewFeedbackService(db)

    try:
        feedback = await service.submit_feedback(
            org_id=principal.organization_id,
            feedback_id=feedback_id,
            requesting_user_id=principal.user_id,
        )

        return FeedbackResponse.from_orm(feedback)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit interview feedback",
        ) from e


@router.post(
    "/transcript",
    response_model=FeedbackResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="submit_interview_transcript",
    summary="Submit interview transcript for AI analysis",
    description="Submit an interview transcript to generate AI-assisted behavioral feedback. "
    "Creates a DRAFT feedback record with type=AIGenerated and queues a background task "
    "to invoke the BehavioralFeedbackAgent. "
    "On agent failure, logs the error and returns DRAFT feedback for manual fallback. "
    "Requires Interviewer, Recruiter, or Administrator role. Returns 202 Accepted with feedback ID.",
    responses={
        202: {"description": "Transcript accepted, AI processing queued", "model": FeedbackResponse},
        403: {"description": "Forbidden: User is not the assigned interviewer or insufficient role"},
        404: {"description": "Not found: Interview slot not found in organization"},
        422: {"description": "Validation error: Transcript exceeds 50000 characters"},
    },
)
async def submit_interview_transcript(
    request: TranscriptRequest,
    principal: Principal = Depends(require_role("Interviewer", "Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> FeedbackResponse:
    """
    Submit interview transcript for AI-generated behavioral feedback.

    Requirements: 3.4, 3.5

    Args:
        request: Transcript submission request with slot_id and transcript text
        principal: Authenticated principal with organization context and user ID
        db: Database session
        background_tasks: FastAPI background tasks for AI agent invocation

    Returns:
        FeedbackResponse with created DRAFT feedback (status=DRAFT, type=AIGenerated)

    Raises:
        HTTPException: 403 if not assigned interviewer, 404 if slot not found, 422 if transcript too long
    """
    service = InterviewFeedbackService(db)

    try:
        feedback = await service.submit_transcript(
            org_id=principal.organization_id,
            slot_id=request.slot_id,
            transcript=request.transcript,
            requesting_user_id=principal.user_id,
            background_tasks=background_tasks,
        )

        return FeedbackResponse.from_orm(feedback)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit interview transcript",
        ) from e
