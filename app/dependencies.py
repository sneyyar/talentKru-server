"""
Shared FastAPI dependencies for authentication, authorization, and multi-tenancy.

Provides:
- Principal: dataclass holding the authenticated user's identity
- get_current_principal(): reads the principal from request.state (set by auth middleware)
- require_super_admin(): dependency that enforces the SuperAdministrator role
- get_org_scoped_query(): returns a SELECT pre-filtered by organization_id and soft-delete
"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Principal dataclass
# ---------------------------------------------------------------------------


@dataclass
class Principal:
    """Represents the authenticated caller extracted from the JWT."""

    user_id: UUID
    organization_id: UUID
    role: str
    roles: list[str] | None = None  # List of all roles
    jti: str | None = None  # JWT ID for revocation
    obo_by: str | None = None  # SuperAdmin user ID if on-behalf-of


# ---------------------------------------------------------------------------
# Authentication dependency
# ---------------------------------------------------------------------------


async def get_current_principal(request: Request) -> Principal:
    """
    JWT stub dependency — returns a principal from request state.

    Full JWT validation is implemented in the auth middleware
    (``app/middleware/auth.py``).  That middleware validates the token and
    stores the resulting ``Principal`` on ``request.state.principal`` before
    the route handler is invoked.

    If ``request.state.principal`` is not set (e.g., the auth middleware has
    not run or the token was absent/invalid), this dependency raises
    ``HTTP 401 Unauthorized``.
    """
    if hasattr(request.state, "principal"):
        return request.state.principal

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


# ---------------------------------------------------------------------------
# Authorization dependency
# ---------------------------------------------------------------------------


async def require_super_admin(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """
    Dependency that requires the caller to hold the SuperAdministrator role.

    Raises ``HTTP 403 Forbidden`` for any other role.  Use this on
    organization-management endpoints that must bypass the per-org data
    isolation filter (Requirements 2.5, 2.6).
    """
    if principal.role != "SuperAdministrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this resource is forbidden",
        )
    return principal


# ---------------------------------------------------------------------------
# Multi-tenancy query helper
# ---------------------------------------------------------------------------


async def get_org_scoped_query(
    model_class,
    organization_id: UUID,
    db: AsyncSession,  # noqa: ARG001 — reserved for future shard routing
):
    """
    Return a SELECT statement pre-filtered by ``organization_id`` and soft-delete.

    Every service method that queries tenant-owned data should call this helper
    instead of constructing raw ``select()`` statements, ensuring that:

    1. Results are always scoped to the caller's organization (Requirement 2.4).
    2. Soft-deleted rows (``deleted_at IS NOT NULL``) are never returned
       (design principle: soft-delete only).

    SuperAdministrators bypass this filter on organization-management endpoints
    by using a separate query path that does not call this helper.

    Args:
        model_class: The SQLAlchemy ORM model class to query.
        organization_id: The UUID of the organization whose data is requested.
        db: The current async database session (reserved for future shard routing).

    Returns:
        A ``sqlalchemy.sql.Select`` statement with ``organization_id`` and
        ``deleted_at IS NULL`` filters applied.
    """
    stmt = (
        select(model_class)
        .where(model_class.organization_id == organization_id)
        .where(model_class.deleted_at.is_(None))
    )
    return stmt
