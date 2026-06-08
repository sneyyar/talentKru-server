"""
Pydantic schemas for candidate availability endpoints.

Requirements: 7.1, 7.2, 7.3
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class AvailabilityCreate(BaseModel):
    """Request model for creating candidate availability."""

    interview_type: str = Field(
        ..., description="Interview type for this availability slot (RecruiterScreen, ManagerScreen, or LoopInterview)"
    )
    start_time: datetime = Field(
        ..., description="ISO 8601 datetime for the start of the availability window (must be at least 1 hour in future)"
    )
    end_time: datetime = Field(
        ..., description="ISO 8601 datetime for the end of the availability window (must be after start_time)"
    )
    timezone: str = Field(
        ..., max_length=100, description="IANA timezone identifier for this availability slot (maximum 100 characters)"
    )


class AvailabilityResponse(BaseModel):
    """Response model for candidate availability."""

    candidate_availability_slot_id: UUID = Field(
        ..., description="Unique identifier for the availability slot"
    )
    candidate_id: UUID = Field(
        ..., description="The candidate this availability belongs to"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this availability belongs to"
    )
    interview_type: str = Field(
        ..., description="Interview type for this availability slot"
    )
    start_time: datetime = Field(
        ..., description="ISO 8601 datetime for the start of the availability window"
    )
    end_time: datetime = Field(
        ..., description="ISO 8601 datetime for the end of the availability window"
    )
    timezone: str = Field(
        ..., description="IANA timezone identifier for this availability slot"
    )
    status: str = Field(
        ..., description="Current status of the availability slot (Active or Cancelled)"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the availability slot was created"
    )
    created_by: UUID = Field(
        ..., description="User ID of the availability slot creator"
    )
