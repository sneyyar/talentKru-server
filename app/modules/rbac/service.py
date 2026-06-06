"""
RBAC service for role and privilege management.

Provides:
- RBACService: Role assignment, privilege management, audit logging

Requirements: 5.1, 5.2, 5.8, 5.9, 6.1, 6.2, 6.5, 6.6, 6.7, 6.8, 6.9
"""

from datetime import datetime, timezone
from typing import Optional, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit_log
from app.decorators import transactional, read_only
from app.modules.rbac.models import (
    Privilege,
    Role,
    RolePrivilege,
    UserRole,
)


# Supported roles
SUPPORTED_ROLES = {
    "SuperAdministrator",
    "Administrator",
    "Recruiter",
    "HiringManager",
    "CommitteeMember",
    "HRManager",
    "Interviewer",
}


class RBACService:
    """
    RBAC service for role and privilege management.
    
    Requirements: 5.1, 5.2, 5.8, 5.9, 6.1, 6.2, 6.5, 6.6, 6.7, 6.8, 6.9
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the RBAC service.
        
        Args:
            db: AsyncSession for database access
        """
        self.db = db

    @transactional(name="assign_role")
    async def assign_role(
        self, user_id: UUID, role_name: str, actor_id: UUID, obo_by: Optional[UUID] = None
    ) -> UserRole:
        """
        Assign a role to a user.
        
        Args:
            user_id: User ID
            role_name: Role name to assign
            actor_id: User ID of the actor performing the assignment
            obo_by: SuperAdmin user ID if this is an on-behalf-of action (for audit logging)
            
        Returns:
            Created UserRole entity
            
        Raises:
            ValueError: If role name is not supported or user already has role
            
        Requirements: 5.1, 5.2, 5.8, 7.3
        """
        # Validate role name
        if role_name not in SUPPORTED_ROLES:
            raise ValueError(f"Unknown role: {role_name}")
        
        # Check if user already has this role
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_name == role_name,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise ValueError(f"User already has role {role_name}")
        
        # Create user role
        user_role = UserRole(
            user_id=user_id,
            role_name=role_name,
        )
        self.db.add(user_role)
        await self.db.flush()
        
        # Write audit log entry
        await write_audit_log(
            actor_id=actor_id,
            action="RoleAssigned",
            target_entity="UserRole",
            target_id=user_role.user_role_id,
            changed_values={
                "user_id": str(user_id),
                "role_name": role_name,
            },
            obo_by=obo_by,
            timestamp=datetime.now(timezone.utc),
            db=self.db,
        )
        
        return user_role

    @transactional(name="remove_role")
    async def remove_role(
        self, user_id: UUID, role_name: str, actor_id: UUID, obo_by: Optional[UUID] = None
    ) -> None:
        """
        Remove a role from a user.
        
        Args:
            user_id: User ID
            role_name: Role name to remove
            actor_id: User ID of the actor performing the removal
            obo_by: SuperAdmin user ID if this is an on-behalf-of action (for audit logging)
            
        Raises:
            ValueError: If user doesn't have the role
            
        Requirements: 5.1, 5.2, 5.9, 7.3
        """
        # Find the user role
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_name == role_name,
        )
        result = await self.db.execute(stmt)
        user_role = result.scalar_one_or_none()
        
        if not user_role:
            raise ValueError(f"User does not have role {role_name}")
        
        # Soft delete
        from app.base_model import current_user_id_var
        from datetime import datetime, timezone
        
        user_role.deleted_at = datetime.now(timezone.utc)
        user_role.deleted_by = UUID(current_user_id_var.get() or "00000000-0000-0000-0000-000000000000")
        await self.db.flush()
        
        # Write audit log entry
        await write_audit_log(
            actor_id=actor_id,
            action="RoleRemoved",
            target_entity="UserRole",
            target_id=user_role.user_role_id,
            changed_values={
                "user_id": str(user_id),
                "role_name": role_name,
            },
            obo_by=obo_by,
            timestamp=datetime.now(timezone.utc),
            db=self.db,
        )

    @read_only
    async def list_roles(self) -> list[Role]:
        """
        List all available roles.
        
        Returns:
            List of Role entities
            
        Requirements: 5.1
        """
        stmt = select(Role)
        result = await self.db.execute(stmt)
        return cast(list[Role], result.scalars().all())  # type: ignore[arg-type]  # type: ignore[assignment]

    @read_only
    async def get_user_roles(self, user_id: UUID) -> list[UserRole]:
        """
        Get all roles for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of UserRole entities
            
        Requirements: 5.1
        """
        stmt = select(UserRole).where(UserRole.user_id == user_id)
        result = await self.db.execute(stmt)
        return cast(list[UserRole], result.scalars().all())  # type: ignore[arg-type]  # type: ignore[assignment]

    @transactional(name="assign_privilege")
    async def assign_privilege(
        self, role_name: str, privilege_id: UUID, actor_id: UUID, obo_by: Optional[UUID] = None
    ) -> RolePrivilege:
        """
        Assign a privilege to a role.
        
        Args:
            role_name: Role name
            privilege_id: Privilege ID
            actor_id: User ID of the actor performing the assignment
            obo_by: SuperAdmin user ID if this is an on-behalf-of action (for audit logging)
            
        Returns:
            Created RolePrivilege entity
            
        Raises:
            ValueError: If privilege doesn't exist or already assigned
            
        Requirements: 6.1, 6.2, 6.5, 6.6, 6.7, 6.9, 7.3
        """
        # Verify privilege exists in system set
        privilege = await self.db.get(Privilege, privilege_id)
        if not privilege:
            raise ValueError(f"Privilege {privilege_id} not found")
        
        # Check if already assigned
        stmt = select(RolePrivilege).where(
            RolePrivilege.role_name == role_name,
            RolePrivilege.privilege_id == privilege_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise ValueError(
                f"Privilege {privilege.name} already assigned to role {role_name}"
            )
        
        # Create role privilege
        role_privilege = RolePrivilege(
            role_name=role_name,
            privilege_id=privilege_id,
        )
        self.db.add(role_privilege)
        await self.db.flush()
        
        # Write audit log entry
        await write_audit_log(
            actor_id=actor_id,
            action="PrivilegeAssigned",
            target_entity="RolePrivilege",
            target_id=role_privilege.role_privilege_id,
            changed_values={
                "role_name": role_name,
                "privilege_id": str(privilege_id),
                "privilege_name": privilege.name,
            },
            obo_by=obo_by,
            timestamp=datetime.now(timezone.utc),
            db=self.db,
        )
        
        return role_privilege

    @transactional(name="remove_privilege")
    async def remove_privilege(
        self, role_name: str, privilege_id: UUID, actor_id: UUID, obo_by: Optional[UUID] = None
    ) -> None:
        """
        Remove a privilege from a role.
        
        Args:
            role_name: Role name
            privilege_id: Privilege ID
            actor_id: User ID of the actor performing the removal
            obo_by: SuperAdmin user ID if this is an on-behalf-of action (for audit logging)
            
        Raises:
            ValueError: If privilege not assigned or would leave role with 0 privileges
            
        Requirements: 6.1, 6.2, 6.7, 6.8, 6.9, 7.3
        """
        # Find the role privilege
        stmt = select(RolePrivilege).where(
            RolePrivilege.role_name == role_name,
            RolePrivilege.privilege_id == privilege_id,
        )
        result = await self.db.execute(stmt)
        role_privilege = result.scalar_one_or_none()
        
        if not role_privilege:
            raise ValueError(f"Privilege not assigned to role {role_name}")
        
        # Check if this is the last privilege for the role (only count non-deleted)
        stmt = select(RolePrivilege).where(
            RolePrivilege.role_name == role_name,
            RolePrivilege.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        active_privileges = result.scalars().all()
        
        if len(active_privileges) <= 1:
            raise ValueError(
                f"Cannot remove the last privilege from role {role_name}"
            )
        
        # Soft delete
        role_privilege.deleted_at = datetime.now(timezone.utc)
        role_privilege.deleted_by = actor_id
        await self.db.flush()
        
        # Get privilege details for audit log
        privilege = await self.db.get(Privilege, privilege_id)
        
        # Write audit log entry
        await write_audit_log(
            actor_id=actor_id,
            action="PrivilegeRemoved",
            target_entity="RolePrivilege",
            target_id=role_privilege.role_privilege_id,
            changed_values={
                "role_name": role_name,
                "privilege_id": str(privilege_id),
                "privilege_name": privilege.name if privilege else None,
            },
            obo_by=obo_by,
            timestamp=datetime.now(timezone.utc),
            db=self.db,
        )

    @read_only
    async def list_privileges(self) -> list[Privilege]:
        """
        List all available privileges.
        
        Returns:
            List of Privilege entities
            
        Requirements: 6.1
        """
        stmt = select(Privilege)
        result = await self.db.execute(stmt)
        return cast(list[Privilege], result.scalars().all())  # type: ignore[arg-type]  # type: ignore[assignment]

    @read_only
    async def get_role_privileges(self, role_name: str) -> list[RolePrivilege]:
        """
        Get all privileges for a role.
        
        Args:
            role_name: Role name
            
        Returns:
            List of RolePrivilege entities (non-deleted only)
            
        Requirements: 6.1
        """
        stmt = select(RolePrivilege).where(
            RolePrivilege.role_name == role_name,
            RolePrivilege.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return cast(list[RolePrivilege], result.scalars().all())  # type: ignore[arg-type]  # type: ignore[assignment]
