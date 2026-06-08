"""
Pydantic schemas for interview feedback endpoints.

Requirements: 3.1, 3.3, 3.4
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """Request model for creating interview feedback."""

    slot_id: UUID = Field(
        ..., description="The interview slot ID to attach feedback to"
    )
    competency_ratings: dict[str, int] = Field(
        ..., description="Competency ratings as a dictionary mapping competency names to integer ratings (1-5 scale)"
    )
    narrative: str = Field(
        ..., max_length=5000, description="Narrative summary of the feedback (maximum 5000 characters)"
    )
    hiring_recommendation: str = Field(
        ..., description="Hiring recommendation (StrongYes, Yes, Neutral, No, or StrongNo)"
    )


class FeedbackUpdate(BaseModel):
    """Request model for updating interview feedback."""

    competency_ratings: dict[str, int] | None = Field(
        None, description="Updated competency ratings as a dictionary (optional)"
    )
    narrative: str | None = Field(
        None, max_length=5000, description="Updated narrative summary (maximum 5000 characters, optional)"
    )
    hiring_recommendation: str | None = Field(
        None, description="Updated hiring recommendation (optional)"
    )


class FeedbackResponse(BaseModel):
    """Response model for interview feedback."""

    interview_feedback_id: UUID = Field(
        ..., description="Unique identifier for the interview feedback record"
    )
    interview_slot_id: UUID = Field(
        ..., description="The associated interview slot ID"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this feedback belongs to"
    )
    feedback_type: str = Field(
        ..., description="Type of feedback (Manual or AIGenerated)"
    )
    status: str = Field(
        ..., description="Current status of the feedback (Draft or Submitted)"
    )
    competency_ratings: dict[str, int] = Field(
        ..., description="Competency ratings as a dictionary mapping competency names to integer ratings"
    )
    narrative: str = Field(
        ..., description="Narrative summary of the feedback"
    )
    hiring_recommendation: str = Field(
        ..., description="Hiring recommendation (StrongYes, Yes, Neutral, No, or StrongNo)"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the feedback was created"
    )
    created_by: UUID = Field(
        ..., description="User ID of the feedback creator"
    )
    updated_at: datetime | None = Field(
        None, description="Timestamp when the feedback was last updated"
    )


class TranscriptRequest(BaseModel):
    """Request model for submitting an interview transcript."""

    slot_id: UUID = Field(
        ..., description="The interview slot ID to generate feedback for"
    )
    transcript: str = Field(
        ..., max_length=50000, description="Interview transcript text (maximum 50000 characters)"
    )
