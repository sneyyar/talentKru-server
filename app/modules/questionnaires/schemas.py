"""
Pydantic schemas for questionnaire endpoints.

Requirements: 4.1, 4.5, 4.6, 4.9, 5.7
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class QuestionnaireCreate(BaseModel):
    """Request model for creating a questionnaire."""

    title: str = Field(
        ..., min_length=1, max_length=500, description="Title of the questionnaire (maximum 500 characters)"
    )
    questions_yaml: str = Field(
        ..., min_length=1, description="Questionnaire questions in YAML format defining structure with questions list"
    )


class QuestionnaireResponse(BaseModel):
    """Response model for a questionnaire."""

    questionnaire_id: UUID = Field(
        ..., description="Unique identifier for the questionnaire record"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this questionnaire belongs to"
    )
    title: str = Field(
        ..., description="Title of the questionnaire"
    )
    questions_yaml: str = Field(
        ..., description="Questionnaire questions in YAML format"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the questionnaire was created"
    )
    created_by: UUID = Field(
        ..., description="User ID of the questionnaire creator"
    )


class ResponseCreate(BaseModel):
    """Request model for saving questionnaire responses."""

    answers: dict[str, str] = Field(
        ..., description="Dictionary mapping question IDs to candidate answers as strings"
    )
    is_final_submit: bool = Field(
        False, description="Boolean indicating if this is the final submission (true) or a draft save (false)"
    )


class CandidateQuestionnaireResponseSchema(BaseModel):
    """Response model for a candidate questionnaire response."""

    candidate_questionnaire_response_id: UUID = Field(
        ..., description="Unique identifier for the candidate response record"
    )
    candidate_id: UUID = Field(
        ..., description="The candidate this response belongs to"
    )
    questionnaire_id: UUID = Field(
        ..., description="The questionnaire being responded to"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this response belongs to"
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
