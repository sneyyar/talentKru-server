"""Seed roles and default privilege mappings.

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:00.000000

Seeds:
- 7 roles: SuperAdministrator, Administrator, Recruiter, HiringManager, CommitteeMember, HRManager, Interviewer
- Default privileges with role assignments
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

# Define roles
ROLES = [
    ("SuperAdministrator", "Cross-tenant platform administration"),
    ("Administrator", "Organization-level user and configuration management"),
    ("Recruiter", "Candidate and requisition management"),
    ("HiringManager", "Interview journey stage transitions"),
    ("CommitteeMember", "Panel review participation"),
    ("HRManager", "Reporting and analytics access"),
    ("Interviewer", "Interview slot management and feedback"),
]

# Define privileges with their default role assignments
PRIVILEGES = [
    ("users:read", "users", "Read user information", ["Administrator", "SuperAdministrator"]),
    ("users:write", "users", "Create and update users", ["Administrator", "SuperAdministrator"]),
    ("roles:assign", "rbac", "Assign roles to users", ["Administrator", "SuperAdministrator"]),
    ("privileges:manage", "rbac", "Manage privilege assignments", ["SuperAdministrator"]),
    ("candidates:write", "candidates", "Create and update candidates", ["Recruiter"]),
    ("requisitions:write", "requisitions", "Create and update requisitions", ["Recruiter"]),
    ("journeys:transition", "journeys", "Transition interview journeys between stages", ["Recruiter", "HiringManager"]),
    ("interviews:feedback", "interviews", "Submit interview feedback", ["Interviewer"]),
    ("reports:read", "reporting", "Access reporting and analytics", ["Administrator", "HRManager"]),
]

def upgrade() -> None:
    # Insert roles
    roles_table = sa.table(
        "roles",
        sa.column("role_name", sa.String),
        sa.column("description", sa.String),
    )
    
    for role_name, description in ROLES:
        op.execute(
            roles_table.insert().values(
                role_name=role_name,
                description=description,
            )
        )

    # Insert privileges
    privileges_table = sa.table(
        "privileges",
        sa.column("privilege_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("resource_category", sa.String),
    )
    
    privilege_ids = {}
    for priv_name, resource_category, description, _ in PRIVILEGES:
        priv_id = str(uuid.uuid4())
        privilege_ids[priv_name] = priv_id
        op.execute(
            privileges_table.insert().values(
                privilege_id=priv_id,
                name=priv_name,
                description=description,
                resource_category=resource_category,
            )
        )

    # Insert role-privilege mappings
    role_privileges_table = sa.table(
        "role_privileges",
        sa.column("role_privilege_id", postgresql.UUID(as_uuid=True)),
        sa.column("role_name", sa.String),
        sa.column("privilege_id", postgresql.UUID(as_uuid=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    for priv_name, _, _, role_names in PRIVILEGES:
        for role_name in role_names:
            op.execute(
                role_privileges_table.insert().values(
                    role_privilege_id=str(uuid.uuid4()),
                    role_name=role_name,
                    privilege_id=privilege_ids[priv_name],
                    created_at=now,
                    updated_at=now,
                )
            )

def downgrade() -> None:
    # Delete role-privilege mappings
    op.execute("DELETE FROM role_privileges")
    
    # Delete privileges
    op.execute("DELETE FROM privileges")
    
    # Delete roles
    op.execute("DELETE FROM roles")
