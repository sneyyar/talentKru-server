"""Interview slot schemas."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any


class SlotCreate(BaseModel):
    """Schema for creating a new interview slot."""
    interview_journey_id: UUID = Field(
        ...,
        description="Journey identifier for which this interview slot is scheduled (UUID)"
    )
    type: str = Field(
        ...,
        description="Interview slot type (MANAGER, TECHNICAL, BEHAVIORAL, or PANEL)"
    )
    scheduled_start: datetime = Field(
        ...,
        description="Interview start time in ISO 8601 format with timezone information"
    )
    scheduled_end: datetime = Field(
        ...,
        description="Interview end time in ISO 8601 format with timezone information"
    )
    timezone: str = Field(
        ...,
        description="IANA timezone identifier for the interview (e.g., America/New_York)"
    )
    interviewer_user_id: Optional[UUID] = Field(
        None,
        description="Optional interviewer user identifier (UUID) for assignment to this slot"
    )


class SlotUpdate(BaseModel):
    """Schema for updating an interview slot."""
    status: Optional[str] = Field(
        None,
        description="Interview slot status (SCHEDULED, IN_PROGRESS, COMPLETE, or CANCELLED)"
    )
    invitation_status: Optional[str] = Field(
        None,
        description="Interviewer invitation status (PENDING, ACCEPTED, or DECLINED)"
    )
    attendance_status: Optional[str] = Field(
        None,
        description="Candidate attendance status (UNKNOWN, ATTENDED, or NO_SHOW)"
    )


class SlotResponse(BaseModel):
    """Schema for interview slot response."""
    interview_slot_id: UUID = Field(
        ...,
        description="Unique slot identifier (UUID)"
    )
    organization_id: UUID = Field(
        ...,
        description="Organization identifier (UUID)"
    )
    interview_journey_id: UUID = Field(
        ...,
        description="Journey identifier this slot belongs to (UUID)"
    )
    type: str = Field(
        ...,
        description="Interview slot type (MANAGER, TECHNICAL, BEHAVIORAL, or PANEL)"
    )
    scheduled_start: datetime = Field(
        ...,
        description="Interview start time in ISO 8601 format"
    )
    scheduled_end: datetime = Field(
        ...,
        description="Interview end time in ISO 8601 format"
    )
    timezone: str = Field(
        ...,
        description="IANA timezone identifier for the interview"
    )
    status: str = Field(
        ...,
        description="Interview slot status (SCHEDULED, IN_PROGRESS, COMPLETE, or CANCELLED)"
    )
    invitation_status: Optional[str] = Field(
        None,
        description="Interviewer invitation status (PENDING, ACCEPTED, DECLINED, or null if no interviewer)"
    )
    attendance_status: str = Field(
        ...,
        description="Candidate attendance status (UNKNOWN, ATTENDED, or NO_SHOW)"
    )
    interviewer_user_id: Optional[UUID] = Field(
        None,
        description="Assigned interviewer identifier (UUID) or null if unassigned"
    )
    feedback_id: Optional[UUID] = Field(
        None,
        description="Feedback identifier if feedback has been submitted (UUID) or null"
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


class InterviewerPreferenceCreate(BaseModel):
    """Schema for creating or updating interviewer scheduling preferences."""
    allowed_interview_types: List[str] = Field(
        ...,
        description="List of interview types this interviewer is allowed to conduct (subset of MANAGER, TECHNICAL, BEHAVIORAL, PANEL)"
    )
    max_interviews_per_day: int = Field(
        ...,
        ge=1,
        le=20,
        description="Maximum number of interviews allowed per day (must be between 1 and 20 inclusive)"
    )
    max_interviews_per_week: int = Field(
        ...,
        ge=1,
        le=100,
        description="Maximum number of interviews allowed per week (must be between 1 and 100 inclusive)"
    )
    working_hours: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional working hours constraints as JSON object (format: {day_of_week: {start_time, end_time}})"
    )
