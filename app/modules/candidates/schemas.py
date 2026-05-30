"""Pydantic schemas for candidate management."""

from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class CandidateCreate(BaseModel):
    """Schema for creating a new candidate."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Candidate full name (max 200 characters)"
    )
    email: EmailStr = Field(
        ...,
        description="Candidate email address (max 254 characters)"
    )
    phone: Optional[str] = Field(
        None,
        max_length=50,
        description="Candidate phone number (optional, max 50 characters)"
    )
    location: Optional[str] = Field(
        None,
        max_length=200,
        description="Candidate location (optional, max 200 characters)"
    )


class CandidateUpdate(BaseModel):
    """Schema for updating a candidate."""
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Candidate full name (optional, max 200 characters)"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Candidate email address (optional, max 254 characters)"
    )
    phone: Optional[str] = Field(
        None,
        max_length=50,
        description="Candidate phone number (optional, max 50 characters)"
    )
    location: Optional[str] = Field(
        None,
        max_length=200,
        description="Candidate location (optional, max 200 characters)"
    )
    global_status: Optional[str] = Field(
        None,
        description="Candidate global status (Active, Interviewing, Expired, Ineligible, Deleted)"
    )
    ineligibility_reason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Reason for ineligibility (required when status is Ineligible, max 1000 characters)"
    )


class CandidateResponse(BaseModel):
    """Schema for candidate response."""
    candidate_id: UUID = Field(
        ...,
        description="Unique candidate identifier (UUID)"
    )
    organization_id: UUID = Field(
        ...,
        description="Organization identifier (UUID)"
    )
    name: str = Field(
        ...,
        description="Candidate full name (max 200 characters)"
    )
    email: str = Field(
        ...,
        description="Candidate email address (max 254 characters)"
    )
    phone: Optional[str] = Field(
        None,
        description="Candidate phone number (optional, max 50 characters)"
    )
    location: Optional[str] = Field(
        None,
        description="Candidate location (optional, max 200 characters)"
    )
    global_status: str = Field(
        ...,
        description="Candidate global status (Active, Interviewing, Expired, Ineligible, Deleted)"
    )
    ineligibility_reason: Optional[str] = Field(
        None,
        description="Reason for ineligibility (max 1000 characters)"
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


class CandidateSearchParams(BaseModel):
    """Schema for candidate search parameters."""
    name: Optional[str] = Field(
        None,
        description="Partial name search (case-insensitive)"
    )
    email: Optional[str] = Field(
        None,
        description="Partial email search (case-insensitive)"
    )
    status: Optional[str] = Field(
        None,
        description="Exact status match (Active, Interviewing, Expired, Ineligible, Deleted)"
    )
    page: int = Field(
        1,
        ge=1,
        description="Page number (1-indexed, default 1)"
    )
    page_size: int = Field(
        50,
        ge=1,
        le=50,
        description="Results per page (max 50, default 50)"
    )
