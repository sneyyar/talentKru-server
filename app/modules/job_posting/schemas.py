"""Pydantic schemas for job postings."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class JobPostingCreate(BaseModel):
    """Schema for creating a job posting."""
    job_profile_id: UUID = Field(..., description="Unique identifier of the job profile")
    description: str = Field(..., min_length=1, max_length=5000, description="Detailed job description")
    work_locations: List[str] = Field(..., description="List of work location strings")
    salary_min: float = Field(..., ge=0, description="Minimum salary for the position")
    salary_max: float = Field(..., ge=0, description="Maximum salary for the position")
    salary_currency: str = Field(..., max_length=3, description="ISO 4217 currency code")
    sourcing_channel: str = Field(..., max_length=100, description="Channel where job is posted")


class JobPostingFilter(BaseModel):
    """Schema for filtering job postings."""
    location: Optional[str] = Field(None, description="Filter by specific work location")
    salary_filter_min: Optional[float] = Field(None, ge=0, description="Minimum salary filter value")
    salary_filter_max: Optional[float] = Field(None, ge=0, description="Maximum salary filter value")
    sourcing_channel: Optional[str] = Field(None, description="Filter by sourcing channel")
    page: int = Field(1, ge=1, description="Page number for pagination")
    page_size: int = Field(50, ge=1, le=50, description="Results per page for pagination")


class JobPostingResponse(BaseModel):
    """Schema for job posting response."""
    job_posting_id: UUID = Field(..., description="Unique identifier for the job posting")
    organization_id: UUID = Field(..., description="Unique identifier of the organization")
    job_profile_id: UUID = Field(..., description="Unique identifier of the job profile")
    description: str = Field(..., description="Detailed job description")
    work_locations: List[str] = Field(..., description="List of work location strings")
    salary_min: float = Field(..., description="Minimum salary for the position")
    salary_max: float = Field(..., description="Maximum salary for the position")
    salary_currency: str = Field(..., description="ISO 4217 currency code")
    sourcing_channel: str = Field(..., description="Channel where job is posted")
    created_at: datetime = Field(..., description="Timestamp when job posting was created")
    updated_at: datetime = Field(..., description="Timestamp of last job posting update")
    version: int = Field(..., description="Version number for optimistic locking")

    class Config:
        from_attributes = True
