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
    # Add check constraint for domain_events status column
    op.execute("""
        ALTER TABLE domain_events
        ADD CONSTRAINT ck_domain_events_status
        CHECK (status IN ('PENDING', 'PROCESSED', 'FAILED'))
    """)


def downgrade() -> None:
    # Drop check constraint
    op.execute("ALTER TABLE domain_events DROP CONSTRAINT ck_domain_events_status")
