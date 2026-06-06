"""Privacy management router.

Endpoints:
- GET /api/v1/dsar — require_role("Administrator", "HRManager"); paginated list
- PATCH /api/v1/dsar/{dsar_id} — require_role("Administrator", "HRManager"); process Access or Erasure based on request_type
- POST /api/v1/dsar/{dsar_id}/deny — require_role("Administrator", "HRManager"); requires denial_reason
- GET /api/v1/privacy/retention-policy — require_role("Administrator")
- PATCH /api/v1/privacy/retention-policy — require_role("Administrator")

Requirements: 6.2, 6.3, 6.6, 6.7
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import require_role
from app.modules.privacy.models import DataSubjectAccessRequest, DSARRequestType
from app.modules.privacy.schemas import (
    DSARManageResponse,
    DSARDenyRequest,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
)
from app.modules.privacy.service import PrivacyService
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["privacy"])


@router.get(
    "/dsar",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="list_dsars",
    summary="List Data Subject Access Requests",
    description="List all DSARs in the organization with optional status filter and pagination. Requires Administrator or HRManager role. Returns paginated list with total count.",
    responses={
        200: {"description": "DSARs retrieved successfully"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_dsars(
    status: str | None = Query(None, description="Filter by DSAR status (PENDING, COMPLETED, DENIED)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=50, description="Results per page (max 50)"),
    principal: Principal = Depends(require_role("Administrator", "HRManager")),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List Data Subject Access Requests.
    
    Supports filtering by status and pagination.
    
    Requirements: 6.6
    """
    service = PrivacyService(db)
    
    offset = (page - 1) * page_size
    
    dsars, total_count = await service.list_dsars(
        org_id=principal.organization_id,
        status_filter=status,
        page=page,
        page_size=page_size,
    )
    
    return {
        "items": [DSARManageResponse.from_orm(d) for d in dsars],
        "total": total_count,
        "page": page,
        "page_size": page_size,
    }


@router.patch(
    "/dsar/{dsar_id}",
    response_model=DSARManageResponse,
    status_code=status.HTTP_200_OK,
    operation_id="process_dsar",
    summary="Process a Data Subject Access Request",
    description="Process a DSAR by executing Access or Erasure workflow based on request_type. Requires Administrator or HRManager role.",
    responses={
        200: {"description": "DSAR processed successfully", "model": DSARManageResponse},
        400: {"description": "Invalid request type or DSAR status"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: DSAR not found"},
    },
)
async def process_dsar(
    dsar_id: UUID,
    principal: Principal = Depends(require_role("Administrator", "HRManager")),
    db: AsyncSession = Depends(get_db_session),
) -> DSARManageResponse:
    """
    Process a Data Subject Access Request.
    
    Executes Access or Erasure workflow based on request_type.
    - Access: Compiles candidate profile, job history, skills, questionnaire responses, availability slots, and journey metadata
    - Erasure: Hard-deletes Resume and Candidate records, anonymizes AuditLog entries
    
    Requirements: 6.2, 6.3
    """
    service = PrivacyService(db)
    
    # Fetch DSAR
    result = await db.execute(
        select(DataSubjectAccessRequest).where(
            and_(
                DataSubjectAccessRequest.dsar_id == dsar_id,
                DataSubjectAccessRequest.organization_id == principal.organization_id,
                DataSubjectAccessRequest.deleted_at.is_(None),
            )
        )
    )
    dsar = result.scalar_one_or_none()
    
    if not dsar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DSAR not found",
        )
    
    # Process based on request type
    if dsar.request_type == DSARRequestType.ACCESS.value:
        await service.process_access_dsar(dsar)
    elif dsar.request_type == DSARRequestType.ERASURE.value:
        await service.process_erasure_dsar(dsar)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid DSAR request type",
        )
    
    return DSARManageResponse.from_orm(dsar)


@router.post(
    "/dsar/{dsar_id}/deny",
    response_model=DSARManageResponse,
    status_code=status.HTTP_200_OK,
    operation_id="deny_dsar",
    summary="Deny a Data Subject Access Request",
    description="Deny a DSAR with a reason. Requires Administrator or HRManager role. Denial reason must be at least 10 characters.",
    responses={
        200: {"description": "DSAR denied successfully", "model": DSARManageResponse},
        400: {"description": "Invalid denial reason (must be at least 10 characters)"},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: DSAR not found"},
    },
)
async def deny_dsar(
    dsar_id: UUID,
    request: DSARDenyRequest,
    principal: Principal = Depends(require_role("Administrator", "HRManager")),
    db: AsyncSession = Depends(get_db_session),
) -> DSARManageResponse:
    """
    Deny a Data Subject Access Request.
    
    Validates denial_reason is at least 10 characters.
    Writes audit log entry with denied_by user.
    
    Requirements: 6.7
    """
    service = PrivacyService(db)
    
    # Fetch DSAR
    result = await db.execute(
        select(DataSubjectAccessRequest).where(
            and_(
                DataSubjectAccessRequest.dsar_id == dsar_id,
                DataSubjectAccessRequest.organization_id == principal.organization_id,
                DataSubjectAccessRequest.deleted_at.is_(None),
            )
        )
    )
    dsar = result.scalar_one_or_none()
    
    if not dsar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DSAR not found",
        )
    
    await service.deny_dsar(
        dsar=dsar,
        denial_reason=request.denial_reason,
        denied_by=principal.user_id,
    )
    
    return DSARManageResponse.from_orm(dsar)


@router.get(
    "/privacy/retention-policy",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_retention_policy",
    summary="Get organization retention policy",
    description="Retrieve the data retention policy for the organization. Requires Administrator role.",
    responses={
        200: {"description": "Retention policy retrieved successfully", "model": RetentionPolicyResponse},
        403: {"description": "Forbidden: User does not have Administrator role"},
        404: {"description": "Not Found: Retention policy not found"},
    },
)
async def get_retention_policy(
    principal: Principal = Depends(require_role("Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> RetentionPolicyResponse:
    """
    Get organization retention policy.
    
    Requirements: 6.4
    """
    service = PrivacyService(db)
    
    policy = await service.get_retention_policy(principal.organization_id)
    
    return RetentionPolicyResponse.from_orm(policy)


@router.patch(
    "/privacy/retention-policy",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_retention_policy",
    summary="Update organization retention policy",
    description="Update the data retention policy for the organization. Requires Administrator role.",
    responses={
        200: {"description": "Retention policy updated successfully", "model": RetentionPolicyResponse},
        403: {"description": "Forbidden: User does not have Administrator role"},
        404: {"description": "Not Found: Retention policy not found"},
    },
)
async def update_retention_policy(
    request: RetentionPolicyUpdate,
    principal: Principal = Depends(require_role("Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> RetentionPolicyResponse:
    """
    Update organization retention policy.
    
    Requirements: 6.4
    """
    service = PrivacyService(db)
    
    policy = await service.update_retention_policy(
        org_id=principal.organization_id,
        candidate_data_retention_days=request.candidate_data_retention_days,
        resume_retention_days=request.resume_retention_days,
        audit_log_retention_days=request.audit_log_retention_days,
        updated_by=principal.user_id,
    )
    
    return RetentionPolicyResponse.from_orm(policy)
