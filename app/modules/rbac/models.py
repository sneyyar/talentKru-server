"""
RBAC models for role-based access control.

Provides:
- Role: role definitions with descriptions
- UserRole: user-to-role assignments with audit tracking
- Privilege: granular permissions with resource categorization
- RolePrivilege: role-to-privilege assignments with audit tracking

Requirements: 5.1, 5.2, 6.1, 6.2
"""

import uuid

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.base_model import AuditMixin, Base


class Role(Base):
    """
    Role entity for grouping privileges.

    Requirements: 5.1
    """

    __tablename__ = "roles"

    role_name = Column(String(64), primary_key=True)
    description = Column(String(256), nullable=True)

    user_roles = relationship("UserRole", back_populates="role")
    role_privileges = relationship("RolePrivilege", back_populates="role")


class UserRole(Base, AuditMixin):
    """
    User-to-role assignment with audit tracking.

    Requirements: 5.1, 5.2
    """

    __tablename__ = "user_roles"

    user_role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    role_name = Column(
        String(64), ForeignKey("roles.role_name"), nullable=False
    )

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (UniqueConstraint("user_id", "role_name", name="uq_user_roles"),)


class Privilege(Base):
    """
    Privilege entity for granular permissions.

    Requirements: 6.1
    """

    __tablename__ = "privileges"

    privilege_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(
        String(100), nullable=False, unique=True
    )  # snake_case identifier
    description = Column(String(500), nullable=True)
    resource_category = Column(
        String(64), nullable=False
    )  # e.g., "candidates", "requisitions"

    role_privileges = relationship("RolePrivilege", back_populates="privilege")


class RolePrivilege(Base, AuditMixin):
    """
    Role-to-privilege assignment with audit tracking.

    Requirements: 6.1, 6.2
    """

    __tablename__ = "role_privileges"

    role_privilege_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_name = Column(
        String(64), ForeignKey("roles.role_name"), nullable=False
    )
    privilege_id = Column(
        UUID(as_uuid=True), ForeignKey("privileges.privilege_id"), nullable=False
    )

    role = relationship("Role", back_populates="role_privileges")
    privilege = relationship("Privilege", back_populates="role_privileges")

    __table_args__ = (
        UniqueConstraint(
            "role_name", "privilege_id", name="uq_role_privileges"
        ),
    )
