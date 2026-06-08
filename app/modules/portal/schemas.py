"""
Pydantic schemas for candidate portal endpoints.

Requirements: 5.1, 5.2, 5.4, 5.5, 5.6, 5.7
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class PortalTokenResponse(BaseModel):
    """Response model for portal token generation."""

    raw_token: str = Field(
        ..., description="The URL-safe token for portal access (minimum 32 bytes, returned only once)"
    )
    expires_at: datetime = Field(
        ..., description="ISO 8601 timestamp indicating when the token expires"
    )


class PortalVerifyRequest(BaseModel):
    """Request model for portal email verification."""

    token: str = Field(
        ..., min_length=1, description="The portal token string for authentication"
    )
    email: EmailStr = Field(
        ..., max_length=254, description="Candidate email address for verification (maximum 254 characters)"
    )


class PortalJWTResponse(BaseModel):
    """Response model for portal JWT token."""

    access_token: str = Field(
        ..., description="JWT access token valid for 60 minutes with scoped claims (candidate_id, org_id, sub)"
    )
    token_type: str = Field(
        default="bearer", description="Token type (always 'bearer')"
    )


class PortalQuestionnaireResponse(BaseModel):
    """Response model for candidate's portal questionnaire status."""

    candidate_questionnaire_response_id: UUID = Field(
        ..., description="Unique identifier for the candidate's questionnaire response"
    )
    questionnaire_id: UUID = Field(
        ..., description="The questionnaire ID"
    )
    questionnaire_title: str = Field(
        ..., description="Human-readable title of the questionnaire"
    )
    status: str = Field(
        ..., description="Current status of the response (Draft, Incomplete, or Submitted)"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the response was created"
    )
    updated_at: datetime | None = Field(
        None, description="Timestamp when the response was last updated"
    )
