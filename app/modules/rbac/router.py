"""
RBAC router for role and privilege management.

Endpoints:
- GET /roles: List all roles
- POST /roles/{role_name}/users/{user_id}: Assign role to user
- DELETE /roles/{role_name}/users/{user_id}: Remove role from user
- GET /roles/{role_name}/privileges: Get privileges for a role
- GET /privileges: List all privileges
- POST /roles/{role_name}/privileges: Assign privilege to role
- DELETE /roles/{role_name}/privileges/{privilege_id}: Remove privilege from role

Requirements: 5.1, 5.6, 6.5, 6.6
"""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.rbac.schemas import (
    AssignPrivilegeRequest,
    PrivilegeResponse,
    RolePrivilegeResponse,
    RoleResponse,
)
from app.modules.rbac.service import RBACService

router = APIRouter(tags=["rbac"])


@router.get(
    "/roles",
    response_model=list[RoleResponse],
    status_code=status.HTTP_200_OK,
    summary="List all roles",
    description="List all available roles in the system.",
)
async def list_roles(
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> list[RoleResponse]:
    """
    List all roles.
    
    Requirements: 5.1, 5.6
    """
    service = RBACService(db)
    roles = await service.list_roles()
    return [RoleResponse.from_orm(r) for r in roles]


@router.post(
    "/roles/{role_name}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign role to user",
    description="Assign a role to a user.",
)
async def assign_role(
    role_name: str,
    user_id: UUID,
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Assign a role to a user.
    
    Requirements: 5.1, 5.6, 7.3
    """
    service = RBACService(db)
    
    try:
        await service.assign_role(
            user_id,
            role_name,
            principal.user_id,
            obo_by=UUID(principal.obo_by) if principal.obo_by else None,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/roles/{role_name}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove role from user",
    description="Remove a role from a user.",
)
async def remove_role(
    role_name: str,
    user_id: UUID,
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove a role from a user.
    
    Requirements: 5.1, 5.6, 7.3
    """
    service = RBACService(db)
    
    try:
        await service.remove_role(
            user_id,
            role_name,
            principal.user_id,
            obo_by=UUID(principal.obo_by) if principal.obo_by else None,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/privileges",
    response_model=list[PrivilegeResponse],
    status_code=status.HTTP_200_OK,
    summary="List all privileges",
    description="List all available privileges in the system.",
)
async def list_privileges(
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> list[PrivilegeResponse]:
    """
    List all privileges.
    
    Requirements: 6.1, 6.5
    """
    service = RBACService(db)
    privileges = await service.list_privileges()
    return [PrivilegeResponse.from_orm(p) for p in privileges]


@router.get(
    "/roles/{role_name}/privileges",
    response_model=list[RolePrivilegeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get privileges for a role",
    description="Get all privileges assigned to a role.",
)
async def get_role_privileges(
    role_name: str,
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> list[RolePrivilegeResponse]:
    """
    Get privileges for a role.
    
    Requirements: 6.1, 6.5
    """
    service = RBACService(db)
    role_privileges = await service.get_role_privileges(role_name)
    return [RolePrivilegeResponse.from_orm(rp) for rp in role_privileges]


@router.post(
    "/roles/{role_name}/privileges",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign privilege to role",
    description="Assign a privilege to a role (SuperAdmin only).",
)
async def assign_privilege(
    role_name: str,
    request: AssignPrivilegeRequest = Body(...),
    principal: Principal = Depends(require_role("SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Assign a privilege to a role.
    
    Requirements: 6.1, 6.5, 6.6, 7.3
    """
    service = RBACService(db)
    
    try:
        await service.assign_privilege(
            role_name,
            request.privilege_id,
            principal.user_id,
            obo_by=UUID(principal.obo_by) if principal.obo_by else None,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/roles/{role_name}/privileges/{privilege_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove privilege from role",
    description="Remove a privilege from a role (SuperAdmin only).",
)
async def remove_privilege(
    role_name: str,
    privilege_id: UUID,
    principal: Principal = Depends(require_role("SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Remove a privilege from a role.
    
    Requirements: 6.1, 6.5, 6.6, 7.3
    """
    service = RBACService(db)
    
    try:
        await service.remove_privilege(
            role_name,
            privilege_id,
            principal.user_id,
            obo_by=UUID(principal.obo_by) if principal.obo_by else None,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
