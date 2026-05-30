"""Pydantic schemas for job requisitions."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class RequisitionCreate(BaseModel):
    """Schema for creating a job requisition."""
    title: str = Field(..., min_length=1, max_length=200, description="Title of the job requisition")
    department: str = Field(..., min_length=1, max_length=100, description="Department for the position")
    location: str = Field(..., min_length=1, max_length=200, description="Location of the position")
    hiring_manager_user_id: UUID = Field(..., description="Unique identifier of the hiring manager")
    job_profile_id: UUID = Field(..., description="Unique identifier of the job profile")
    description: Optional[str] = Field(None, max_length=5000, description="Detailed requisition description")


class RequisitionUpdate(BaseModel):
    """Schema for updating a job requisition."""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Title of the job requisition")
    department: Optional[str] = Field(None, min_length=1, max_length=100, description="Department for the position")
    location: Optional[str] = Field(None, min_length=1, max_length=200, description="Location of the position")
    status: Optional[str] = Field(None, description="Requisition status: open, on_hold, closed, cancelled")
    description: Optional[str] = Field(None, max_length=5000, description="Detailed requisition description")
    version: int = Field(..., description="Version number for optimistic locking")


class RequisitionResponse(BaseModel):
    """Schema for job requisition response."""
    job_requisition_id: UUID = Field(..., description="Unique identifier for the requisition")
    organization_id: UUID = Field(..., description="Unique identifier of the organization")
    title: str = Field(..., description="Title of the job requisition")
    department: str = Field(..., description="Department for the position")
    location: str = Field(..., description="Location of the position")
    hiring_manager_user_id: UUID = Field(..., description="Unique identifier of the hiring manager")
    job_profile_id: UUID = Field(..., description="Unique identifier of the job profile")
    status: str = Field(..., description="Requisition status: open, on_hold, closed, cancelled")
    description: Optional[str] = Field(None, description="Detailed requisition description")
    created_at: datetime = Field(..., description="Timestamp when requisition was created")
    updated_at: datetime = Field(..., description="Timestamp of last requisition update")
    version: int = Field(..., description="Version number for optimistic locking")

    class Config:
        from_attributes = True


class CandidateAssociationRequest(BaseModel):
    """Schema for associating a candidate with a requisition."""
    candidate_id: UUID = Field(..., description="Unique identifier of the candidate")
