"""Add enum types for domain events and other models

Revision ID: 007
Revises: 006
Create Date: 2026-05-30 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create EventStatus enum for domain_events table
    op.execute("""
        CREATE TYPE eventstatus AS ENUM (
            'Pending',
            'Processed',
            'Failed'
        )
    """)


def downgrade() -> None:
    # Drop EventStatus enum
    op.execute("DROP TYPE IF EXISTS eventstatus")
