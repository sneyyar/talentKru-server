"""
Invitation router for user account setup.

Endpoints:
- POST /auth/invitation/accept: Accept an invitation and activate account
- POST /auth/invitation/resend: Resend an invitation to a user

Requirements: 9.3, 9.6, 9.9
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.invitations.schemas import (
    InvitationAcceptRequest,
    InvitationResendRequest,
)
from app.modules.invitations.service import InvitationService
from app.modules.users.schemas import UserResponse

router = APIRouter(tags=["invitations"])


@router.post(
    "/auth/invitation/accept",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept invitation and activate account",
    description=(
        "Accept an invitation token and set the initial password. "
        "Activates the user account."
    ),
)
async def accept_invitation(
    request: InvitationAcceptRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Accept an invitation and activate the user account.
    
    Requirements: 9.3, 9.8, 9.9
    """
    service = InvitationService(db)
    
    try:
        user = await service.accept_invitation(request.token, request.password)
        await db.commit()
        return UserResponse.from_orm(user)
    except ValueError as e:
        error_msg = str(e)
        if "policy" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_msg,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )


@router.post(
    "/auth/invitation/resend",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Resend invitation",
    description="Resend an invitation to a user in PendingInvitation status.",
)
async def resend_invitation(
    request: InvitationResendRequest,
    principal: Principal = Depends(require_role("Administrator", "SuperAdministrator")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Resend an invitation to a user.
    
    Requirements: 9.6
    """
    service = InvitationService(db)
    
    try:
        await service.resend_invitation(
            request.user_id, principal.organization_id, principal.user_id
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
