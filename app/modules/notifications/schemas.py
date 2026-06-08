"""
Pydantic schemas for notification endpoints.

Requirements: 8.7, 8.8, 9.7, 9.17, 9.18
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class NotificationTemplateCreate(BaseModel):
    """Request model for creating a notification template."""

    event_type: str = Field(
        ..., min_length=1, description="Type of event this template handles (e.g., journey_stage_changed)"
    )
    subject: str = Field(
        ..., max_length=200, description="Email subject line template with {{placeholder}} variables (maximum 200 characters)"
    )
    body_template: str = Field(
        ..., min_length=1, description="Email body template with {{placeholder}} variables for dynamic content insertion"
    )
    is_enabled: bool = Field(
        True, description="Whether this notification template is currently enabled"
    )
    locale: str | None = Field(
        None, max_length=10, description="Language and region code for locale-specific variants (e.g., en_US, max 10 characters)"
    )


class NotificationTemplateResponse(BaseModel):
    """Response model for a notification template."""

    notification_template_id: UUID = Field(
        ..., description="Unique identifier for the notification template"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this template belongs to"
    )
    event_type: str = Field(
        ..., description="Type of event this template handles"
    )
    subject: str = Field(
        ..., description="Email subject line template"
    )
    body_template: str = Field(
        ..., description="Email body template"
    )
    is_enabled: bool = Field(
        ..., description="Whether this template is currently enabled"
    )
    locale: str | None = Field(
        None, description="Language and region code for this template variant"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the template was created"
    )
    created_by: UUID = Field(
        ..., description="User ID of the template creator"
    )


class NotificationRecordResponse(BaseModel):
    """Response model for a notification delivery record."""

    notification_record_id: UUID = Field(
        ..., description="Unique identifier for the notification record"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this notification was sent to"
    )
    event_type: str = Field(
        ..., description="Type of event that triggered this notification"
    )
    recipient_email: str = Field(
        ..., description="Email address of the notification recipient"
    )
    status: str = Field(
        ..., description="Current delivery status (Pending, Retrying, Delivered, PermanentlyFailed)"
    )
    attempt_count: int = Field(
        ..., description="Number of delivery attempts made for this notification"
    )
    delivered_at: datetime | None = Field(
        None, description="Timestamp when the notification was successfully delivered"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the notification record was created"
    )


class SurveyFeedbackTemplateCreate(BaseModel):
    """Request model for creating a survey feedback template."""

    template_type: str = Field(
        ..., description="Template type (initial_survey_invitation or survey_reminder)"
    )
    subject: str = Field(
        ..., max_length=200, description="Email subject line template with {{placeholder}} variables (maximum 200 characters)"
    )
    body_template: str = Field(
        ..., min_length=1, description="Email body template with {{placeholder}} variables for survey-specific content"
    )
    is_enabled: bool = Field(
        True, description="Whether this survey template is currently enabled"
    )


class SurveyFeedbackTemplateResponse(BaseModel):
    """Response model for a survey feedback template."""

    survey_feedback_template_id: UUID = Field(
        ..., description="Unique identifier for the survey feedback template"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this template belongs to"
    )
    template_type: str = Field(
        ..., description="Template type (initial_survey_invitation or survey_reminder)"
    )
    subject: str = Field(
        ..., description="Email subject line template"
    )
    body_template: str = Field(
        ..., description="Email body template"
    )
    is_enabled: bool = Field(
        ..., description="Whether this template is currently enabled"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the template was created"
    )
    created_by: UUID = Field(
        ..., description="User ID of the template creator"
    )
