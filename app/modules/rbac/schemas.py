"""
Pydantic schemas for RBAC endpoints.

Requirements: 5.1, 6.1, 6.2
"""

from uuid import UUID

from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    """Response model for role."""

    role_name: str = Field(..., description="Role name")
    description: str | None = Field(None, description="Role description")

    class Config:
        from_attributes = True


class RoleAssignRequest(BaseModel):
    """Request model for assigning a role to a user."""

    role_name: str = Field(..., description="Role name to assign")

    class Config:
        from_attributes = True


class PrivilegeResponse(BaseModel):
    """Response model for privilege."""

    privilege_id: UUID = Field(..., description="Privilege ID")
    name: str = Field(
        ..., max_length=100, description="Privilege name (snake_case, max 100 chars)"
    )
    description: str | None = Field(
        None, max_length=500, description="Privilege description (max 500 chars)"
    )
    resource_category: str = Field(
        ..., description="Resource category (e.g., 'candidates')"
    )

    class Config:
        from_attributes = True


class RolePrivilegeResponse(BaseModel):
    """Response model for role-privilege assignment."""

    role_privilege_id: UUID = Field(..., description="Role-privilege ID")
    role_name: str = Field(..., description="Role name")
    privilege_id: UUID = Field(..., description="Privilege ID")

    class Config:
        from_attributes = True


class AssignPrivilegeRequest(BaseModel):
    """Request model for assigning a privilege to a role."""

    privilege_id: UUID = Field(..., description="Privilege ID to assign")

    class Config:
        from_attributes = True

