"""
Pydantic schemas for user management endpoints.

Requirements: 1.1, 1.7, 3.9, 7.6
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.models import UserStatus


class UserCreate(BaseModel):
    """Request model for user creation."""

    email: EmailStr = Field(
        ..., max_length=254, description="User email address (max 254 chars)"
    )
    given_name: str = Field(
        ..., min_length=1, max_length=100, description="User's given name (max 100 chars)"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=100, description="User's last name (max 100 chars)"
    )
    manager_user_id: Optional[UUID] = Field(
        None, description="Optional manager user ID"
    )
    locale: Optional[str] = Field(
        None, max_length=10, description="User's locale (e.g., en-US, max 10 chars)"
    )


class UserUpdate(BaseModel):
    """Request model for user updates."""

    given_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="User's given name (max 100 chars)"
    )
    last_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="User's last name (max 100 chars)"
    )
    locale: Optional[str] = Field(
        None, max_length=10, description="User's locale (e.g., en-US, max 10 chars)"
    )
    manager_user_id: Optional[UUID] = Field(
        None, description="Optional manager user ID"
    )


class UserResponse(BaseModel):
    """Response model for user endpoints."""

    user_id: UUID
    organization_id: Optional[UUID]
    given_name: str
    last_name: str
    status: UserStatus
    locale: str
    manager_user_id: Optional[UUID]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Response model for paginated user list."""

    items: list[UserResponse]
    total: int
    page: int
    page_size: int
