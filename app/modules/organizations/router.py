"""
Organization REST API router.

Exposes CRUD endpoints for managing tenant organizations. All endpoints are
restricted to the SuperAdministrator role and include full OpenAPI metadata
for AI agent compatibility (Requirements 2.6, 5.1, 6.4).

Requirements: 2.6, 5.1, 6.4
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal, require_super_admin
from app.modules.organizations.schemas import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.modules.organizations.service import (
    create_organization,
    get_organization,
    list_organizations,
    update_organization,
)

router = APIRouter(tags=["organizations"])


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=201,
    operation_id="create_organization",
    summary="Create a new organization",
    description=(
        "Creates a new tenant organization. Restricted to SuperAdministrator role. "
        "Slug must be unique across all organizations."
    ),
    dependencies=[Depends(require_super_admin)],
)
async def create_organization_endpoint(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Create a new organization and return the persisted record."""
    org = await create_organization(data, db)
    return OrganizationResponse.model_validate(org)


@router.get(
    "/organizations",
    response_model=list[OrganizationResponse],
    operation_id="list_organizations",
    summary="List all organizations",
    description=(
        "Returns all active (non-deleted) organizations. "
        "Restricted to SuperAdministrator role."
    ),
    dependencies=[Depends(require_super_admin)],
)
async def list_organizations_endpoint(
    db: AsyncSession = Depends(get_db_session),
) -> list[OrganizationResponse]:
    """Return all active organizations."""
    orgs = await list_organizations(db)
    return [OrganizationResponse.model_validate(org) for org in orgs]


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    operation_id="get_organization",
    summary="Get organization by ID",
    description=(
        "Returns a single active organization by its UUID. "
        "Restricted to SuperAdministrator role."
    ),
    dependencies=[Depends(require_super_admin)],
)
async def get_organization_endpoint(
    org_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Retrieve a single organization by its UUID."""
    org = await get_organization(org_id, db)
    return OrganizationResponse.model_validate(org)


@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    operation_id="update_organization",
    summary="Update an organization",
    description=(
        "Partially updates an organization. Requires current version for optimistic "
        "locking. Restricted to SuperAdministrator role."
    ),
    dependencies=[Depends(require_super_admin)],
)
async def update_organization_endpoint(
    org_id: UUID,
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Apply a partial update to an existing organization."""
    org = await update_organization(org_id, data, db)
    return OrganizationResponse.model_validate(org)
