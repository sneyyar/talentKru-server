"""
Pydantic schemas for password reset endpoints.

Requirements: 10.1, 10.3
"""

from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequest(BaseModel):
    """Request model for password reset request."""

    email: EmailStr = Field(..., max_length=254, description="User email address (max 254 chars)")


class PasswordResetConfirm(BaseModel):
    """Request model for password reset confirmation."""

    token: str = Field(
        ..., description="The password reset token sent to the user's email"
    )
    new_password: str = Field(
        ..., min_length=12, description="New password (min 12 chars, must include uppercase, lowercase, digit, special char)"
    )
