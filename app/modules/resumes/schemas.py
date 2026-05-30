"""Pydantic schemas for resume management."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class ResumeUploadResponse(BaseModel):
    """Schema for resume upload response."""
    resume_id: UUID = Field(
        ...,
        description="Unique resume identifier (UUID)"
    )
    parse_status: str = Field(
        ...,
        description="Resume parsing status (Pending, Completed, Failed)"
    )


class ResumeResponse(BaseModel):
    """Schema for resume response."""
    resume_id: UUID = Field(
        ...,
        description="Unique resume identifier (UUID)"
    )
    candidate_id: Optional[UUID] = Field(
        None,
        description="Associated candidate ID (nullable at upload)"
    )
    organization_id: UUID = Field(
        ...,
        description="Organization identifier (UUID)"
    )
    storage_location: str = Field(
        ...,
        description="Storage URI for the resume file (local:// or s3://)"
    )
    mime_type: str = Field(
        ...,
        description="MIME type of the resume file (application/pdf, application/msword, application/vnd.openxmlformats-officedocument.wordprocessingml.document)"
    )
    file_name: str = Field(
        ...,
        description="Original filename of the resume"
    )
    file_size_bytes: int = Field(
        ...,
        description="File size in bytes (max 10 MB)"
    )
    uploaded_by_user_id: UUID = Field(
        ...,
        description="User ID who uploaded the resume"
    )
    is_primary: bool = Field(
        ...,
        description="Whether this is the primary resume for the candidate"
    )
    parse_status: str = Field(
        ...,
        description="Resume parsing status (Pending, Completed, Failed)"
    )
    parsed_data: Optional[dict] = Field(
        None,
        description="Parsed resume data (extracted name, email, phone, summary, job history, skills)"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp (ISO 8601 format)"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp (ISO 8601 format)"
    )

    class Config:
        from_attributes = True


class PaginatedResumeList(BaseModel):
    """Schema for paginated resume list response."""
    items: List[ResumeResponse] = Field(
        ...,
        description="List of resume records"
    )
    total: int = Field(
        ...,
        description="Total number of resumes available"
    )
    page: int = Field(
        ...,
        description="Current page number (1-indexed)"
    )
    page_size: int = Field(
        ...,
        description="Number of items per page"
    )
    total_pages: int = Field(
        ...,
        description="Total number of pages available"
    )
