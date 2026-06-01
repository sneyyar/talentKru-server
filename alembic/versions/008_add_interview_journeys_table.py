"""Add interview_journeys table

Revision ID: 008
Revises: 007
Create Date: 2026-05-31 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create interview_journeys table
    op.create_table(
        'interview_journeys',
        sa.Column('interview_journey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('overall_status', sa.String(20), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint("overall_status IN ('ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED')", name='ck_interview_journeys_overall_status'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidate_id'], ),
        sa.PrimaryKeyConstraint('interview_journey_id')
    )
    
    # Create indexes
    op.create_index('ix_interview_journeys_organization_id', 'interview_journeys', ['organization_id'])
    op.create_index('ix_interview_journeys_candidate_id', 'interview_journeys', ['candidate_id'])
    op.create_index('ix_interview_journeys_overall_status', 'interview_journeys', ['overall_status'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_interview_journeys_overall_status', table_name='interview_journeys')
    op.drop_index('ix_interview_journeys_candidate_id', table_name='interview_journeys')
    op.drop_index('ix_interview_journeys_organization_id', table_name='interview_journeys')
    
    # Drop table
    op.drop_table('interview_journeys')
