"""Portal router.

Endpoints:
- POST /api/v1/portal/dsar — authenticated candidates only (any role); returns 201 with dsar_id and status=Pending

Requirements: 6.1
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal
from app.modules.portal.schemas import DSARCreateRequest, DSARResponse
from app.modules.portal.service import PortalService
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/portal", tags=["portal"])


@router.post(
    "/dsar",
    response_model=DSARResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_dsar",
    summary="Create a Data Subject Access Request",
    description="Create a new Data Subject Access Request (DSAR) for the authenticated candidate. Endpoint remains permanently accessible to all authenticated candidates. Returns 201 Created with DSAR ID and status=Pending.",
    responses={
        201: {"description": "DSAR created successfully", "model": DSARResponse},
        400: {"description": "Invalid request data"},
        401: {"description": "Unauthorized: Valid JWT required"},
    },
)
async def create_dsar(
    request: DSARCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> DSARResponse:
    """
    Create a Data Subject Access Request.
    
    Endpoint is permanently accessible to all authenticated candidates.
    No role restriction beyond valid JWT.
    
    Requirements: 6.1
    """
    service = PortalService(db)
    
    dsar = await service.create_dsar(
        candidate_id=principal.user_id,
        org_id=principal.organization_id,
        request_type=request.request_type,
    )
    
    await db.commit()
    
    logger.info(
        "dsar_endpoint_success",
        dsar_id=str(dsar.dsar_id),
        candidate_id=str(principal.user_id),
        organization_id=str(principal.organization_id),
    )
    
    return DSARResponse(
        dsar_id=dsar.dsar_id,
        status=dsar.status.value,
        requested_at=dsar.requested_at,
    )
