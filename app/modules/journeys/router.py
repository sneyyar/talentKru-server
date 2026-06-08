"""
Interview journey router for lifecycle management.

Endpoints:
- POST /journeys: Create a new journey
- GET /journeys: List journeys with pagination
- GET /journeys/{journey_id}: Retrieve a specific journey
- POST /journeys/{journey_id}/transition: Transition journey stage
- GET /journeys/{journey_id}/history: Get paginated stage history

Requirements: 1.1, 1.2, 1.4, 1.7, 1.8
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.journeys.models import JourneyStage
from app.modules.journeys.schemas import (
    JourneyCreate,
    JourneyResponse,
    JourneyTransitionRequest,
    StageHistoryResponse,
)
from app.modules.journeys.service import InterviewJourneyService

router = APIRouter(prefix="/journeys", tags=["journeys"])


@router.post(
    "",
    response_model=JourneyResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_journey",
    summary="Create a new interview journey",
    description="Create a new interview journey for a candidate on a job requisition. "
    "Initializes with SOURCED stage and ACTIVE overall status. "
    "Requires Recruiter or Administrator role. Returns 201 with journey details.",
    responses={
        201: {"description": "Journey created successfully", "model": JourneyResponse},
        400: {"description": "Invalid request data"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Candidate or job requisition not found"},
    },
)
async def create_journey(
    request: JourneyCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> JourneyResponse:
    """
    Create a new interview journey.

    Requirements: 1.1, 1.2

    Args:
        request: Journey creation request with candidate_id and job_requisition_id
        principal: Authenticated principal with organization context
        db: Database session
        background_tasks: FastAPI background tasks for event dispatch

    Returns:
        JourneyResponse with created journey details

    Raises:
        HTTPException: 400 if validation fails, 404 if resources not found
    """
    service = InterviewJourneyService(db)

    try:
        journey = await service.create_journey(
            org_id=principal.organization_id,
            candidate_id=request.candidate_id,
            job_requisition_id=request.job_requisition_id,
            created_by=principal.user_id,
            background_tasks=background_tasks,
        )

        return JourneyResponse.from_orm(journey)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create journey",
        ) from e


@router.get(
    "",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="list_journeys",
    summary="List interview journeys",
    description="List all interview journeys in the organization with optional pagination. "
    "Supports filtering by candidate_id. "
    "Requires Recruiter, Administrator, or HiringManager role. "
    "Returns paginated list with total count.",
    responses={
        200: {"description": "Journeys retrieved successfully"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_journeys(
    candidate_id: UUID | None = Query(
        None, description="Filter by candidate ID (optional)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        50, ge=1, le=100, description="Items per page (1-100, default 50)"
    ),
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List interview journeys.

    Requirements: 1.1

    Args:
        candidate_id: Optional filter by candidate ID
        page: Page number (1-indexed)
        page_size: Items per page
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        Dictionary with data (list of JourneyResponse) and meta (total, page, page_size)
    """
    service = InterviewJourneyService(db)

    try:
        offset = (page - 1) * page_size
        journeys, total = await service.list_journeys(
            org_id=principal.organization_id,
            candidate_id=candidate_id,
            limit=page_size,
            offset=offset,
        )

        return {
            "data": [JourneyResponse.from_orm(j) for j in journeys],
            "meta": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list journeys",
        ) from e


@router.get(
    "/{journey_id}",
    response_model=JourneyResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_journey",
    summary="Retrieve a specific interview journey",
    description="Retrieve details of a specific interview journey by ID. "
    "Requires Recruiter, Administrator, or HiringManager role. "
    "Returns journey with all current state information.",
    responses={
        200: {"description": "Journey retrieved successfully", "model": JourneyResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Journey not found in organization"},
    },
)
async def get_journey(
    journey_id: UUID,
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> JourneyResponse:
    """
    Retrieve a specific interview journey.

    Requirements: 1.1

    Args:
        journey_id: Journey ID
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        JourneyResponse with journey details

    Raises:
        HTTPException: 404 if journey not found
    """
    service = InterviewJourneyService(db)

    try:
        journey = await service.get_journey(journey_id, principal.organization_id)

        if not journey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journey not found",
            )

        return JourneyResponse.from_orm(journey)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve journey",
        ) from e


@router.post(
    "/{journey_id}/transition",
    response_model=JourneyResponse,
    status_code=status.HTTP_200_OK,
    operation_id="transition_journey_stage",
    summary="Transition interview journey to next stage",
    description="Transition an interview journey to a new stage using FSM rules. "
    "Validates that the transition is allowed from the current stage. "
    "Creates a stage history record and encrypts PII on OfferAccepted. "
    "Requires Recruiter or Administrator role. "
    "Returns 200 with updated journey.",
    responses={
        200: {"description": "Stage transition successful", "model": JourneyResponse},
        400: {"description": "Invalid stage transition or validation error"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Journey not found in organization"},
        409: {"description": "Conflict: Optimistic lock failure (version mismatch)"},
    },
)
async def transition_journey_stage(
    journey_id: UUID,
    request: JourneyTransitionRequest,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> JourneyResponse:
    """
    Transition interview journey to a new stage.

    Requirements: 1.2, 1.4, 1.7, 1.8

    Args:
        journey_id: Journey ID
        request: Transition request with to_stage and optional comments
        principal: Authenticated principal with organization context
        db: Database session
        background_tasks: FastAPI background tasks for event dispatch

    Returns:
        JourneyResponse with updated journey

    Raises:
        HTTPException: 400 on invalid transition, 404 if journey not found
    """
    service = InterviewJourneyService(db)

    try:
        # Fetch the journey
        journey = await service.get_journey(journey_id, principal.organization_id)

        if not journey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journey not found",
            )

        # Parse the target stage
        try:
            to_stage = JourneyStage(request.to_stage)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {request.to_stage}",
            )

        # Transition the stage
        updated_journey = await service.transition_stage(
            journey=journey,
            to_stage=to_stage,
            changed_by=principal.user_id,
            comments=request.comments,
            background_tasks=background_tasks,
        )

        return JourneyResponse.from_orm(updated_journey)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transition journey stage",
        ) from e


@router.get(
    "/{journey_id}/history",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="get_journey_history",
    summary="Get stage transition history",
    description="Get paginated stage transition history for an interview journey. "
    "Shows all stage changes with timestamps, user info, and comments. "
    "Requires Recruiter, Administrator, or HiringManager role. "
    "Returns paginated history records.",
    responses={
        200: {"description": "History retrieved successfully"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Journey not found in organization"},
    },
)
async def get_journey_history(
    journey_id: UUID,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        50, ge=1, le=100, description="Items per page (1-100, default 50)"
    ),
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Get stage transition history for a journey.

    Requirements: 1.1, 1.4

    Args:
        journey_id: Journey ID
        page: Page number (1-indexed)
        page_size: Items per page
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        Dictionary with data (list of StageHistoryResponse) and meta (total, page, page_size)

    Raises:
        HTTPException: 404 if journey not found
    """
    service = InterviewJourneyService(db)

    try:
        # Verify journey exists in organization
        journey = await service.get_journey(journey_id, principal.organization_id)

        if not journey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journey not found",
            )

        # Get history
        offset = (page - 1) * page_size
        history, total = await service.get_journey_history(
            journey_id=journey_id,
            org_id=principal.organization_id,
            limit=page_size,
            offset=offset,
        )

        return {
            "data": [StageHistoryResponse.from_orm(h) for h in history],
            "meta": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve journey history",
        ) from e
