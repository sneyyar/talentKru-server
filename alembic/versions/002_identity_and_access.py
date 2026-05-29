"""Identity and Access module tables.

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:00.000000

Creates:
- users table (with email encryption support, audit fields, version)
- password_history table (with index on user_id, created_at)
- refresh_tokens table (with token rotation tracking)
- revoked_tokens table (with jti index for revocation checks)
- roles table (system-managed role definitions)
- user_roles table (user-to-role assignments with audit)
- privileges table (granular permissions)
- role_privileges table (role-to-privilege assignments with audit)
- invitation_tokens table (single-use invitation tokens)
- password_reset_tokens table (single-use password reset tokens)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users table
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.organization_id"),
            nullable=True,
        ),
        sa.Column("email", sa.String(512), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("given_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="PendingInvitation",
        ),
        sa.Column(
            "manager_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=True,
        ),
        sa.Column("hashed_password", sa.String(60), nullable=True),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en-US"),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id",
            "email_hash",
            name="uq_users_org_email",
        ),
    )
    op.create_index("idx_users_org_id", "users", ["organization_id"])
    op.create_index("idx_users_email_hash", "users", ["email_hash"])

    # ------------------------------------------------------------------
    # password_history table
    # ------------------------------------------------------------------
    op.create_table(
        "password_history",
        sa.Column(
            "password_history_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("hashed_password", sa.String(60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "idx_password_history_user",
        "password_history",
        ["user_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # refresh_tokens table
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "refresh_token_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "replaced_by_token_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("refresh_tokens.refresh_token_id"),
            nullable=True,
        ),
    )
    op.create_index("idx_refresh_tokens_user", "refresh_tokens", ["user_id"])

    # ------------------------------------------------------------------
    # revoked_tokens table
    # ------------------------------------------------------------------
    op.create_table(
        "revoked_tokens",
        sa.Column(
            "revoked_token_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("jti", sa.String(36), nullable=False, unique=True),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(64), nullable=True),
    )
    op.create_index("idx_revoked_tokens_jti", "revoked_tokens", ["jti"])
    op.create_index("idx_revoked_tokens_expires", "revoked_tokens", ["expires_at"])

    # ------------------------------------------------------------------
    # roles table
    # ------------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("role_name", sa.String(64), primary_key=True),
        sa.Column("description", sa.String(256), nullable=True),
    )

    # ------------------------------------------------------------------
    # user_roles table
    # ------------------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column(
            "user_role_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "role_name",
            sa.String(64),
            sa.ForeignKey("roles.role_name"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("user_id", "role_name", name="uq_user_roles"),
    )

    # ------------------------------------------------------------------
    # privileges table
    # ------------------------------------------------------------------
    op.create_table(
        "privileges",
        sa.Column(
            "privilege_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("resource_category", sa.String(64), nullable=False),
    )

    # ------------------------------------------------------------------
    # role_privileges table
    # ------------------------------------------------------------------
    op.create_table(
        "role_privileges",
        sa.Column(
            "role_privilege_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "role_name",
            sa.String(64),
            sa.ForeignKey("roles.role_name"),
            nullable=False,
        ),
        sa.Column(
            "privilege_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("privileges.privilege_id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint(
            "role_name",
            "privilege_id",
            name="uq_role_privileges",
        ),
    )

    # ------------------------------------------------------------------
    # invitation_tokens table
    # ------------------------------------------------------------------
    op.create_table(
        "invitation_tokens",
        sa.Column(
            "invitation_token_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_used",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # ------------------------------------------------------------------
    # password_reset_tokens table
    # ------------------------------------------------------------------
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "password_reset_token_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_used",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("invitation_tokens")
    op.drop_table("role_privileges")
    op.drop_table("privileges")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("idx_revoked_tokens_expires", table_name="revoked_tokens")
    op.drop_index("idx_revoked_tokens_jti", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    op.drop_index("idx_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("idx_password_history_user", table_name="password_history")
    op.drop_table("password_history")
    op.drop_index("idx_users_email_hash", table_name="users")
    op.drop_index("idx_users_org_id", table_name="users")
    op.drop_table("users")
