"""
Organization Pydantic request/response schemas.

Defines the data shapes for creating, updating, and returning Organization
entities via the REST API. All fields include Field(description=...) for
OpenAPI documentation and AI agent compatibility (Requirement 5.2).

Requirements: 2.1, 5.2, 7.2
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrganizationCreate(BaseModel):
    """Request schema for creating a new organization."""

    name: str = Field(
        ...,
        max_length=128,
        description="Organization display name, max 128 characters",
    )
    slug: str = Field(
        ...,
        max_length=64,
        description="URL-safe unique identifier, lowercase alphanumeric and hyphens only",
    )
    logo_url: Optional[str] = Field(
        None,
        max_length=512,
        description="URL to the organization logo image",
    )
    primary_color: Optional[str] = Field(
        None,
        max_length=7,
        description="Primary brand color as hex code, e.g. #FF5733",
    )
    secondary_color: Optional[str] = Field(
        None,
        max_length=7,
        description="Secondary brand color as hex code, e.g. #33FF57",
    )
    terms_url: Optional[str] = Field(
        None,
        max_length=512,
        description="URL to the organization terms and conditions page",
    )
    contact_name: Optional[str] = Field(
        None,
        max_length=128,
        description="Primary contact person full name, max 128 characters",
    )
    contact_email: Optional[EmailStr] = Field(
        None,
        description="Primary contact email address in valid email format",
    )
    contact_phone: Optional[str] = Field(
        None,
        max_length=32,
        description="Primary contact phone number, max 32 characters",
    )
    feature_flags: dict = Field(
        default_factory=dict,
        description="Feature flag overrides as key-value boolean pairs",
    )
    allowed_origins: list[str] = Field(
        default_factory=list,
        description="List of allowed CORS origins for this organization, max 20 entries",
    )


class OrganizationUpdate(BaseModel):
    """Request schema for updating an existing organization.

    Requires the current version for optimistic locking (Requirement 7.2).
    All fields except version are optional to support partial updates.
    """

    version: int = Field(
        ...,
        description="Current version for optimistic locking, must match stored version",
    )
    name: Optional[str] = Field(
        None,
        max_length=128,
        description="Organization display name, max 128 characters",
    )
    slug: Optional[str] = Field(
        None,
        max_length=64,
        description="URL-safe unique identifier, lowercase alphanumeric and hyphens only",
    )
    logo_url: Optional[str] = Field(
        None,
        max_length=512,
        description="URL to the organization logo image",
    )
    primary_color: Optional[str] = Field(
        None,
        max_length=7,
        description="Primary brand color as hex code, e.g. #FF5733",
    )
    secondary_color: Optional[str] = Field(
        None,
        max_length=7,
        description="Secondary brand color as hex code, e.g. #33FF57",
    )
    terms_url: Optional[str] = Field(
        None,
        max_length=512,
        description="URL to the organization terms and conditions page",
    )
    contact_name: Optional[str] = Field(
        None,
        max_length=128,
        description="Primary contact person full name, max 128 characters",
    )
    contact_email: Optional[EmailStr] = Field(
        None,
        description="Primary contact email address in valid email format",
    )
    contact_phone: Optional[str] = Field(
        None,
        max_length=32,
        description="Primary contact phone number, max 32 characters",
    )
    feature_flags: Optional[dict] = Field(
        None,
        description="Feature flag overrides as key-value boolean pairs",
    )
    allowed_origins: Optional[list[str]] = Field(
        None,
        description="List of allowed CORS origins for this organization, max 20 entries",
    )


class OrganizationResponse(BaseModel):
    """Response schema for returning organization data.

    Includes all persisted fields, audit timestamps, and the current version
    for optimistic locking (Requirement 7.2). Supports ORM model hydration
    via from_attributes=True.
    """

    organization_id: UUID = Field(
        ...,
        description="Unique identifier for the organization as a UUID",
    )
    version: int = Field(
        ...,
        description="Current version for optimistic locking, increment on each update",
    )
    name: str = Field(
        ...,
        description="Organization display name, max 128 characters",
    )
    slug: str = Field(
        ...,
        description="URL-safe unique identifier, lowercase alphanumeric and hyphens only",
    )
    logo_url: Optional[str] = Field(
        None,
        description="URL to the organization logo image",
    )
    primary_color: Optional[str] = Field(
        None,
        description="Primary brand color as hex code, e.g. #FF5733",
    )
    secondary_color: Optional[str] = Field(
        None,
        description="Secondary brand color as hex code, e.g. #33FF57",
    )
    terms_url: Optional[str] = Field(
        None,
        description="URL to the organization terms and conditions page",
    )
    contact_name: Optional[str] = Field(
        None,
        description="Primary contact person full name, max 128 characters",
    )
    contact_email: Optional[str] = Field(
        None,
        description="Primary contact email address in valid email format",
    )
    contact_phone: Optional[str] = Field(
        None,
        description="Primary contact phone number, max 32 characters",
    )
    feature_flags: dict = Field(
        ...,
        description="Feature flag overrides as key-value boolean pairs",
    )
    allowed_origins: list[str] = Field(
        ...,
        description="List of allowed CORS origins for this organization",
    )
    shard_id: int = Field(
        ...,
        description="Database shard identifier, default 0 for single-shard deployment",
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the organization was created",
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp when the organization was last updated",
    )
    deleted_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp when the organization was soft-deleted, null if active",
    )

    model_config = {"from_attributes": True}
