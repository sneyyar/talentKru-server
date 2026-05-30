"""
Pydantic schemas for invitation endpoints.

Requirements: 9.3, 9.6
"""

from uuid import UUID

from pydantic import BaseModel, Field


class InvitationAcceptRequest(BaseModel):
    """Request model for accepting an invitation."""

    token: str = Field(
        ..., description="The invitation token sent to the user's email"
    )
    password: str = Field(
        ..., min_length=12, description="New password (min 12 chars, must include uppercase, lowercase, digit, special char)"
    )


class InvitationResendRequest(BaseModel):
    """Request model for resending an invitation."""

    user_id: UUID = Field(..., description="User ID to resend invitation to")
