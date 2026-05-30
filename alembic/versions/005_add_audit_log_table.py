"""Add audit_log table for tracking user actions and system events.

Revision ID: 005
Revises: 004
Create Date: 2025-01-01 00:00:00.000000

Creates:
- audit_logs table with indexes on actor_id, org_id, action, and timestamp
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # audit_logs table
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column(
            "audit_log_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_entity", sa.String(128), nullable=True),
        sa.Column("target_id", sa.String(255), nullable=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("changed_values", postgresql.JSONB, nullable=True),
        sa.Column("obo_by", sa.String(255), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index("idx_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_index("idx_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_org_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor_id", table_name="audit_logs")
    op.drop_table("audit_logs")
