"""
Pydantic schemas for email configuration endpoints.

Requirements: 6.1, 6.2, 6.5, 6.8
"""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class EmailConfigCreate(BaseModel):
    """Request model for creating organization email configuration."""

    provider_type: str = Field(
        ..., description="Email provider type (smtp, sendgrid, or ses)"
    )
    smtp_host: str | None = Field(
        None, max_length=253, description="SMTP host address for SMTP provider (required for smtp, max 253 characters)"
    )
    smtp_port: int | None = Field(
        None, description="SMTP port number for SMTP provider (required for smtp, typically 25/465/587)"
    )
    smtp_username: str | None = Field(
        None, max_length=254, description="SMTP username for SMTP provider (required for smtp, max 254 characters)"
    )
    smtp_password: str | None = Field(
        None, description="SMTP password for SMTP provider (required for smtp, stored encrypted)"
    )
    smtp_use_tls: bool | None = Field(
        None, description="Whether to use TLS for SMTP provider (optional, defaults to true)"
    )
    third_party_api_key: str | None = Field(
        None, description="API key for SendGrid or SES provider (required for sendgrid/ses, stored encrypted)"
    )
    third_party_provider_region: str | None = Field(
        None, max_length=100, description="AWS region for SES provider (optional, max 100 characters)"
    )
    from_address: EmailStr = Field(
        ..., max_length=254, description="Email address to use in the From field (maximum 254 characters)"
    )
    from_name: str = Field(
        ..., max_length=100, description="Display name to use in the From field (maximum 100 characters)"
    )


class EmailConfigUpdate(BaseModel):
    """Request model for updating organization email configuration."""

    provider_type: str | None = Field(
        None, description="Email provider type (smtp, sendgrid, or ses, optional)"
    )
    smtp_host: str | None = Field(
        None, max_length=253, description="SMTP host address (optional)"
    )
    smtp_port: int | None = Field(
        None, description="SMTP port number (optional)"
    )
    smtp_username: str | None = Field(
        None, max_length=254, description="SMTP username (optional)"
    )
    smtp_password: str | None = Field(
        None, description="SMTP password (optional, stored encrypted)"
    )
    smtp_use_tls: bool | None = Field(
        None, description="Whether to use TLS for SMTP (optional)"
    )
    third_party_api_key: str | None = Field(
        None, description="API key for third-party provider (optional, stored encrypted)"
    )
    third_party_provider_region: str | None = Field(
        None, max_length=100, description="AWS region for SES provider (optional)"
    )
    from_address: EmailStr | None = Field(
        None, max_length=254, description="Email address for From field (optional)"
    )
    from_name: str | None = Field(
        None, max_length=100, description="Display name for From field (optional)"
    )


class EmailConfigResponse(BaseModel):
    """Response model for organization email configuration (no plaintext passwords)."""

    organization_email_config_id: UUID = Field(
        ..., description="Unique identifier for the email configuration"
    )
    organization_id: UUID = Field(
        ..., description="The organization ID this configuration belongs to"
    )
    email_notifications_enabled: bool = Field(
        ..., description="Whether email notifications are enabled for this organization"
    )
    provider_type: str = Field(
        ..., description="Email provider type (smtp, sendgrid, or ses)"
    )
    smtp_host: str | None = Field(
        None, description="SMTP host address (if configured)"
    )
    smtp_port: int | None = Field(
        None, description="SMTP port number (if configured)"
    )
    smtp_username: str | None = Field(
        None, description="SMTP username (if configured)"
    )
    smtp_use_tls: bool | None = Field(
        None, description="Whether TLS is enabled for SMTP (if configured)"
    )
    third_party_provider_region: str | None = Field(
        None, description="AWS region for SES (if configured)"
    )
    from_address: str = Field(
        ..., description="Email address used in From field"
    )
    from_name: str = Field(
        ..., description="Display name used in From field"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the configuration was created"
    )
    created_by: UUID = Field(
        ..., description="User ID of the configuration creator"
    )


class SystemSettingResponse(BaseModel):
    """Response model for a system setting."""

    setting_key: str = Field(
        ..., description="Unique identifier for the system setting (e.g., email_notifications_enabled)"
    )
    setting_value: str = Field(
        ..., description="String value of the setting (e.g., 'true' or 'false')"
    )
    description: str | None = Field(
        None, description="Human-readable description of what this setting controls"
    )
    updated_at: datetime | None = Field(
        None, description="Timestamp when the setting was last updated"
    )


class SystemSettingUpdate(BaseModel):
    """Request model for updating a system setting."""

    setting_value: str = Field(
        ..., min_length=1, description="New value for the system setting"
    )
