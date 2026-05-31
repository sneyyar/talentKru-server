"""
JWT dependencies for authentication and authorization.

Provides:
- get_current_principal: Validates JWT and returns Principal
- require_role: Dependency factory for role-based authorization
- require_privilege: Dependency factory for privilege-based authorization

Requirements: 3.5, 3.6, 4.4, 5.3, 5.6, 6.4
"""

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.service import RevocationCache
from app.modules.users.models import User
from app.crypto import hash_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")


def get_revocation_cache() -> RevocationCache:
    """Get the global revocation cache instance."""
    # This will be set by the router
    from app.modules.auth.router import get_revocation_cache as router_get_cache
    return router_get_cache()


async def get_current_principal(
    token: str = Depends(oauth2_scheme),
    revocation_cache: RevocationCache = Depends(get_revocation_cache),
    db: AsyncSession = Depends(get_db_session),
) -> Principal:
    """
    Validate JWT and return the authenticated principal.
    
    Decodes the JWT with JWT_SIGNING_KEY, checks the exp claim,
    verifies the jti is not in the revocation cache, and returns
    a Principal with the user's identity and roles.
    
    Args:
        token: JWT token from Authorization header
        revocation_cache: RevocationCache for checking revoked tokens
        db: AsyncSession for database access (to look up user_id from email)
        
    Returns:
        Principal with user identity and roles
        
    Raises:
        HTTPException: If token is invalid, expired, or revoked
        
    Requirements: 3.5, 3.6, 4.4
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, settings.JWT_SIGNING_KEY, algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    # Check if token is revoked by jti
    jti = payload.get("jti")
    if jti and revocation_cache.is_revoked(jti):
        raise credentials_exception
    
    # Extract claims
    sub = payload.get("sub")  # email address
    org_id_str = payload.get("org_id")
    roles = payload.get("roles", [])
    obo_by = payload.get("obo_by")
    
    if not sub or not org_id_str:
        raise credentials_exception
    
    try:
        org_id = UUID(org_id_str)
    except (ValueError, TypeError):
        raise credentials_exception
    
    # Look up user_id from email and org_id
    # The email is stored encrypted, so we need to search by email_hash
    from app.crypto import hash_email
    email_hash = hash_email(sub)
    
    stmt = select(User).where(
        User.organization_id == org_id,
        User.email_hash == email_hash,
        User.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()  # type: ignore[arg-type]
    
    if not user:
        raise credentials_exception
    
    # Use the first role as the primary role
    primary_role = roles[0] if roles else "User"
    
    return Principal(
        user_id=user.user_id,
        organization_id=org_id,
        role=primary_role,
        roles=roles,
        jti=jti,
        obo_by=obo_by,
    )


def require_role(*required_roles: str):
    """
    Dependency factory for role-based authorization.
    
    Returns a dependency that checks if the principal holds at least
    one of the required roles. Raises 403 Forbidden if not.
    
    Args:
        required_roles: One or more role names that are allowed
        
    Returns:
        Dependency function that checks roles
        
    Requirements: 5.3, 5.6
    """
    async def _check(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if not principal.roles or not any(
            r in principal.roles for r in required_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return principal
    
    return _check


def require_privilege(privilege_name: str):
    """
    Dependency factory for privilege-based authorization.
    
    Returns a dependency that checks if the principal holds at least
    one role that has been assigned the specified privilege.
    Performs a database lookup of the role→privilege mapping.
    Raises 403 Forbidden if not found.
    
    Args:
        privilege_name: The privilege name to check (snake_case identifier)
        
    Returns:
        Dependency function that checks privileges
        
    Requirements: 6.4
    """
    async def _check(
        principal: Principal = Depends(get_current_principal),
        db: AsyncSession = Depends(get_db_session),
    ) -> Principal:
        # Check if any of the user's roles have this privilege
        from app.modules.rbac.models import RolePrivilege, Privilege
        
        if not principal.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privilege",
            )
        
        # Query for privilege: find any RolePrivilege where the role is in
        # principal.roles and the privilege name matches
        stmt = (
            select(RolePrivilege)
            .join(Privilege)
            .where(
                RolePrivilege.role_name.in_(principal.roles),
                Privilege.name == privilege_name,
                RolePrivilege.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        has_privilege = result.scalar_one_or_none() is not None
        
        if not has_privilege:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privilege",
            )
        
        return principal
    
    return _check
