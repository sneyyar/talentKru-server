"""
Organization service layer.

Provides business logic for creating, retrieving, updating, and listing
Organization entities. Enforces slug uniqueness with a pre-write SELECT check
and applies shard_id=0 on creation.

Requirements: 2.1, 2.2, 2.6, 2.7
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organizations.models import Organization
from app.modules.organizations.schemas import OrganizationCreate, OrganizationUpdate


async def _check_slug_unique(
    db: AsyncSession, slug: str, exclude_id: UUID | None = None
) -> None:
    """Raise 409 if slug is already in use by another organization."""
    stmt = select(Organization).where(
        Organization.slug == slug,
        Organization.deleted_at.is_(None),
    )
    if exclude_id:
        stmt = stmt.where(Organization.organization_id != exclude_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "slug already in use", "field": "slug"},
        )


async def create_organization(data: OrganizationCreate, db: AsyncSession) -> Organization:
    """
    Create a new organization.

    Enforces slug uniqueness before insert and assigns shard_id=0 (Requirement 2.2).

    Args:
        data: Validated creation payload.
        db: Async database session.

    Returns:
        The newly created Organization ORM instance.

    Raises:
        HTTPException(409): If the slug is already in use.
    """
    await _check_slug_unique(db, data.slug)
    org = Organization(
        name=data.name,
        slug=data.slug,
        logo_url=data.logo_url,
        primary_color=data.primary_color,
        secondary_color=data.secondary_color,
        terms_url=data.terms_url,
        contact_name=data.contact_name,
        contact_email=str(data.contact_email) if data.contact_email else None,
        contact_phone=data.contact_phone,
        feature_flags=data.feature_flags,
        allowed_origins=data.allowed_origins,
        shard_id=0,
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


async def get_organization(org_id: UUID, db: AsyncSession) -> Organization:
    """
    Retrieve a single active organization by its primary key.

    Args:
        org_id: The UUID of the organization to retrieve.
        db: Async database session.

    Returns:
        The matching Organization ORM instance.

    Raises:
        HTTPException(404): If no active organization with the given ID exists.
    """
    stmt = select(Organization).where(
        Organization.organization_id == org_id,
        Organization.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    return org


async def list_organizations(db: AsyncSession) -> list[Organization]:
    """
    Return all active (non-deleted) organizations.

    Args:
        db: Async database session.

    Returns:
        List of active Organization ORM instances.
    """
    stmt = select(Organization).where(Organization.deleted_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_organization(
    org_id: UUID, data: OrganizationUpdate, db: AsyncSession
) -> Organization:
    """
    Apply a partial update to an existing organization.

    Enforces slug uniqueness when the slug is being changed. The ``version``
    field in the payload is used by SQLAlchemy's optimistic locking mechanism
    (VersionMixin / version_id_col) — a stale version will raise a
    StaleDataError which the route handler should surface as 409 Conflict.

    Args:
        org_id: The UUID of the organization to update.
        data: Validated update payload (all fields except ``version`` are optional).
        db: Async database session.

    Returns:
        The updated Organization ORM instance.

    Raises:
        HTTPException(404): If no active organization with the given ID exists.
        HTTPException(409): If the new slug is already in use by another org.
    """
    org = await get_organization(org_id, db)
    if data.slug and data.slug != org.slug:
        await _check_slug_unique(db, data.slug, exclude_id=org_id)

    # Apply updates for all explicitly provided fields, excluding version
    # (version is managed by SQLAlchemy's optimistic locking, not set manually)
    update_data = data.model_dump(exclude_unset=True, exclude={"version"})
    for field, value in update_data.items():
        # Always apply JSON/array fields even when None (explicit null is valid)
        if value is not None or field in ("feature_flags", "allowed_origins"):
            setattr(org, field, value)

    await db.flush()
    await db.refresh(org)
    return org
