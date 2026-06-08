"""Pydantic schemas for interview journey management."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class JourneyCreate(BaseModel):
    """Schema for creating a new interview journey."""
    candidate_id: UUID = Field(
        ...,
        description="Unique identifier for the candidate starting the journey (UUID)"
    )
    job_requisition_id: UUID = Field(
        ...,
        description="Unique identifier for the job requisition this journey applies to (UUID)"
    )


class JourneyTransitionRequest(BaseModel):
    """Schema for requesting a stage transition in an interview journey."""
    to_stage: str = Field(
        ...,
        description="Target interview stage (must be valid per FSM transition rules)"
    )
    comments: Optional[str] = Field(
        None,
        max_length=2000,
        description="Optional comments on the transition reason (maximum 2000 characters)"
    )


class JourneyResponse(BaseModel):
    """Schema for interview journey response."""
    interview_journey_id: UUID = Field(
        ...,
        description="Unique journey identifier (UUID)"
    )
    organization_id: UUID = Field(
        ...,
        description="Organization identifier (UUID)"
    )
    journey_public_id: str = Field(
        ...,
        description="URL-safe public identifier for external references (minimum 22 characters)"
    )
    candidate_id: UUID = Field(
        ...,
        description="Candidate identifier (UUID)"
    )
    job_requisition_id: UUID = Field(
        ...,
        description="Job requisition identifier (UUID)"
    )
    current_stage: str = Field(
        ...,
        description="Current interview stage in the journey (e.g., SOURCED, RECRUITER_SCREEN, etc.)"
    )
    current_stage_status: Optional[str] = Field(
        None,
        description="Sub-status of current stage if applicable (SCHEDULED, IN_PROGRESS, COMPLETE or null for terminal stages)"
    )
    overall_status: str = Field(
        ...,
        description="Overall journey status (ACTIVE, ON_HOLD, COMPLETED, or CANCELLED)"
    )
    offer_extended_at: Optional[datetime] = Field(
        None,
        description="Timestamp when offer was extended to the candidate (ISO 8601 format)"
    )
    offer_responded_at: Optional[datetime] = Field(
        None,
        description="Timestamp when candidate responded to offer (ISO 8601 format)"
    )
    start_date: datetime = Field(
        ...,
        description="Date the journey started (ISO 8601 format)"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp (ISO 8601 format)"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp (ISO 8601 format)"
    )
    version: int = Field(
        ...,
        description="Version for optimistic locking (incremented on each update)"
    )

    class Config:
        from_attributes = True


class StageHistoryResponse(BaseModel):
    """Schema for interview journey stage history record."""
    interview_journey_stage_history_id: UUID = Field(
        ...,
        description="Unique history record identifier (UUID)"
    )
    interview_journey_id: UUID = Field(
        ...,
        description="Journey identifier this history record belongs to (UUID)"
    )
    from_stage: str = Field(
        ...,
        description="Interview stage before transition (e.g., SOURCED, RECRUITER_SCREEN)"
    )
    to_stage: str = Field(
        ...,
        description="Interview stage after transition (e.g., RECRUITER_SCREEN, REJECTED)"
    )
    changed_by_user_id: UUID = Field(
        ...,
        description="User identifier of who made the transition (UUID)"
    )
    changed_at: datetime = Field(
        ...,
        description="Timestamp of transition (ISO 8601 format)"
    )
    comments: Optional[str] = Field(
        None,
        description="Optional comments provided during transition (maximum 2000 characters)"
    )

    class Config:
        from_attributes = True
