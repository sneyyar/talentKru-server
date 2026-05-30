"""
Authentication router for JWT issuance, token refresh, and impersonation.

Endpoints:
- POST /token: Authenticate with email/password, return access + refresh tokens
- POST /token/refresh: Refresh an access token using a refresh token
- POST /admin/impersonate: SuperAdmin impersonation (on-behalf-of)

Requirements: 3.1, 3.2, 3.9, 4.2, 4.3, 2.1, 2.5
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.modules.auth.schemas import (
    ImpersonateRequest,
    RefreshRequest,
    TokenResponse,
)
from app.modules.auth.service import (
    AuthService,
    AuthenticationError,
    RevocationCache,
)
from app.modules.auth.dependencies import require_role
from app.modules.users.models import User
from app.dependencies import Principal, get_current_principal

router = APIRouter(tags=["auth"])

# Global revocation cache instance
_revocation_cache: RevocationCache | None = None


def get_revocation_cache() -> RevocationCache:
    """Get the global revocation cache instance."""
    global _revocation_cache
    if _revocation_cache is None:
        _revocation_cache = RevocationCache()
    return _revocation_cache


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email and password",
    description=(
        "Authenticate a user with email and password. "
        "Returns access token (60-min TTL) and refresh token (7-day TTL). "
        "Accepts application/x-www-form-urlencoded format."
    ),
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
    revocation_cache: RevocationCache = Depends(get_revocation_cache),
) -> TokenResponse:
    """
    Authenticate a user and return JWT tokens.
    
    Accepts email and password via application/x-www-form-urlencoded.
    Returns 422 if email or password is missing.
    Returns 401 if credentials are invalid (no field disclosure).
    
    Requirements: 3.1, 3.2, 3.9
    """
    # Extract email and password from form data
    # OAuth2PasswordRequestForm uses 'username' field for the username/email
    email = form_data.username
    password = form_data.password
    
    # Validate required fields
    if not email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "loc": ["body", "username"],
                    "msg": "Field required",
                    "type": "value_error.missing",
                }
            ],
        )
    
    if not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "loc": ["body", "password"],
                    "msg": "Field required",
                    "type": "value_error.missing",
                }
            ],
        )
    
    # For MVP: search across all organizations for the email
    # In production, this would come from a tenant header or request context
    # We'll try to find the user by email across all orgs
    from sqlalchemy import select
    import hashlib
    
    email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
    
    # Find the user by email_hash (searches across all orgs)
    stmt = select(User).where(User.email_hash == email_hash)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        # User not found - return 401 without disclosing whether email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    org_id = user.organization_id
    
    try:
        service = AuthService(db, revocation_cache)
        access_token, refresh_token = await service.authenticate(
            email, password, org_id
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


@router.post(
    "/token/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh an access token",
    description="Use a refresh token to obtain a new access token.",
)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
    revocation_cache: RevocationCache = Depends(get_revocation_cache),
) -> TokenResponse:
    """
    Refresh an access token using a refresh token.
    
    Requirements: 4.2, 4.3
    """
    service = AuthService(db, revocation_cache)
    
    try:
        access_token, new_refresh_token = await service.refresh(
            request.refresh_token
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@router.post(
    "/admin/impersonate",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="SuperAdmin impersonation",
    description=(
        "SuperAdmin impersonates an Administrator in a target organization. "
        "Returns an on-behalf-of JWT with obo_by claim."
    ),
)
async def impersonate(
    request: ImpersonateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
    revocation_cache: RevocationCache = Depends(get_revocation_cache),
    _: Principal = Depends(require_role("SuperAdministrator")),
) -> TokenResponse:
    """
    SuperAdmin impersonation endpoint.
    
    Requirements: 2.1, 2.5
    """
    service = AuthService(db, revocation_cache)
    
    try:
        token = await service.impersonate(
            principal,
            request.target_org_id,
            request.target_user_id,
        )
        
        return TokenResponse(
            access_token=token,
            refresh_token="",  # No refresh token for OBO sessions
            token_type="bearer",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
