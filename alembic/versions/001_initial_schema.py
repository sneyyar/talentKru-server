"""Initial schema: organizations and domain_events tables.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

Creates:
- PostgreSQL extensions: vector, uuid-ossp
- organizations table (with audit fields, version, allowed_origins, feature_flags)
- domain_events table (with status and event_type indexes)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # PostgreSQL extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ------------------------------------------------------------------
    # organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("secondary_color", sa.String(7), nullable=True),
        sa.Column("terms_url", sa.String(512), nullable=True),
        sa.Column("contact_name", sa.String(128), nullable=True),
        sa.Column("contact_email", sa.String(254), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column(
            "feature_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "shard_id",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "allowed_origins",
            postgresql.ARRAY(sa.String(253)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
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
        # Constraints
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    # Index on slug for fast lookups (unique constraint already creates one,
    # but an explicit named index makes intent clear and supports partial queries)
    op.create_index(
        "idx_organizations_slug",
        "organizations",
        ["slug"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # domain_events
    # ------------------------------------------------------------------
    op.create_table(
        "domain_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'Pending'"),
        ),
        sa.Column("correlation_id", sa.String(64), nullable=True),
    )

    # Indexes for common query patterns (retry job, event type filtering)
    op.create_index(
        "idx_domain_events_status",
        "domain_events",
        ["status"],
    )
    op.create_index(
        "idx_domain_events_event_type",
        "domain_events",
        ["event_type"],
    )


def downgrade() -> None:
    # Drop indexes first, then tables, then extensions
    op.drop_index("idx_domain_events_event_type", table_name="domain_events")
    op.drop_index("idx_domain_events_status", table_name="domain_events")
    op.drop_table("domain_events")

    op.drop_index("idx_organizations_slug", table_name="organizations")
    op.drop_table("organizations")

    # Note: extensions are intentionally NOT dropped in downgrade to avoid
    # breaking other objects that may depend on them (e.g., vector columns
    # in other tables created by later migrations).
