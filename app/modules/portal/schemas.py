"""Pydantic schemas for candidate portal."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal


class DSARCreateRequest(BaseModel):
    """Schema for creating a Data Subject Access Request."""
    request_type: Literal["Access", "Erasure"] = Field(
        ...,
        description="Type of data subject access request: Access to retrieve personal data or Erasure to delete personal data"
    )


class DSARResponse(BaseModel):
    """Schema for DSAR response returned to candidate."""
    dsar_id: UUID = Field(
        ...,
        description="Unique identifier for the data subject access request"
    )
    status: str = Field(
        ...,
        description="Current status of the DSAR: Pending, Processing, Completed, or Denied"
    )
    requested_at: datetime = Field(
        ...,
        description="Timestamp when the data subject access request was submitted"
    )

    class Config:
        from_attributes = True
