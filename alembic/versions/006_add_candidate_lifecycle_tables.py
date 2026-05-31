"""Add candidate-lifecycle tables

Revision ID: 006
Revises: 005
Create Date: 2026-05-30 07:28:21.408539

Creates all candidate-lifecycle tables:
- candidates: candidate profiles with encrypted PII
- resumes: uploaded resume files and parsed data
- candidate_job_history: job history extracted from resumes
- domains: skill domain/category taxonomy
- skills: individual skills within domains
- candidate_skills: candidate skill proficiency and experience
- unmatched_skill_reviews: flagged unmatched skills for manual review
- job_profiles: job category definitions
- job_profile_skills: skills required/desired for job profiles
- job_postings: public-facing job posting details
- job_requisitions: open positions within organization
- requisition_required_skills: skills required for job requisitions
- candidate_requisitions: candidate-requisition associations
- data_subject_access_requests: GDPR DSAR records
- organization_retention_policies: data retention configuration per organization

Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 6.4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # candidates table
    # ------------------------------------------------------------------
    op.create_table(
        'candidates',
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(512), nullable=False),
        sa.Column('name_hash', sa.String(64), nullable=False),
        sa.Column('email', sa.String(512), nullable=False),
        sa.Column('email_hash', sa.String(64), nullable=False),
        sa.Column('phone', sa.String(200), nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('global_status', sa.Enum('Active', 'Interviewing', 'Expired', 'Ineligible', 'Deleted', name='globalstatus'), nullable=False, server_default='Active'),
        sa.Column('ineligibility_reason', sa.String(1000), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], name=op.f('candidates_organization_id_fkey')),
        sa.PrimaryKeyConstraint('candidate_id', name=op.f('candidates_pkey')),
        sa.UniqueConstraint('organization_id', 'email_hash', name='uq_candidates_org_email'),
    )
    op.create_index('idx_candidates_org_status', 'candidates', ['organization_id', 'global_status'], postgresql_where='deleted_at IS NULL')
    op.create_index('idx_candidates_name_hash', 'candidates', ['organization_id', 'name_hash'], postgresql_where='deleted_at IS NULL')

    # ------------------------------------------------------------------
    # resumes table
    # ------------------------------------------------------------------
    op.create_table(
        'resumes',
        sa.Column('resume_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('storage_location', sa.String(1024), nullable=False),
        sa.Column('mime_type', sa.String(128), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('uploaded_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('parse_status', sa.Enum('Pending', 'Completed', 'Failed', name='parsestatus'), nullable=False, server_default='Pending'),
        sa.Column('parsed_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidate_id'], name=op.f('resumes_candidate_id_fkey')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], name=op.f('resumes_organization_id_fkey')),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.user_id'], name=op.f('resumes_uploaded_by_user_id_fkey')),
        sa.PrimaryKeyConstraint('resume_id', name=op.f('resumes_pkey')),
    )
    op.create_index('idx_resumes_candidate', 'resumes', ['candidate_id'], postgresql_where='deleted_at IS NULL')

    # ------------------------------------------------------------------
    # candidate_job_history table
    # ------------------------------------------------------------------
    op.create_table(
        'candidate_job_history',
        sa.Column('candidate_job_history_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_name', sa.String(200), nullable=False),
        sa.Column('job_title', sa.String(200), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('description', sa.String(2000), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidate_id'], name=op.f('candidate_job_history_candidate_id_fkey')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], name=op.f('candidate_job_history_organization_id_fkey')),
        sa.PrimaryKeyConstraint('candidate_job_history_id', name=op.f('candidate_job_history_pkey')),
    )

    # ------------------------------------------------------------------
    # domains table
    # ------------------------------------------------------------------
    op.create_table(
        'domains',
        sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('domain_id', name=op.f('domains_pkey')),
    )

    # ------------------------------------------------------------------
    # skills table
    # ------------------------------------------------------------------
    op.create_table(
        'skills',
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['domain_id'], ['domains.domain_id'], name=op.f('skills_domain_id_fkey')),
        sa.PrimaryKeyConstraint('skill_id', name=op.f('skills_pkey')),
        sa.UniqueConstraint('domain_id', 'name', name='uq_skills_domain_name'),
    )

    # ------------------------------------------------------------------
    # candidate_skills table
    # ------------------------------------------------------------------
    op.create_table(
        'candidate_skills',
        sa.Column('candidate_skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('proficiency_rank', sa.Integer(), nullable=False),
        sa.Column('years_of_experience', sa.Integer(), nullable=False),
        sa.Column('source', sa.Enum('Manual', 'Parsed', 'Inferred', name='skillsource'), nullable=False, server_default='Manual'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint('proficiency_rank >= 1 AND proficiency_rank <= 5', name='ck_candidate_skills_proficiency_rank'),
        sa.CheckConstraint('years_of_experience >= 0 AND years_of_experience <= 50', name='ck_candidate_skills_years_of_experience'),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], name=op.f('candidate_skills_skill_id_fkey')),
        sa.PrimaryKeyConstraint('candidate_skill_id', name=op.f('candidate_skills_pkey')),
        sa.UniqueConstraint('candidate_id', 'skill_id', name='uq_candidate_skills_candidate_skill'),
    )

    # ------------------------------------------------------------------
    # unmatched_skill_reviews table
    # ------------------------------------------------------------------
    op.create_table(
        'unmatched_skill_reviews',
        sa.Column('unmatched_skill_review_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('unmatched_skill_name', sa.String(200), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('unmatched_skill_review_id', name=op.f('unmatched_skill_reviews_pkey')),
    )

    # ------------------------------------------------------------------
    # job_profiles table
    # ------------------------------------------------------------------
    op.create_table(
        'job_profiles',
        sa.Column('job_profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], name=op.f('job_profiles_organization_id_fkey')),
        sa.PrimaryKeyConstraint('job_profile_id', name=op.f('job_profiles_pkey')),
    )

    # ------------------------------------------------------------------
    # job_profile_skills table
    # ------------------------------------------------------------------
    op.create_table(
        'job_profile_skills',
        sa.Column('job_profile_skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('designation', sa.Enum('Required', 'Desired', name='skilldesignation'), nullable=False, server_default='Required'),
        sa.Column('required_proficiency_rank', sa.Integer(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint('required_proficiency_rank >= 1 AND required_proficiency_rank <= 5', name='ck_job_profile_skills_proficiency_rank'),
        sa.ForeignKeyConstraint(['job_profile_id'], ['job_profiles.job_profile_id'], name=op.f('job_profile_skills_job_profile_id_fkey')),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], name=op.f('job_profile_skills_skill_id_fkey')),
        sa.PrimaryKeyConstraint('job_profile_skill_id', name=op.f('job_profile_skills_pkey')),
        sa.UniqueConstraint('job_profile_id', 'skill_id', name='uq_job_profile_skills'),
    )

    # ------------------------------------------------------------------
    # job_postings table
    # ------------------------------------------------------------------
    op.create_table(
        'job_postings',
        sa.Column('job_posting_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('work_locations', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('salary_min', sa.Numeric(12, 2), nullable=True),
        sa.Column('salary_max', sa.Numeric(12, 2), nullable=True),
        sa.Column('salary_currency', sa.String(3), nullable=True),
        sa.Column('sourcing_channel', sa.String(100), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['job_profile_id'], ['job_profiles.job_profile_id'], name=op.f('job_postings_job_profile_id_fkey')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], name=op.f('job_postings_organization_id_fkey')),
        sa.PrimaryKeyConstraint('job_posting_id', name=op.f('job_postings_pkey')),
    )
    op.create_index('idx_job_postings_salary', 'job_postings', ['organization_id', 'salary_min', 'salary_max'], postgresql_where='deleted_at IS NULL')

    # ------------------------------------------------------------------
    # job_requisitions table
    # ------------------------------------------------------------------
    op.create_table(
        'job_requisitions',
        sa.Column('job_requisition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('external_requisition_id', sa.String(255), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('department', sa.String(100), nullable=False),
        sa.Column('location', sa.String(200), nullable=False),
        sa.Column('hiring_manager_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('Open', 'OnHold', 'Closed', 'Cancelled', name='requisitionstatus'), nullable=False, server_default='Open'),
        sa.Column('description', sa.String(5000), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['hiring_manager_user_id'], ['users.user_id'], name=op.f('job_requisitions_hiring_manager_user_id_fkey')),
        sa.ForeignKeyConstraint(['job_profile_id'], ['job_profiles.job_profile_id'], name=op.f('job_requisitions_job_profile_id_fkey')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], name=op.f('job_requisitions_organization_id_fkey')),
        sa.PrimaryKeyConstraint('job_requisition_id', name=op.f('job_requisitions_pkey')),
    )

    # ------------------------------------------------------------------
    # requisition_required_skills table
    # ------------------------------------------------------------------
    op.create_table(
        'requisition_required_skills',
        sa.Column('requisition_required_skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_requisition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('required_proficiency_rank', sa.Integer(), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint('required_proficiency_rank >= 1 AND required_proficiency_rank <= 5', name='ck_requisition_required_skills_proficiency_rank'),
        sa.CheckConstraint('weight >= 1 AND weight <= 10', name='ck_requisition_required_skills_weight'),
        sa.ForeignKeyConstraint(['job_requisition_id'], ['job_requisitions.job_requisition_id'], name=op.f('requisition_required_skills_job_requisition_id_fkey')),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id'], name=op.f('requisition_required_skills_skill_id_fkey')),
        sa.PrimaryKeyConstraint('requisition_required_skill_id', name=op.f('requisition_required_skills_pkey')),
        sa.UniqueConstraint('job_requisition_id', 'skill_id', name='uq_requisition_required_skills_requisition_skill'),
    )

    # ------------------------------------------------------------------
    # candidate_requisitions table
    # ------------------------------------------------------------------
    op.create_table(
        'candidate_requisitions',
        sa.Column('candidate_requisition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_requisition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidate_id'], name=op.f('candidate_requisitions_candidate_id_fkey')),
        sa.ForeignKeyConstraint(['job_requisition_id'], ['job_requisitions.job_requisition_id'], name=op.f('candidate_requisitions_job_requisition_id_fkey')),
        sa.PrimaryKeyConstraint('candidate_requisition_id', name=op.f('candidate_requisitions_pkey')),
        sa.UniqueConstraint('candidate_id', 'job_requisition_id', name='uq_candidate_requisition'),
    )

    # ------------------------------------------------------------------
    # data_subject_access_requests table
    # ------------------------------------------------------------------
    op.create_table(
        'data_subject_access_requests',
        sa.Column('dsar_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_type', sa.Enum('Access', 'Erasure', name='dsarrequesttype'), nullable=False),
        sa.Column('status', sa.Enum('Pending', 'Completed', 'Denied', name='dsarstatus'), nullable=False, server_default='Pending'),
        sa.Column('requested_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('denial_reason', sa.String(1000), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('dsar_id', name=op.f('data_subject_access_requests_pkey')),
    )

    # ------------------------------------------------------------------
    # organization_retention_policies table
    # ------------------------------------------------------------------
    op.create_table(
        'organization_retention_policies',
        sa.Column('organization_retention_policy_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_data_retention_days', sa.Integer(), nullable=False, server_default='730'),
        sa.Column('resume_retention_days', sa.Integer(), nullable=False, server_default='365'),
        sa.Column('audit_log_retention_days', sa.Integer(), nullable=False, server_default='2555'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], name=op.f('organization_retention_policies_organization_id_fkey')),
        sa.PrimaryKeyConstraint('organization_retention_policy_id', name=op.f('organization_retention_policies_pkey')),
        sa.UniqueConstraint('organization_id', name='uq_organization_retention_policy'),
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign key dependencies)
    op.drop_table('organization_retention_policies')
    op.drop_table('data_subject_access_requests')
    op.drop_table('candidate_requisitions')
    op.drop_table('requisition_required_skills')
    op.drop_table('job_requisitions')
    op.drop_index('idx_job_postings_salary', table_name='job_postings')
    op.drop_table('job_postings')
    op.drop_table('job_profile_skills')
    op.drop_table('job_profiles')
    op.drop_table('unmatched_skill_reviews')
    op.drop_table('candidate_skills')
    op.drop_table('skills')
    op.drop_table('domains')
    op.drop_table('candidate_job_history')
    op.drop_index('idx_resumes_candidate', table_name='resumes')
    op.drop_table('resumes')
    op.drop_index('idx_candidates_name_hash', table_name='candidates')
    op.drop_index('idx_candidates_org_status', table_name='candidates')
    op.drop_table('candidates')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS skilldesignation")
    op.execute("DROP TYPE IF EXISTS dsarstatus")
    op.execute("DROP TYPE IF EXISTS dsarrequesttype")
    op.execute("DROP TYPE IF EXISTS requisitionstatus")
    op.execute("DROP TYPE IF EXISTS parsestatus")
    op.execute("DROP TYPE IF EXISTS globalstatus")
