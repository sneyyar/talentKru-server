"""Pydantic schemas for job profiles."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class JobProfileSkillCreate(BaseModel):
    """Schema for adding a skill to a job profile."""
    skill_id: UUID = Field(..., description="Unique identifier of the skill")
    designation: str = Field(..., description="Skill designation: required or desired")
    required_proficiency_rank: int = Field(..., ge=1, le=5, description="Required proficiency level from 1 to 5")


class JobProfileCreate(BaseModel):
    """Schema for creating a job profile."""
    name: str = Field(..., min_length=1, max_length=200, description="Name of the job profile")
    skills: Optional[List[JobProfileSkillCreate]] = Field(None, description="List of associated skills")


class JobProfileResponse(BaseModel):
    """Schema for job profile response."""
    job_profile_id: UUID = Field(..., description="Unique identifier for the job profile")
    organization_id: UUID = Field(..., description="Unique identifier of the organization")
    name: str = Field(..., description="Name of the job profile")
    created_at: datetime = Field(..., description="Timestamp when job profile was created")
    updated_at: datetime = Field(..., description="Timestamp of last job profile update")
    version: int = Field(..., description="Version number for optimistic locking")

    class Config:
        from_attributes = True
