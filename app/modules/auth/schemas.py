"""
Pydantic schemas for authentication endpoints.

Requirements: 3.9, 4.2, 2.1
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Request model for user login endpoint."""

    email: EmailStr = Field(
        ..., max_length=254, description="User email address (max 254 chars)"
    )
    password: str = Field(
        ..., min_length=1, description="User password"
    )


class TokenResponse(BaseModel):
    """Response model for token endpoints."""

    access_token: str = Field(
        ..., description="JWT access token (60-minute TTL)"
    )
    refresh_token: str = Field(
        ..., description="Opaque refresh token (7-day TTL)"
    )
    token_type: str = Field(
        default="bearer", description="Token type (always 'bearer')"
    )


class RefreshRequest(BaseModel):
    """Request model for token refresh endpoint."""

    refresh_token: str = Field(
        ..., description="The refresh token to exchange for a new access token"
    )


class ImpersonateRequest(BaseModel):
    """Request model for SuperAdmin impersonation endpoint."""

    target_org_id: UUID = Field(
        ..., description="The organization ID to impersonate within"
    )
    target_user_id: UUID = Field(
        ..., description="The user ID to impersonate (must hold Administrator role)"
    )
