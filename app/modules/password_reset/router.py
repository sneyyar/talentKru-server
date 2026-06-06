"""
Password reset router for password recovery.

Endpoints:
- POST /auth/password-reset/request: Request a password reset
- POST /auth/password-reset/confirm: Confirm password reset with new password

Requirements: 10.1, 10.8, 10.9, 10.11
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.modules.password_reset.schemas import (
    PasswordResetConfirm,
    PasswordResetRequest,
)
from app.modules.password_reset.service import PasswordResetService
from app.modules.users.schemas import UserResponse

router = APIRouter(tags=["password-reset"])


@router.post(
    "/auth/password-reset/request",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description=(
        "Request a password reset. Always returns 200 regardless of whether "
        "the email exists (no email disclosure). Rate-limited to 3 requests "
        "per 10 minutes per IP address."
    ),
)
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Request a password reset.
    
    Public endpoint (no JWT required). Always returns 200 OK regardless of whether
    the email exists in the system, to prevent email enumeration attacks.
    
    If a user with the provided email exists and has status Active, a password
    reset token is generated and sent to their email address. Otherwise, no email
    is sent but the response is still 200 OK.
    
    Rate-limited to 3 requests per 10 minutes per source IP address.
    
    Requirements: 10.1, 10.2, 10.7, 10.8
    """
    service = PasswordResetService(db)
    
    # Request reset (always returns silently, no email disclosure)
    # Note: org_id determination would come from request context/tenant header in production
    # For now, we search across all organizations (or use a placeholder)
    await service.request_reset(request.email)
    
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post(
    "/auth/password-reset/confirm",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset",
    description=(
        "Confirm a password reset with a new password. Rate-limited to 5 attempts "
        "per 10 minutes per IP address."
    ),
)
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Confirm a password reset and update the user's password.
    
    Public endpoint (no JWT required). Accepts a password reset token and a new
    password. Validates the token (must be valid, non-expired, and unused) and
    the password (must meet policy requirements and not match last 5 passwords).
    
    On success:
    - Updates the user's password
    - Marks the reset token as used
    - Revokes all active refresh tokens for the user (forcing re-authentication)
    - Returns the updated user entity
    
    On failure:
    - Returns 400 Bad Request if token is invalid/expired/used (without revealing which)
    - Returns 422 Unprocessable Entity if password violates policy (token remains unused)
    
    Rate-limited to 5 attempts per 10 minutes per source IP address.
    
    Requirements: 10.3, 10.4, 10.5, 10.6, 10.9
    """
    service = PasswordResetService(db)
    
    try:
        user = await service.confirm_reset(request.token, request.new_password)
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
