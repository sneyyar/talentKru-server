"""Add description column to job_postings table.

Revision ID: 009
Revises: 008
Create Date: 2026-06-06 00:00:00.000000

Adds:
- description column to job_postings table (required by JobPosting model)

Requirements: 4.2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add description column to job_postings table
    op.add_column(
        'job_postings',
        sa.Column('description', sa.Text(), nullable=False, server_default='')
    )


def downgrade() -> None:
    # Remove description column from job_postings table
    op.drop_column('job_postings', 'description')
