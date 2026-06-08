"""
Interview slot router for scheduling and managing interview slots.

Endpoints:
- POST /slots: Create a new interview slot
- GET /slots: List interview slots
- GET /slots/{slot_id}: Retrieve a specific slot
- PATCH /slots/{slot_id}: Update slot details
- PATCH /slots/{slot_id}/attendance: Update attendance status
- PATCH /slots/{slot_id}/invitation: Update invitation status (interviewer self-service)

Requirements: 2.1, 2.2, 2.5, 2.6, 2.7, 2.9
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.slots.models import InterviewSlot, InterviewerPreference, AttendanceStatus, InvitationStatus
from app.modules.slots.schemas import (
    SlotCreate,
    SlotUpdate,
    SlotResponse,
    InterviewerPreferenceCreate,
)
from app.modules.slots.service import InterviewSlotService

router = APIRouter(prefix="/slots", tags=["slots"])
prefs_router = APIRouter(prefix="/interviewer-preferences", tags=["interviewer-preferences"])


@router.post(
    "",
    response_model=SlotResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_interview_slot",
    summary="Create a new interview slot",
    description="Create a new interview slot for a journey. "
    "Validates slot duration (15-480 minutes), validates interviewer assignment constraints "
    "(max interviews per day/week, allowed interview types), and publishes interview_slot_created event. "
    "Requires Recruiter or Administrator role. Returns 201 with slot details.",
    responses={
        201: {"description": "Slot created successfully", "model": SlotResponse},
        400: {"description": "Invalid request data (invalid times)"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Journey not found in organization"},
        409: {"description": "Conflict: Interviewer constraint violated (max interviews, interview type)"},
        422: {"description": "Validation error: Invalid slot duration or times"},
    },
)
async def create_interview_slot(
    request: SlotCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> SlotResponse:
    """
    Create a new interview slot.

    Requirements: 2.1, 2.4, 2.5

    Args:
        request: Slot creation request
        principal: Authenticated principal with organization context
        db: Database session
        background_tasks: FastAPI background tasks for event dispatch

    Returns:
        SlotResponse with created slot details

    Raises:
        HTTPException: 400 on invalid times, 409 on constraint violation, 422 on invalid duration
    """
    service = InterviewSlotService(db)

    try:
        slot = await service.create_slot(
            org_id=principal.organization_id,
            journey_id=request.interview_journey_id,
            slot_type=request.type,
            scheduled_start=request.scheduled_start,
            scheduled_end=request.scheduled_end,
            timezone_str=request.timezone,
            interviewer_user_id=request.interviewer_user_id,
            background_tasks=background_tasks,
        )

        return SlotResponse.from_orm(slot)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create interview slot",
        ) from e


@router.get(
    "",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="list_interview_slots",
    summary="List interview slots",
    description="List all interview slots in the organization with optional filtering and pagination. "
    "Supports filtering by journey_id and interviewer_user_id. "
    "Requires Recruiter, Administrator, or HiringManager role. "
    "Returns paginated list with total count.",
    responses={
        200: {"description": "Slots retrieved successfully"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_interview_slots(
    journey_id: UUID | None = Query(None, description="Filter by journey ID (optional)"),
    interviewer_user_id: UUID | None = Query(None, description="Filter by interviewer user ID (optional)"),
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
    List interview slots.

    Requirements: 2.1

    Args:
        journey_id: Optional filter by journey ID
        interviewer_user_id: Optional filter by interviewer user ID
        page: Page number (1-indexed)
        page_size: Items per page
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        Dictionary with data (list of SlotResponse) and meta (total, page, page_size)
    """
    try:
        offset = (page - 1) * page_size

        # Build query
        query = select(InterviewSlot).where(
            InterviewSlot.organization_id == principal.organization_id,
            InterviewSlot.deleted_at.is_(None),
        )

        if journey_id:
            query = query.where(InterviewSlot.interview_journey_id == journey_id)
        if interviewer_user_id:
            query = query.where(InterviewSlot.interviewer_user_id == interviewer_user_id)

        # Get total count
        count_query = query.with_only_columns(None).count()
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(InterviewSlot.scheduled_start.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        slots = result.scalars().all()

        return {
            "data": [SlotResponse.from_orm(s) for s in slots],
            "meta": {
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list interview slots",
        ) from e


@router.get(
    "/{slot_id}",
    response_model=SlotResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_interview_slot",
    summary="Retrieve a specific interview slot",
    description="Retrieve details of a specific interview slot by ID. "
    "Requires Recruiter, Administrator, or HiringManager role. "
    "Returns slot with all current state information.",
    responses={
        200: {"description": "Slot retrieved successfully", "model": SlotResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Slot not found in organization"},
    },
)
async def get_interview_slot(
    slot_id: UUID,
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> SlotResponse:
    """
    Retrieve a specific interview slot.

    Requirements: 2.1

    Args:
        slot_id: Slot ID
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        SlotResponse with slot details

    Raises:
        HTTPException: 404 if slot not found
    """
    try:
        result = await db.execute(
            select(InterviewSlot).where(
                InterviewSlot.interview_slot_id == slot_id,
                InterviewSlot.organization_id == principal.organization_id,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        slot = result.scalar_one_or_none()

        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview slot not found",
            )

        return SlotResponse.from_orm(slot)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interview slot",
        ) from e


@router.patch(
    "/{slot_id}",
    response_model=SlotResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_interview_slot",
    summary="Update interview slot details",
    description="Update details of an existing interview slot (status, invitation_status). "
    "Requires Recruiter or Administrator role. "
    "Returns 200 with updated slot.",
    responses={
        200: {"description": "Slot updated successfully", "model": SlotResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Slot not found in organization"},
        409: {"description": "Conflict: Optimistic lock failure (version mismatch)"},
    },
)
async def update_interview_slot(
    slot_id: UUID,
    request: SlotUpdate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> SlotResponse:
    """
    Update interview slot details.

    Requirements: 2.1

    Args:
        slot_id: Slot ID
        request: Update request with optional status, invitation_status
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        SlotResponse with updated slot

    Raises:
        HTTPException: 404 if slot not found
    """
    try:
        result = await db.execute(
            select(InterviewSlot).where(
                InterviewSlot.interview_slot_id == slot_id,
                InterviewSlot.organization_id == principal.organization_id,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        slot = result.scalar_one_or_none()

        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview slot not found",
            )

        # Update provided fields
        if request.status is not None:
            slot.status = request.status
        if request.invitation_status is not None:
            slot.invitation_status = request.invitation_status

        await db.flush()
        return SlotResponse.from_orm(slot)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update interview slot",
        ) from e


@router.patch(
    "/{slot_id}/attendance",
    response_model=SlotResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_slot_attendance",
    summary="Update interview attendance status",
    description="Update attendance status (ATTENDED, NO_SHOW) for a completed interview slot. "
    "Can only be updated after the slot's scheduled_end time has passed. "
    "Requires Recruiter or Administrator role. "
    "Returns 200 with updated slot.",
    responses={
        200: {"description": "Attendance updated successfully", "model": SlotResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not found: Slot not found in organization"},
        409: {"description": "Conflict: Slot is still in the future"},
    },
)
async def update_slot_attendance(
    slot_id: UUID,
    attendance_status: str = Query(..., description="Attendance status: ATTENDED or NO_SHOW"),
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> SlotResponse:
    """
    Update interview attendance status.

    Requirements: 2.7

    Args:
        slot_id: Slot ID
        attendance_status: New attendance status (ATTENDED or NO_SHOW)
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        SlotResponse with updated slot

    Raises:
        HTTPException: 404 if slot not found, 409 if slot is still in the future
    """
    service = InterviewSlotService(db)

    try:
        result = await db.execute(
            select(InterviewSlot).where(
                InterviewSlot.interview_slot_id == slot_id,
                InterviewSlot.organization_id == principal.organization_id,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        slot = result.scalar_one_or_none()

        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview slot not found",
            )

        # Use service to update with time validation
        updated_slot = await service.update_attendance_status(slot, attendance_status)
        return SlotResponse.from_orm(updated_slot)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update attendance status",
        ) from e


@router.patch(
    "/{slot_id}/invitation",
    response_model=SlotResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_slot_invitation",
    summary="Update interview invitation status (interviewer self-service)",
    description="Update invitation status (ACCEPTED or DECLINED) for a scheduled interview slot. "
    "Can only be updated by the assigned interviewer. "
    "No role requirement (authenticated interviewer only). "
    "Returns 200 with updated slot.",
    responses={
        200: {"description": "Invitation status updated successfully", "model": SlotResponse},
        403: {"description": "Forbidden: User is not the assigned interviewer"},
        404: {"description": "Not found: Slot not found in organization"},
    },
)
async def update_slot_invitation(
    slot_id: UUID,
    invitation_status: str = Query(..., description="Invitation status: ACCEPTED or DECLINED"),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> SlotResponse:
    """
    Update interview invitation status (interviewer self-service).

    Requirements: 2.6

    Args:
        slot_id: Slot ID
        invitation_status: New invitation status (ACCEPTED or DECLINED)
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        SlotResponse with updated slot

    Raises:
        HTTPException: 403 if user is not the assigned interviewer, 404 if slot not found
    """
    service = InterviewSlotService(db)

    try:
        result = await db.execute(
            select(InterviewSlot).where(
                InterviewSlot.interview_slot_id == slot_id,
                InterviewSlot.organization_id == principal.organization_id,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        slot = result.scalar_one_or_none()

        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview slot not found",
            )

        # Only assigned interviewer can update invitation status
        if slot.interviewer_user_id != principal.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the assigned interviewer can update the invitation status",
            )

        updated_slot = await service.update_invitation_status(slot, invitation_status)
        return SlotResponse.from_orm(updated_slot)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update invitation status",
        ) from e


@prefs_router.get(
    "/{user_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="get_interviewer_preferences",
    summary="Get interviewer scheduling preferences",
    description="Get interviewer scheduling preferences including max interviews per day/week "
    "and allowed interview types. "
    "Can be accessed by the interviewer themselves, or by Administrator/SuperAdministrator. "
    "Returns preferences or default values if no preference record exists.",
    responses={
        200: {"description": "Preferences retrieved successfully"},
        403: {"description": "Forbidden: User does not have permission to view these preferences"},
        404: {"description": "Not found: User not found"},
    },
)
async def get_interviewer_preferences(
    user_id: UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Get interviewer scheduling preferences.

    Requirements: 2.8, 2.9

    Args:
        user_id: Interviewer user ID
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        Dictionary with interviewer preferences

    Raises:
        HTTPException: 403 if not authorized to view preferences
    """
    try:
        # Authorization: only interviewer themselves or admin
        if (
            principal.user_id != user_id
            and principal.role not in ("Administrator", "SuperAdministrator")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view these preferences",
            )

        result = await db.execute(
            select(InterviewerPreference).where(
                InterviewerPreference.interviewer_user_id == user_id,
                InterviewerPreference.organization_id == principal.organization_id,
                InterviewerPreference.deleted_at.is_(None),
            )
        )
        pref = result.scalar_one_or_none()

        if pref:
            return {
                "interviewer_user_id": str(pref.interviewer_user_id),
                "allowed_interview_types": pref.allowed_interview_types,
                "max_interviews_per_day": pref.max_interviews_per_day,
                "max_interviews_per_week": pref.max_interviews_per_week,
                "working_hours": pref.working_hours,
                "version": pref.version,
            }
        else:
            # Return defaults (Req 2.10)
            return {
                "interviewer_user_id": str(user_id),
                "allowed_interview_types": ["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"],
                "max_interviews_per_day": 5,
                "max_interviews_per_week": 20,
                "working_hours": None,
                "version": 0,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve preferences",
        ) from e


@prefs_router.put(
    "/{user_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="create_or_update_interviewer_preferences",
    summary="Create or update interviewer scheduling preferences",
    description="Create or update interviewer scheduling preferences (max interviews per day/week, "
    "allowed interview types, working hours). "
    "Can only be modified by the interviewer themselves or by Administrator/SuperAdministrator. "
    "Validates max_interviews_per_day (1-20) and max_interviews_per_week (1-100). "
    "Returns 200 with updated preferences.",
    responses={
        200: {"description": "Preferences updated successfully"},
        403: {"description": "Forbidden: User does not have permission to modify these preferences"},
        404: {"description": "Not found: User not found"},
        422: {"description": "Validation error: Invalid max interviews or interview types"},
    },
)
async def create_or_update_interviewer_preferences(
    user_id: UUID,
    request: InterviewerPreferenceCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Create or update interviewer scheduling preferences.

    Requirements: 2.8, 2.9

    Args:
        user_id: Interviewer user ID
        request: Preference creation/update request
        principal: Authenticated principal with organization context
        db: Database session

    Returns:
        Dictionary with created/updated preferences

    Raises:
        HTTPException: 403 if not authorized, 422 if validation fails
    """
    service = InterviewSlotService(db)

    try:
        pref = await service.create_or_update_preference(
            org_id=principal.organization_id,
            interviewer_user_id=user_id,
            current_user_id=principal.user_id,
            current_user_role=principal.role,
            allowed_interview_types=request.allowed_interview_types,
            max_interviews_per_day=request.max_interviews_per_day,
            max_interviews_per_week=request.max_interviews_per_week,
            working_hours=request.working_hours,
        )

        return {
            "interviewer_user_id": str(pref.interviewer_user_id),
            "allowed_interview_types": pref.allowed_interview_types,
            "max_interviews_per_day": pref.max_interviews_per_day,
            "max_interviews_per_week": pref.max_interviews_per_week,
            "working_hours": pref.working_hours,
            "version": pref.version,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences",
        ) from e
