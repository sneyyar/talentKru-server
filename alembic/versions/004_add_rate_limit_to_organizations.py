"""Add rate_limit_per_minute to organizations table.

Revision ID: 004
Revises: 003
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add rate_limit_per_minute column to organizations table."""
    op.add_column(
        "organizations",
        sa.Column(
            "rate_limit_per_minute",
            sa.Integer(),
            nullable=False,
            server_default="1000",
        ),
    )


def downgrade() -> None:
    """Remove rate_limit_per_minute column from organizations table."""
    op.drop_column("organizations", "rate_limit_per_minute")
