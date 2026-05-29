"""Pydantic schemas for candidate management."""

from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class CandidateCreate(BaseModel):
    """Schema for creating a new candidate."""
    name: str = Field(..., min_length=1, max_length=200, description="Candidate full name")
    email: EmailStr = Field(..., description="Candidate email address")
    phone: Optional[str] = Field(None, max_length=50, description="Candidate phone number")
    location: Optional[str] = Field(None, max_length=200, description="Candidate location")


class CandidateUpdate(BaseModel):
    """Schema for updating a candidate."""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Candidate full name")
    email: Optional[EmailStr] = Field(None, description="Candidate email address")
    phone: Optional[str] = Field(None, max_length=50, description="Candidate phone number")
    location: Optional[str] = Field(None, max_length=200, description="Candidate location")
    global_status: Optional[str] = Field(None, description="Candidate global status")
    ineligibility_reason: Optional[str] = Field(None, max_length=1000, description="Reason for ineligibility")


class CandidateResponse(BaseModel):
    """Schema for candidate response."""
    candidate_id: UUID = Field(..., description="Unique candidate identifier")
    organization_id: UUID = Field(..., description="Organization identifier")
    name: str = Field(..., description="Candidate full name")
    email: str = Field(..., description="Candidate email address")
    phone: Optional[str] = Field(None, description="Candidate phone number")
    location: Optional[str] = Field(None, description="Candidate location")
    global_status: str = Field(..., description="Candidate global status")
    ineligibility_reason: Optional[str] = Field(None, description="Reason for ineligibility")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    version: int = Field(..., description="Version for optimistic locking")

    class Config:
        from_attributes = True


class CandidateSearchParams(BaseModel):
    """Schema for candidate search parameters."""
    name: Optional[str] = Field(None, description="Partial name search")
    email: Optional[str] = Field(None, description="Partial email search")
    status: Optional[str] = Field(None, description="Exact status match")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=50, description="Results per page")
