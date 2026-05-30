"""Pydantic schemas for privacy and GDPR compliance."""

from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal


class DSARManageResponse(BaseModel):
    """Schema for DSAR management response with all DSAR fields."""
    dsar_id: UUID = Field(
        ...,
        description="Unique identifier for the data subject access request"
    )
    candidate_id: UUID = Field(
        ...,
        description="Unique identifier of the candidate who submitted the request"
    )
    organization_id: UUID = Field(
        ...,
        description="Unique identifier of the organization managing the request"
    )
    request_type: Literal["Access", "Erasure"] = Field(
        ...,
        description="Type of data subject access request: Access to retrieve personal data or Erasure to delete personal data"
    )
    status: Literal["Pending", "Processing", "Completed", "Denied"] = Field(
        ...,
        description="Current status of the DSAR: Pending, Processing, Completed, or Denied"
    )
    requested_at: datetime = Field(
        ...,
        description="Timestamp when the data subject access request was submitted"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the data subject access request was completed or denied"
    )
    denial_reason: Optional[str] = Field(
        None,
        description="Reason provided by administrator for denying the data subject access request"
    )

    class Config:
        from_attributes = True


class DSARDenyRequest(BaseModel):
    """Schema for denying a DSAR with required reason."""
    denial_reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Reason for denying the data subject access request (minimum 10 characters)"
    )

    @field_validator("denial_reason")
    @classmethod
    def validate_denial_reason(cls, v: str) -> str:
        """Ensure denial reason is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Denial reason cannot be empty or contain only whitespace")
        if len(v.strip()) < 10:
            raise ValueError("Denial reason must be at least 10 non-whitespace characters")
        return v


class RetentionPolicyResponse(BaseModel):
    """Schema for organization retention policy response."""
    organization_retention_policy_id: UUID = Field(
        ...,
        description="Unique identifier for the organization retention policy"
    )
    organization_id: UUID = Field(
        ...,
        description="Unique identifier of the organization this policy applies to"
    )
    candidate_data_retention_days: int = Field(
        ...,
        ge=1,
        description="Number of days to retain candidate profile data before purging"
    )
    resume_retention_days: int = Field(
        ...,
        ge=1,
        description="Number of days to retain resume files before purging"
    )
    audit_log_retention_days: int = Field(
        ...,
        ge=1,
        description="Number of days to retain audit log entries before purging"
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the retention policy was created"
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the retention policy was last updated"
    )

    class Config:
        from_attributes = True


class RetentionPolicyUpdate(BaseModel):
    """Schema for updating retention policy with optional fields."""
    candidate_data_retention_days: Optional[int] = Field(
        None,
        ge=1,
        description="Number of days to retain candidate profile data before purging"
    )
    resume_retention_days: Optional[int] = Field(
        None,
        ge=1,
        description="Number of days to retain resume files before purging"
    )
    audit_log_retention_days: Optional[int] = Field(
        None,
        ge=1,
        description="Number of days to retain audit log entries before purging"
    )
