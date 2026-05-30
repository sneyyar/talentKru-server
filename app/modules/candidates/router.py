"""
Candidate router for CRUD operations and status management.

Endpoints:
- POST /candidates: Create a new candidate (201)
- GET /candidates: List candidates with pagination and search
- GET /candidates/{candidate_id}: Retrieve a specific candidate
- PATCH /candidates/{candidate_id}: Update candidate status

Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.candidates.models import GlobalStatus
from app.modules.candidates.schemas import (
    CandidateCreate,
    CandidateResponse,
    CandidateSearchParams,
    CandidateUpdate,
)
from app.modules.candidates.service import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post(
    "",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_candidate",
    summary="Create a new candidate",
    description="Create a new candidate profile in the organization with Active status. Requires Recruiter or Administrator role.",
    responses={
        201: {"description": "Candidate created successfully", "model": CandidateResponse},
        400: {"description": "Invalid request data"},
        403: {"description": "Forbidden: User does not have required role"},
        409: {"description": "Conflict: Email already exists in organization"},
    },
)
async def create_candidate(
    request: CandidateCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> CandidateResponse:
    """
    Create a new candidate.

    Requirements: 1.1, 1.2
    
    Args:
        request: Candidate creation request with name, email, phone, location
        principal: Authenticated principal with organization context
        db: Database session
        background_tasks: FastAPI background tasks for event dispatch
        
    Returns:
        CandidateResponse with created candidate details
        
    Raises:
        HTTPException: 409 if email already exists in organization
    """
    service = CandidateService(db)

    try:
        candidate = await service.create_candidate(
            org_id=principal.organization_id,
            name=request.name,
            email=request.email,
            phone=request.phone,
            location=request.location,
            created_by=principal.user_id,
            background_tasks=background_tasks,
        )
        await db.commit()

        # Decrypt PII for response
        decrypted = await service.decrypt_candidate(candidate)
        return CandidateResponse(**decrypted)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create candidate",
        ) from e


@router.get(
    "",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="list_candidates",
    summary="List candidates with search and pagination",
    description="List candidates in the organization with optional filtering by name, email, or status. Supports pagination with max 50 per page. Requires Recruiter, Administrator, or HiringManager role.",
)
async def list_candidates(
    name: str | None = Query(
        None, description="Partial name search (case-insensitive)"
    ),
    email: str | None = Query(
        None, description="Partial email search (case-insensitive)"
    ),
    status: str | None = Query(
        None,
        description="Exact status match (Active, Interviewing, Expired, Ineligible, Deleted)",
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        50, ge=1, le=50, description="Results per page (max 50)"
    ),
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List candidates with pagination and search.

    Requirements: 1.6
    
    Args:
        name: Optional partial name search
        email: Optional partial email search
        status: Optional exact status match
        page: Page number (1-indexed)
        page_size: Results per page (max 50)
        principal: Authenticated principal with organization context
        db: Database session
        
    Returns:
        Dictionary with items, total, page, page_size
    """
    service = CandidateService(db)

    # Parse status if provided
    parsed_status = None
    if status:
        try:
            parsed_status = GlobalStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}. Must be one of: Active, Interviewing, Expired, Ineligible, Deleted",
            )

    # Calculate offset
    offset = (page - 1) * page_size

    # Search candidates
    candidates, total_count = await service.search_candidates(
        org_id=principal.organization_id,
        name=name,
        email=email,
        status=parsed_status,
        offset=offset,
        limit=page_size,
    )

    # Decrypt PII for response
    items = []
    for candidate in candidates:
        decrypted = await service.decrypt_candidate(candidate)
        items.append(CandidateResponse(**decrypted))

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_candidate",
    summary="Retrieve a candidate by ID",
    description="Retrieve a specific candidate profile by ID. Requires Recruiter, Administrator, or HiringManager role.",
)
async def get_candidate(
    candidate_id: UUID,
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> CandidateResponse:
    """
    Retrieve a candidate by ID.

    Requirements: 1.6
    
    Args:
        candidate_id: Candidate ID to retrieve
        principal: Authenticated principal with organization context
        db: Database session
        
    Returns:
        CandidateResponse with candidate details
        
    Raises:
        HTTPException: 404 if candidate not found
    """
    service = CandidateService(db)

    candidate = await service.get_candidate(candidate_id, principal.organization_id)

    # Decrypt PII for response
    decrypted = await service.decrypt_candidate(candidate)
    return CandidateResponse(**decrypted)


@router.patch(
    "/{candidate_id}",
    response_model=CandidateResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_candidate",
    summary="Update candidate status and details",
    description="Update candidate status with FSM validation and handle status transitions. Requires Recruiter or Administrator role.",
)
async def update_candidate(
    candidate_id: UUID,
    request: CandidateUpdate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> CandidateResponse:
    """
    Update candidate status and details.

    Requirements: 1.4, 1.5, 1.7, 1.8
    
    Args:
        candidate_id: Candidate ID to update
        request: Update request with optional status, ineligibility_reason, etc.
        principal: Authenticated principal with organization context
        db: Database session
        background_tasks: FastAPI background tasks for event dispatch
        
    Returns:
        CandidateResponse with updated candidate details
        
    Raises:
        HTTPException: 404 if candidate not found
        HTTPException: 400 if status transition is invalid or ineligibility_reason missing
    """
    service = CandidateService(db)

    try:
        # Fetch candidate
        candidate = await service.get_candidate(candidate_id, principal.organization_id)

        # Handle status transition if provided
        if request.global_status:
            try:
                new_status = GlobalStatus(request.global_status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {request.global_status}. Must be one of: Active, Interviewing, Expired, Ineligible, Deleted",
                )

            candidate = await service.transition_status(
                candidate=candidate,
                new_status=new_status,
                ineligibility_reason=request.ineligibility_reason,
                updated_by=principal.user_id,
                background_tasks=background_tasks,
            )

        await db.commit()

        # Decrypt PII for response
        decrypted = await service.decrypt_candidate(candidate)
        return CandidateResponse(**decrypted)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update candidate",
        ) from e
