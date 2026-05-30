"""Pydantic schemas for skills taxonomy."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class DomainCreate(BaseModel):
    """Schema for creating a domain."""
    name: str = Field(..., min_length=1, max_length=100, description="Unique domain name for skill categorization")
    description: Optional[str] = Field(None, description="Optional description of the domain")


class DomainResponse(BaseModel):
    """Schema for domain response."""
    domain_id: UUID = Field(..., description="Unique identifier for the domain")
    name: str = Field(..., description="Unique domain name for skill categorization")
    description: Optional[str] = Field(None, description="Optional description of the domain")
    created_at: datetime = Field(..., description="Timestamp when domain was created")
    updated_at: datetime = Field(..., description="Timestamp of last domain update")

    class Config:
        from_attributes = True


class SkillCreate(BaseModel):
    """Schema for creating a skill."""
    name: str = Field(..., min_length=1, max_length=100, description="Unique skill name within domain")


class SkillResponse(BaseModel):
    """Schema for skill response."""
    skill_id: UUID = Field(..., description="Unique identifier for the skill")
    domain_id: UUID = Field(..., description="Identifier of the associated domain")
    name: str = Field(..., description="Unique skill name within domain")
    created_at: datetime = Field(..., description="Timestamp when skill was created")
    updated_at: datetime = Field(..., description="Timestamp of last skill update")

    class Config:
        from_attributes = True


class CandidateSkillCreate(BaseModel):
    """Schema for adding a skill to a candidate."""
    skill_id: UUID = Field(..., description="Unique identifier of the skill")
    proficiency_rank: int = Field(..., ge=1, le=5, description="Proficiency level from 1 to 5")
    years_of_experience: int = Field(..., ge=0, le=50, description="Years of experience from 0 to 50")


class CandidateSkillResponse(BaseModel):
    """Schema for candidate skill response."""
    candidate_skill_id: UUID = Field(..., description="Unique identifier for candidate skill")
    candidate_id: UUID = Field(..., description="Unique identifier of the candidate")
    skill_id: UUID = Field(..., description="Unique identifier of the skill")
    proficiency_rank: int = Field(..., description="Proficiency level from 1 to 5")
    years_of_experience: int = Field(..., description="Years of experience from 0 to 50")
    source: str = Field(..., description="Source of skill: manual, parsed, or inferred")
    created_at: datetime = Field(..., description="Timestamp when candidate skill was created")
    updated_at: datetime = Field(..., description="Timestamp of last candidate skill update")

    class Config:
        from_attributes = True
