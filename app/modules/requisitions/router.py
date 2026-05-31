"""Job requisition router.

Endpoints:
- POST /api/v1/requisitions — require_role("Recruiter", "Administrator"); returns 201
- GET /api/v1/requisitions — require_role("Recruiter", "Administrator", "HiringManager")
- GET /api/v1/requisitions/{requisition_id} — require_role("Recruiter", "Administrator", "HiringManager")
- PATCH /api/v1/requisitions/{requisition_id} — require_role("Recruiter", "Administrator")
- POST /api/v1/requisitions/{requisition_id}/candidates — require_role("Recruiter", "Administrator"); associate candidate
- POST /api/v1/requisitions/{requisition_id}/required-skills — require_role("Recruiter", "Administrator")

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import require_role
from app.modules.requisitions.models import JobRequisition, CandidateRequisition
from app.modules.skills.models import RequisitionRequiredSkill
from app.modules.requisitions.schemas import (
    RequisitionCreate,
    RequisitionUpdate,
    RequisitionResponse,
    CandidateAssociationRequest,
    RequiredSkillCreate,
)
from app.modules.requisitions.service import RequisitionService
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/requisitions", tags=["requisitions"])


@router.post(
    "",
    response_model=RequisitionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_requisition",
    summary="Create a new job requisition",
    description="Create a new job requisition with status always set to OPEN. Requires Recruiter or Administrator role. Returns 201 Created.",
    responses={
        201: {"description": "Requisition created successfully", "model": RequisitionResponse},
        400: {"description": "Invalid request data"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def create_requisition(
    request: RequisitionCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> RequisitionResponse:
    """
    Create a new job requisition.
    
    Status is always set to OPEN regardless of any value in the request body.
    Publishes requisition_status_changed event.
    
    Requirements: 5.1, 5.2
    """
    service = RequisitionService(db)
    
    requisition = await service.create_requisition(
        org_id=principal.organization_id,
        job_profile_id=request.job_profile_id,
        hiring_manager_user_id=request.hiring_manager_user_id,
        title=request.title,
        department=request.department,
        location=request.location,
        description=request.description,
        created_by=principal.user_id,
        background_tasks=background_tasks,
    )
    
    await db.commit()
    return RequisitionResponse.from_orm(requisition)


@router.get(
    "",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="list_requisitions",
    summary="List job requisitions",
    description="List all job requisitions in the organization with optional filtering and pagination. Requires Recruiter, Administrator, or HiringManager role. Returns paginated list with total count.",
    responses={
        200: {"description": "Requisitions retrieved successfully"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_requisitions(
    status: str | None = Query(None, description="Filter by requisition status (OPEN, ON_HOLD, CLOSED, CANCELLED)"),
    hiring_manager_user_id: UUID | None = Query(None, description="Filter by hiring manager user ID"),
    department: str | None = Query(None, description="Filter by department"),
    domain: str | None = Query(None, description="Filter by skill domain"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=50, description="Results per page (max 50)"),
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List job requisitions with optional filters.
    
    Supports filtering by status, hiring manager, department, and domain.
    Paginated with max 50 per page.
    
    Requirements: 5.4
    """
    service = RequisitionService(db)
    
    offset = (page - 1) * page_size
    
    requisitions, total_count = await service.list_requisitions(
        org_id=principal.organization_id,
        status=status,
        hiring_manager_user_id=hiring_manager_user_id,
        department=department,
        domain=domain,
        offset=offset,
        limit=page_size,
    )
    
    return {
        "items": [RequisitionResponse.from_orm(r) for r in requisitions],
        "total": total_count,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{requisition_id}",
    response_model=RequisitionResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_requisition",
    summary="Retrieve a job requisition by ID",
    description="Retrieve a specific job requisition by ID. Requires Recruiter, Administrator, or HiringManager role.",
    responses={
        200: {"description": "Requisition retrieved successfully", "model": RequisitionResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Requisition not found"},
    },
)
async def get_requisition(
    requisition_id: UUID,
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> RequisitionResponse:
    """
    Retrieve a job requisition by ID.
    
    Requirements: 5.4
    """
    service = RequisitionService(db)
    
    requisition = await service.get_requisition(requisition_id, principal.organization_id)
    
    return RequisitionResponse.from_orm(requisition)


@router.patch(
    "/{requisition_id}",
    response_model=RequisitionResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_requisition",
    summary="Update a job requisition",
    description="Update a job requisition status with FSM validation. Requires Recruiter or Administrator role.",
    responses={
        200: {"description": "Requisition updated successfully", "model": RequisitionResponse},
        400: {"description": "Invalid status transition"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Requisition not found"},
        409: {"description": "Conflict: Resource has been modified by another request"},
    },
)
async def update_requisition(
    requisition_id: UUID,
    request: RequisitionUpdate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> RequisitionResponse:
    """
    Update a job requisition status.
    
    Validates status transition against VALID_REQUISITION_TRANSITIONS.
    Publishes requisition_status_changed event on successful transition.
    
    Requirements: 5.2, 5.6
    """
    service = RequisitionService(db)
    
    if request.status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status is required for updating a requisition",
        )
    
    requisition = await service.transition_status(
        requisition_id=requisition_id,
        org_id=principal.organization_id,
        new_status=request.status,
        version=request.version,
        updated_by=principal.user_id,
        background_tasks=background_tasks,
    )
    
    await db.commit()
    return RequisitionResponse.from_orm(requisition)


@router.post(
    "/{requisition_id}/candidates",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    operation_id="associate_candidate_to_requisition",
    summary="Associate a candidate with a requisition",
    description="Associate a candidate with a job requisition. Validates requisition status is OPEN and candidate status is ACTIVE or INTERVIEWING. Requires Recruiter or Administrator role. Returns 201 Created.",
    responses={
        201: {"description": "Candidate associated successfully"},
        400: {"description": "Invalid candidate or requisition status"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Requisition or candidate not found"},
        409: {"description": "Conflict: Candidate already associated with this requisition"},
    },
)
async def associate_candidate(
    requisition_id: UUID,
    request: CandidateAssociationRequest,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Associate a candidate with a job requisition.
    
    Validates:
    - Requisition status is OPEN
    - Candidate status is ACTIVE or INTERVIEWING
    - No duplicate association exists
    
    Requirements: 5.3
    """
    service = RequisitionService(db)
    
    candidate_requisition = await service.associate_candidate(
        requisition_id=requisition_id,
        candidate_id=request.candidate_id,
        org_id=principal.organization_id,
        created_by=principal.user_id,
    )
    
    await db.commit()
    
    return {
        "candidate_requisition_id": str(candidate_requisition.candidate_requisition_id),
        "candidate_id": str(candidate_requisition.candidate_id),
        "job_requisition_id": str(candidate_requisition.job_requisition_id),
        "created_at": candidate_requisition.created_at.isoformat() if candidate_requisition.created_at else None,
    }


@router.post(
    "/{requisition_id}/required-skills",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    operation_id="add_required_skill",
    summary="Add a required skill to a requisition",
    description="Add a required skill with proficiency rank and weight to a job requisition. Requires Recruiter or Administrator role. Returns 201 Created.",
    responses={
        201: {"description": "Required skill added successfully"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Requisition or skill not found"},
        409: {"description": "Conflict: Skill already required for this requisition"},
        422: {"description": "Unprocessable Entity: Invalid proficiency rank (1-5) or weight (1-10)"},
    },
)
async def add_required_skill(
    requisition_id: UUID,
    request: RequiredSkillCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Add a required skill to a job requisition.
    
    Validates:
    - proficiency_rank is 1-5
    - weight is 1-10
    - No duplicate skill requirement exists
    
    Requirements: 5.5
    """
    service = RequisitionService(db)
    
    required_skill = await service.add_required_skill(
        requisition_id=requisition_id,
        skill_id=request.skill_id,
        org_id=principal.organization_id,
        required_proficiency_rank=request.required_proficiency_rank,
        weight=request.weight,
        created_by=principal.user_id,
    )
    
    await db.commit()
    
    return {
        "requisition_required_skill_id": str(required_skill.requisition_required_skill_id),
        "job_requisition_id": str(required_skill.job_requisition_id),
        "skill_id": str(required_skill.skill_id),
        "required_proficiency_rank": required_skill.required_proficiency_rank,
        "weight": required_skill.weight,
        "created_at": required_skill.created_at.isoformat() if required_skill.created_at else None,
    }
