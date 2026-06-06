"""
User management router for CRUD operations and session management.

Endpoints:
- GET /users: List users (paginated)
- POST /users: Create a new user
- PATCH /users/{user_id}: Update user information
- DELETE /admin/users/{user_id}/sessions: Revoke all user sessions

Requirements: 1.6, 4.6
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.users.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserListResponse,
)
from app.modules.users.service import (
    UserService,
    UserAlreadyExistsError,
    UserNotFoundError,
)

router = APIRouter(tags=["users"])


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List users",
    description="List users in the organization with pagination.",
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        20, ge=1, le=100, description="Number of users per page"
    ),
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> UserListResponse:
    """
    List users in the organization.
    
    Requirements: 1.6
    """
    service = UserService(db)
    users, total_count = await service.list_users(
        principal.organization_id, page, page_size
    )
    
    return UserListResponse(
        items=[UserResponse.from_orm(u) for u in users],
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Create a new user in the organization with PendingInvitation status.",
)
async def create_user(
    request: UserCreate,
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Create a new user.
    
    Requirements: 1.1, 1.2, 1.3, 7.3
    """
    service = UserService(db)
    
    try:
        user = await service.create_user(
            email=request.email,
            given_name=request.given_name,
            last_name=request.last_name,
            org_id=principal.organization_id,
            manager_user_id=request.manager_user_id,
            locale=request.locale or "en-US",
            actor_id=principal.user_id,
            obo_by=UUID(principal.obo_by) if principal.obo_by else None,
        )
        return UserResponse.from_orm(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists in the organization",
        )


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user information",
    description="Update user information (name, locale, manager).",
)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Update user information.
    
    Requirements: 1.4, 1.6, 7.3
    """
    service = UserService(db)
    
    try:
        user = await service.update_user(
            user_id=user_id,
            org_id=principal.organization_id,
            given_name=request.given_name,
            last_name=request.last_name,
            locale=request.locale,
            manager_user_id=request.manager_user_id,
            actor_id=principal.user_id,
            obo_by=UUID(principal.obo_by) if principal.obo_by else None,
        )
        return UserResponse.from_orm(user)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.delete(
    "/admin/users/{user_id}/sessions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke all user sessions",
    description="Revoke all active sessions for a user.",
)
async def revoke_user_sessions(
    user_id: UUID,
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Revoke all active sessions for a user.
    
    Requirements: 4.6, 7.3
    """
    from app.modules.auth.service import AuthService, RevocationCache
    from app.modules.auth.router import get_revocation_cache
    from app.audit import write_audit_log
    from datetime import datetime, timezone
    
    service = UserService(db)
    
    # Verify user exists
    user = await service.get_user_by_id(user_id, principal.organization_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Revoke all tokens
    auth_service = AuthService(db, get_revocation_cache())
    await auth_service.revoke_all_user_tokens(user_id, reason="session_revocation")
    
    # Write audit log entry
    await write_audit_log(
        actor_id=principal.user_id,
        action="SessionRevoked",
        target_entity="User",
        target_id=user_id,
        org_id=principal.organization_id,
        changed_values={"reason": "session_revocation"},
        obo_by=principal.obo_by if hasattr(principal, 'obo_by') else None,
        timestamp=datetime.now(timezone.utc),
        db=db,
    )
