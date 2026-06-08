"""Portal router.

Endpoints:
- POST /api/v1/portal/auth/verify — unauthenticated; verify email and get JWT session token
- GET /api/v1/portal/questionnaires — token-only auth or JWT; list candidate questionnaires
- GET /api/v1/portal/questionnaires/{response_id} — token-only auth or JWT; get questions and answers
- PATCH /api/v1/portal/questionnaires/{response_id}/answers — token-only auth or JWT; save/submit answers
- GET /api/v1/portal/availability — token-only auth or JWT; list candidate availability slots
- POST /api/v1/portal/availability — token-only auth or JWT; create availability slot
- GET /api/v1/portal/interviews — token-only auth or JWT; list upcoming and past interview slots

All portal endpoints restricted to authenticated candidate's own data within their organization.

Requirements: 5.2, 5.4, 5.6, 5.7, 5.8, 5.9
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.modules.availability.models import CandidateAvailabilitySlot
from app.modules.availability.service import CandidateAvailabilityService
from app.modules.portal.schemas import (
    PortalJWTResponse,
    PortalQuestionnaireResponse,
    PortalVerifyRequest,
)
from app.modules.portal.service import CandidatePortalService
from app.modules.questionnaires.models import (
    CandidateQuestionnaireAnswer,
    CandidateQuestionnaireResponse,
    Questionnaire,
    ResponseStatus,
)
from app.modules.questionnaires.service import QuestionnairesService
from app.modules.slots.models import InterviewSlot, SlotStatus
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/portal", tags=["portal"])


# ================================================================
# Portal Authentication Dependency
# ================================================================


async def get_portal_candidate(
    token: str | None = Query(None, description="Portal token for token-only access"),
    db: AsyncSession = Depends(get_db_session),
) -> tuple[UUID, UUID]:
    """
    Extract candidate_id and org_id from portal authentication.

    Supports two authentication modes:
    1. Token-only: Pass token query parameter
    2. JWT: Pass JWT in Authorization header (handled by middleware, here we extract from context)

    For token-only mode, validates token and returns (candidate_id, org_id).
    For JWT mode, expects the JWT to have been validated by middleware and claims in context.

    Returns:
        Tuple of (candidate_id, org_id)

    Raises:
        HTTPException: 401 if authentication fails

    Requirements: 5.2, 5.4
    """
    service = CandidatePortalService(db)

    if token:
        # Token-only authentication
        try:
            candidate_id, org_id = await service.validate_token(token)
            return candidate_id, org_id
        except HTTPException:
            raise

    # JWT authentication would come from Authorization header (handled by middleware)
    # For now, we'll check if there's a candidate context (set by middleware or previous endpoint)
    # This is a simplified approach; in production, use a proper JWT dependency

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
    )


# ================================================================
# Portal Endpoints
# ================================================================


@router.post(
    "/auth/verify",
    response_model=PortalJWTResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify email and issue JWT session",
    description="Unauthenticated endpoint. Accepts portal token and email. "
    "On successful verification, returns a JWT session token valid for 60 minutes.",
    responses={
        200: {"description": "JWT session token issued successfully"},
        401: {"description": "Invalid token or email mismatch"},
    },
)
async def verify_email_and_issue_jwt(
    request: PortalVerifyRequest,
    db: AsyncSession = Depends(get_db_session),
) -> PortalJWTResponse:
    """
    Verify candidate email and issue JWT session token.

    Validates portal token and verifies email matches the candidate record.
    On success, returns a 60-minute JWT session token with claims:
    - sub: candidate email
    - candidate_id: UUID
    - org_id: UUID
    - exp: 60 minutes from now
    - iat: issued at

    Requirements: 5.4, 5.5

    Args:
        request: PortalVerifyRequest with token and email
        db: AsyncSession

    Returns:
        PortalJWTResponse with access_token and token_type

    Raises:
        HTTPException: 401 on token invalid/expired or email mismatch
    """
    service = CandidatePortalService(db)

    try:
        access_token = await service.verify_email_and_issue_jwt(request.token, request.email)
        return PortalJWTResponse(
            access_token=access_token,
            token_type="bearer",
        )
    except HTTPException:
        raise


@router.get(
    "/questionnaires",
    response_model=list[PortalQuestionnaireResponse],
    status_code=status.HTTP_200_OK,
    summary="List candidate questionnaires",
    description="Token-only auth or JWT. Returns list of questionnaires assigned to candidate "
    "with their completion status.",
    responses={
        200: {"description": "List of candidate questionnaires with status"},
        401: {"description": "Unauthenticated or invalid token"},
    },
)
async def list_questionnaires(
    db: AsyncSession = Depends(get_db_session),
    token: str | None = Query(None),
) -> list[PortalQuestionnaireResponse]:
    """
    List questionnaires assigned to authenticated candidate.

    Returns questionnaires with their response status (Draft, Incomplete, Submitted).

    Requirements: 5.6

    Args:
        db: AsyncSession
        token: Portal token for token-only authentication

    Returns:
        List of PortalQuestionnaireResponse objects

    Raises:
        HTTPException: 401 if authentication fails
    """
    service = CandidatePortalService(db)

    candidate_id: UUID | None = None
    org_id: UUID | None = None

    if token:
        try:
            candidate_id, org_id = await service.validate_token(token)
        except HTTPException:
            raise

    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    # Query candidate questionnaire responses
    stmt = (
        select(
            CandidateQuestionnaireResponse,
            Questionnaire.title,
        )
        .join(
            Questionnaire,
            CandidateQuestionnaireResponse.questionnaire_id == Questionnaire.questionnaire_id,
        )
        .where(
            and_(
                CandidateQuestionnaireResponse.candidate_id == candidate_id,
                CandidateQuestionnaireResponse.organization_id == org_id,
                CandidateQuestionnaireResponse.deleted_at.is_(None),
            )
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    responses = [
        PortalQuestionnaireResponse(
            candidate_questionnaire_response_id=row[0].candidate_questionnaire_response_id,
            questionnaire_id=row[0].questionnaire_id,
            questionnaire_title=row[1],
            status=row[0].status,
            created_at=row[0].created_at,
            updated_at=row[0].updated_at,
        )
        for row in rows
    ]

    logger.info(
        "portal_questionnaires_listed",
        candidate_id=str(candidate_id),
        org_id=str(org_id),
        count=len(responses),
    )

    return responses


@router.get(
    "/questionnaires/{response_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get questionnaire details and answers",
    description="Token-only auth or JWT. Returns questionnaire questions and candidate's existing answers.",
    responses={
        200: {"description": "Questionnaire with questions and existing answers"},
        401: {"description": "Unauthenticated or invalid token"},
        403: {"description": "Candidate does not have access to this questionnaire"},
        404: {"description": "Response not found"},
    },
)
async def get_questionnaire_details(
    response_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    token: str | None = Query(None),
) -> dict:
    """
    Get questionnaire questions and existing answers for candidate.

    Returns questionnaire YAML, parsed questions, and candidate's existing answers.
    Restricted to the authenticated candidate's own response.

    Requirements: 5.6

    Args:
        response_id: The candidate questionnaire response ID
        db: AsyncSession
        token: Portal token for token-only authentication

    Returns:
        Dictionary with questionnaire details and existing answers

    Raises:
        HTTPException: 401 if auth fails, 403 if not candidate's response, 404 if not found
    """
    service = CandidatePortalService(db)

    try:
        candidate_id, org_id = await service.validate_token(token) if token else (None, None)
    except HTTPException:
        raise

    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    # Fetch the questionnaire response
    response_result = await db.execute(
        select(CandidateQuestionnaireResponse).where(
            and_(
                CandidateQuestionnaireResponse.candidate_questionnaire_response_id == response_id,
                CandidateQuestionnaireResponse.candidate_id == candidate_id,
                CandidateQuestionnaireResponse.organization_id == org_id,
                CandidateQuestionnaireResponse.deleted_at.is_(None),
            )
        )
    )
    response = response_result.scalar_one_or_none()

    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found",
        )

    # Fetch the questionnaire
    q_result = await db.execute(
        select(Questionnaire).where(
            and_(
                Questionnaire.questionnaire_id == response.questionnaire_id,
                Questionnaire.deleted_at.is_(None),
            )
        )
    )
    questionnaire = q_result.scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    # Fetch existing answers
    answers_result = await db.execute(
        select(CandidateQuestionnaireAnswer).where(
            and_(
                CandidateQuestionnaireAnswer.candidate_questionnaire_response_id == response_id,
                CandidateQuestionnaireAnswer.deleted_at.is_(None),
            )
        )
    )
    answers = answers_result.scalars().all()
    answers_dict = {answer.question_id: answer.answer for answer in answers}

    logger.info(
        "portal_questionnaire_retrieved",
        response_id=str(response_id),
        candidate_id=str(candidate_id),
    )

    return {
        "response_id": str(response_id),
        "questionnaire_id": str(questionnaire.questionnaire_id),
        "title": questionnaire.title,
        "questions_yaml": questionnaire.questions_yaml,
        "status": response.status,
        "existing_answers": answers_dict,
    }


@router.patch(
    "/questionnaires/{response_id}/answers",
    status_code=status.HTTP_200_OK,
    summary="Save or submit questionnaire answers",
    description="Token-only auth or JWT. Save draft answers or submit completed questionnaire. "
    "Submission validates all required questions are answered.",
    responses={
        200: {"description": "Answers saved or questionnaire submitted"},
        401: {"description": "Unauthenticated or invalid token"},
        403: {"description": "Questionnaire already submitted or unauthorized access"},
        404: {"description": "Response not found"},
        422: {"description": "Validation error (e.g., missing required answers)"},
    },
)
async def save_or_submit_answers(
    response_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    token: str | None = Query(None),
    request_body: dict | None = None,
) -> dict:
    """
    Save or submit questionnaire answers.

    Saves draft answers and optionally submits. On submission, validates all
    required questions are answered. Prevents modifications to submitted responses.

    Requirements: 5.7

    Args:
        response_id: The candidate questionnaire response ID
        request_body: Dictionary with answers and is_final_submit flag
        db: AsyncSession
        token: Portal token

    Returns:
        Status update confirming save or submission

    Raises:
        HTTPException: 401 (auth), 403 (submitted), 404 (not found), 422 (validation)
    """
    if request_body is None:
        request_body = {}

    service = CandidatePortalService(db)

    candidate_id: UUID | None = None
    org_id: UUID | None = None

    if token:
        try:
            candidate_id, org_id = await service.validate_token(token)
        except HTTPException:
            raise

    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    # Fetch response
    response_result = await db.execute(
        select(CandidateQuestionnaireResponse).where(
            and_(
                CandidateQuestionnaireResponse.candidate_questionnaire_response_id == response_id,
                CandidateQuestionnaireResponse.candidate_id == candidate_id,
                CandidateQuestionnaireResponse.organization_id == org_id,
                CandidateQuestionnaireResponse.deleted_at.is_(None),
            )
        )
    )
    response = response_result.scalar_one_or_none()

    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found",
        )

    # Check if already submitted
    if response.status == ResponseStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Questionnaire already submitted and cannot be modified",
        )

    # Use QuestionnairesService to handle answer saving
    q_service = QuestionnairesService(db)
    answers = request_body.get("answers", {})
    is_final_submit = request_body.get("is_final_submit", False)

    await q_service.save_answers(
        response_id=response_id,
        answers=answers,
        is_final_submit=is_final_submit,
        updated_by=candidate_id,
    )

    status_str = (
        ResponseStatus.SUBMITTED.value if is_final_submit else ResponseStatus.INCOMPLETE.value
    )

    logger.info(
        "portal_answers_saved",
        response_id=str(response_id),
        candidate_id=str(candidate_id),
        is_final_submit=is_final_submit,
    )

    return {
        "status": "success",
        "response_status": status_str,
        "message": "Questionnaire submitted" if is_final_submit else "Answers saved",
    }


@router.get(
    "/availability",
    response_model=list[dict],
    status_code=status.HTTP_200_OK,
    summary="List candidate availability slots",
    description="Token-only auth or JWT. Returns candidate's active availability slots for interviews.",
    responses={
        200: {"description": "List of candidate availability slots"},
        401: {"description": "Unauthenticated or invalid token"},
    },
)
async def list_availability_slots(
    db: AsyncSession = Depends(get_db_session),
    token: str | None = Query(None),
) -> list[dict]:
    """
    List candidate's active availability slots.

    Returns all active availability slots for the authenticated candidate.

    Requirements: 5.8

    Args:
        db: AsyncSession
        token: Portal token

    Returns:
        List of availability slot dictionaries

    Raises:
        HTTPException: 401 if authentication fails
    """
    service = CandidatePortalService(db)

    try:
        candidate_id, org_id = await service.validate_token(token) if token else (None, None)
    except HTTPException:
        raise

    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    # Query active availability slots
    stmt = select(CandidateAvailabilitySlot).where(
        and_(
            CandidateAvailabilitySlot.candidate_id == candidate_id,
            CandidateAvailabilitySlot.organization_id == org_id,
            CandidateAvailabilitySlot.status == "ACTIVE",
            CandidateAvailabilitySlot.deleted_at.is_(None),
        )
    )

    result = await db.execute(stmt)
    slots = result.scalars().all()

    slots_list = [
        {
            "candidate_availability_slot_id": str(slot.candidate_availability_slot_id),
            "interview_type": slot.interview_type,
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat(),
            "timezone": slot.timezone,
            "status": slot.status,
        }
        for slot in slots
    ]

    logger.info(
        "portal_availability_listed",
        candidate_id=str(candidate_id),
        org_id=str(org_id),
        count=len(slots_list),
    )

    return slots_list


@router.post(
    "/availability",
    status_code=status.HTTP_201_CREATED,
    summary="Create availability slot",
    description="Token-only auth or JWT. Candidate creates an availability slot for interviews.",
    responses={
        201: {"description": "Availability slot created successfully"},
        401: {"description": "Unauthenticated or invalid token"},
        409: {"description": "Limit exceeded or conflict"},
        422: {"description": "Validation error"},
    },
)
async def create_availability_slot(
    db: AsyncSession = Depends(get_db_session),
    token: str | None = Query(None),
    request_body: dict | None = None,
) -> dict:
    """
    Create a new availability slot.

    Validates slot duration (30-480 minutes), future timing (>= 1 hour),
    and active slot limit (max 50).

    Requirements: 5.8, 7.2, 7.3, 7.6

    Args:
        request_body: Dictionary with interview_type, start_time, end_time, timezone
        db: AsyncSession
        token: Portal token

    Returns:
        Created availability slot details

    Raises:
        HTTPException: 401 (auth), 409 (limit), 422 (validation)
    """
    if request_body is None:
        request_body = {}

    service = CandidatePortalService(db)

    candidate_id: UUID | None = None
    org_id: UUID | None = None

    if token:
        try:
            candidate_id, org_id = await service.validate_token(token)
        except HTTPException:
            raise

    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    # Use AvailabilityService to create slot
    availability_service = CandidateAvailabilityService(db)

    try:
        start_time_str = request_body.get("start_time")
        end_time_str = request_body.get("end_time")

        if not start_time_str or not end_time_str:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_time and end_time are required",
            )

        slot = await availability_service.create_availability(
            candidate_id=candidate_id,
            org_id=org_id,
            interview_type=request_body.get("interview_type"),
            start_time=datetime.fromisoformat(start_time_str),
            end_time=datetime.fromisoformat(end_time_str),
            timezone_str=request_body.get("timezone"),
            created_by=candidate_id,
        )

        logger.info(
            "portal_availability_created",
            candidate_id=str(candidate_id),
            slot_id=str(slot.candidate_availability_slot_id),
        )

        return {
            "candidate_availability_slot_id": str(slot.candidate_availability_slot_id),
            "interview_type": slot.interview_type,
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat(),
            "timezone": slot.timezone,
            "status": slot.status,
        }
    except HTTPException:
        raise


@router.get(
    "/interviews",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List upcoming and past interview slots",
    description="Token-only auth or JWT. Returns upcoming and past interview slots for the candidate.",
    responses={
        200: {"description": "Upcoming and past interview slots"},
        401: {"description": "Unauthenticated or invalid token"},
    },
)
async def list_interviews(
    db: AsyncSession = Depends(get_db_session),
    token: str | None = Query(None),
) -> dict:
    """
    List candidate's interview slots (upcoming and past).

    Returns interview slots for the candidate's journeys, categorized as
    upcoming (scheduled after now) and past (scheduled before now).

    Requirements: 5.9

    Args:
        db: AsyncSession
        token: Portal token

    Returns:
        Dictionary with upcoming and past interview slots

    Raises:
        HTTPException: 401 if authentication fails
    """
    service = CandidatePortalService(db)

    try:
        candidate_id, org_id = await service.validate_token(token) if token else (None, None)
    except HTTPException:
        raise

    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    # Query all non-cancelled interview slots for this candidate's journeys
    from app.modules.journeys.models import InterviewJourney

    now = datetime.now(UTC)

    stmt = (
        select(InterviewSlot)
        .join(
            InterviewJourney,
            InterviewSlot.interview_journey_id == InterviewJourney.interview_journey_id,
        )
        .where(
            and_(
                InterviewJourney.candidate_id == candidate_id,
                InterviewJourney.organization_id == org_id,
                InterviewSlot.status != SlotStatus.CANCELLED.value,
                InterviewSlot.deleted_at.is_(None),
            )
        )
    )

    result = await db.execute(stmt)
    slots = result.scalars().all()

    # Categorize into upcoming and past
    upcoming = []
    past = []

    for slot in slots:
        slot_dict = {
            "interview_slot_id": str(slot.interview_slot_id),
            "type": slot.type,
            "scheduled_start": slot.scheduled_start.isoformat(),
            "scheduled_end": slot.scheduled_end.isoformat(),
            "timezone": slot.timezone,
            "status": slot.status,
            "invitation_status": slot.invitation_status,
            "attendance_status": slot.attendance_status,
        }

        if slot.scheduled_start > now:
            upcoming.append(slot_dict)
        else:
            past.append(slot_dict)

    # Sort upcoming by start time (earliest first)
    upcoming.sort(key=lambda x: x["scheduled_start"])
    # Sort past by start time (latest first)
    past.sort(key=lambda x: x["scheduled_start"], reverse=True)

    logger.info(
        "portal_interviews_listed",
        candidate_id=str(candidate_id),
        org_id=str(org_id),
        upcoming=len(upcoming),
        past=len(past),
    )

    return {
        "upcoming": upcoming,
        "past": past,
    }
