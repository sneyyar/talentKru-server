"""Candidate feedback survey schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SurveyQuestionResponse(BaseModel):
    """Survey question response."""
    candidate_feedback_survey_question_id: UUID = Field(description="Unique question ID")
    question_text: str = Field(description="The survey question text")
    category: str = Field(description="Question category (APPLICATION, RECRUITER_EXPERIENCE, etc.)")
    is_required: bool = Field(description="Whether this question is required")
    display_order: int = Field(description="Display order of the question (1-10)")


class SurveyFormResponse(BaseModel):
    """Survey form with questions."""
    candidate_feedback_survey_id: UUID = Field(description="Unique survey ID")
    questions: list[SurveyQuestionResponse] = Field(description="List of survey questions")


class SurveySubmitRequest(BaseModel):
    """Submit survey with answers."""
    answers: dict[str, int] = Field(
        description="Mapping of question_id to rating (0-10, where 0 is N/A)"
    )
    additional_comments: str | None = Field(
        default=None,
        max_length=2000,
        description="Additional open-ended feedback (max 2000 chars)",
    )


class SurveySubmitResponse(BaseModel):
    """Success response after survey submission."""
    success: bool = Field(description="Whether submission succeeded")
    message: str = Field(description="Confirmation message")


class SurveyTemplateCreate(BaseModel):
    """Create survey feedback template."""
    template_type: str = Field(
        description="Template type: initial_survey_invitation or survey_reminder",
    )
    subject: str = Field(
        min_length=1,
        max_length=200,
        description="Email subject line (max 200 characters)",
    )
    body_template: str = Field(
        min_length=1,
        description="Email body template with {{variable}} placeholders for substitution",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether this template is enabled for use",
    )


class SurveyTemplateUpdate(BaseModel):
    """Update survey feedback template."""
    subject: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Email subject line (max 200 characters)",
    )
    body_template: str | None = Field(
        default=None,
        min_length=1,
        description="Email body template with {{variable}} placeholders for substitution",
    )
    is_enabled: bool | None = Field(
        default=None,
        description="Whether this template is enabled for use",
    )


class SurveyTemplateResponse(BaseModel):
    """Survey feedback template response."""
    survey_feedback_template_id: UUID = Field(description="Unique template ID")
    organization_id: UUID = Field(description="Organization UUID")
    template_type: str = Field(description="Template type")
    subject: str = Field(description="Email subject line")
    body_template: str = Field(description="Email body template")
    is_enabled: bool = Field(description="Whether template is enabled")
    version: int = Field(description="Version for optimistic locking")
    created_at: datetime = Field(description="Template creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    class Config:
        from_attributes = True

