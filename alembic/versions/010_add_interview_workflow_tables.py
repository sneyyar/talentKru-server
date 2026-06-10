"""Add interview workflow tables

Revision ID: 010
Revises: 009
Create Date: 2026-06-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to interview_journeys (created in migration 008)
    # Using additive approach (ALTER TABLE) to preserve data and enable safe rollback
    
    # Add new columns (all nullable initially to avoid conflicts with existing data)
    op.add_column('interview_journeys', 
        sa.Column('journey_public_id', sa.String(64), nullable=True))
    op.add_column('interview_journeys', 
        sa.Column('job_requisition_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('interview_journeys', 
        sa.Column('current_stage', sa.String(50), nullable=True, server_default='SOURCED'))
    op.add_column('interview_journeys', 
        sa.Column('current_stage_status', sa.String(50), nullable=True))
    op.add_column('interview_journeys', 
        sa.Column('offer_extended_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('interview_journeys', 
        sa.Column('offer_responded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('interview_journeys', 
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()))
    
    # Update overall_status column width if needed (change from VARCHAR(20) to VARCHAR(50))
    op.alter_column('interview_journeys', 'overall_status',
        existing_type=sa.String(20),
        type_=sa.String(50))
    
    # Create unique constraint for journey_public_id
    op.create_unique_constraint('uk_journey_public_id', 'interview_journeys', ['journey_public_id'])
    
    # Create unique constraint for candidate_id + job_requisition_id
    op.create_unique_constraint('uk_journey_candidate_req', 'interview_journeys', 
        ['candidate_id', 'job_requisition_id'])
    
    # Add check constraints
    op.create_check_constraint(
        'ck_interview_journeys_current_stage',
        'interview_journeys',
        "current_stage IS NULL OR current_stage IN ('SOURCED', 'RECRUITER_SCREEN', 'MANAGER_SCREEN', "
        "'LOOP_INTERVIEW', 'PANEL_REVIEW', 'OFFER_PENDING', 'OFFER_EXTENDED', 'REJECTED', 'OFFER_DECLINED', "
        "'OFFER_ACCEPTED', 'WITHDRAWN')"
    )
    op.create_check_constraint(
        'ck_interview_journeys_stage_status',
        'interview_journeys',
        "current_stage_status IS NULL OR current_stage_status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETE')"
    )
    
    # Create new indexes
    op.create_index('idx_journeys_org_stage', 'interview_journeys', ['organization_id', 'current_stage'], schema=None)
    op.create_index('idx_journeys_candidate_stage', 'interview_journeys', ['candidate_id', 'current_stage'], schema=None)

    # interview_journey_stage_history
    op.create_table(
        'interview_journey_stage_history',
        sa.Column('interview_journey_stage_history_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_journey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_stage', sa.String(50), nullable=False),
        sa.Column('to_stage', sa.String(50), nullable=False),
        sa.Column('changed_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('comments', sa.String(2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('interview_journey_stage_history_id'),
        schema=None,
    )
    op.create_index('idx_stage_history_journey', 'interview_journey_stage_history', ['interview_journey_id'], schema=None)

    # candidate_interview_journeys
    op.create_table(
        'candidate_interview_journeys',
        sa.Column('candidate_interview_journey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_journey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id_encrypted', sa.String(512), nullable=True),
        sa.Column('interview_journey_id_encrypted', sa.String(512), nullable=True),
        sa.Column('is_encrypted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('associated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('candidate_interview_journey_id'),
        schema=None,
    )

    # interview_slots
    op.create_table(
        'interview_slots',
        sa.Column('interview_slot_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_journey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='SCHEDULED'),
        sa.Column('invitation_status', sa.String(50), nullable=True),
        sa.Column('attendance_status', sa.String(50), nullable=False, server_default='UNKNOWN'),
        sa.Column('interviewer_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('feedback_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint("type IN ('MANAGER', 'TECHNICAL', 'BEHAVIORAL', 'PANEL')", name='ck_interview_slots_type'),
        sa.CheckConstraint(
            "status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETE', 'CANCELLED')",
            name='ck_interview_slots_status',
        ),
        sa.CheckConstraint(
            "invitation_status IS NULL OR invitation_status IN ('PENDING', 'ACCEPTED', 'DECLINED')",
            name='ck_interview_slots_invitation_status',
        ),
        sa.CheckConstraint(
            "attendance_status IN ('UNKNOWN', 'ATTENDED', 'NO_SHOW')",
            name='ck_interview_slots_attendance_status',
        ),
        sa.PrimaryKeyConstraint('interview_slot_id'),
        schema=None,
    )
    op.create_index('idx_slots_journey', 'interview_slots', ['interview_journey_id'], schema=None)
    op.create_index('idx_slots_interviewer', 'interview_slots', ['interviewer_user_id'], schema=None)

    # interviewer_preferences
    op.create_table(
        'interviewer_preferences',
        sa.Column('interviewer_preference_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interviewer_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('allowed_interview_types', postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column('max_interviews_per_day', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('max_interviews_per_week', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('working_hours', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint('max_interviews_per_day >= 1 AND max_interviews_per_day <= 20', name='ck_max_per_day'),
        sa.CheckConstraint('max_interviews_per_week >= 1 AND max_interviews_per_week <= 100', name='ck_max_per_week'),
        sa.PrimaryKeyConstraint('interviewer_preference_id'),
        sa.UniqueConstraint('interviewer_user_id', 'organization_id', name='uk_interviewer_org'),
        schema=None,
    )

    # interview_feedback
    op.create_table(
        'interview_feedback',
        sa.Column('interview_feedback_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_slot_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(50), nullable=False, server_default='MANUAL'),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('competency_ratings', postgresql.JSON, nullable=True),
        sa.Column('narrative', sa.String(5000), nullable=True),
        sa.Column('hiring_recommendation', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint("type IN ('MANUAL', 'AI_GENERATED')", name='ck_feedback_type'),
        sa.CheckConstraint("status IN ('DRAFT', 'SUBMITTED')", name='ck_feedback_status'),
        sa.CheckConstraint(
            "hiring_recommendation IS NULL OR hiring_recommendation IN "
            "('STRONG_YES', 'YES', 'NEUTRAL', 'NO', 'STRONG_NO')",
            name='ck_hiring_recommendation',
        ),
        sa.PrimaryKeyConstraint('interview_feedback_id'),
        schema=None,
    )
    op.create_index('idx_feedback_slot', 'interview_feedback', ['interview_slot_id'], schema=None)

    # questionnaires
    op.create_table(
        'questionnaires',
        sa.Column('questionnaire_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('questions_yaml', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('questionnaire_id'),
        sa.Index('ix_questionnaires_organization_id', 'organization_id'),
        schema=None,
    )

    # job_requisition_questionnaires
    op.create_table(
        'job_requisition_questionnaires',
        sa.Column('job_requisition_questionnaire_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_requisition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('questionnaire_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('job_requisition_questionnaire_id'),
        sa.UniqueConstraint('job_requisition_id', 'questionnaire_id', name='uk_req_questionnaire'),
        schema=None,
    )

    # candidate_questionnaire_responses
    op.create_table(
        'candidate_questionnaire_responses',
        sa.Column('candidate_questionnaire_response_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('questionnaire_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint("status IN ('DRAFT', 'INCOMPLETE', 'SUBMITTED')", name='ck_response_status'),
        sa.PrimaryKeyConstraint('candidate_questionnaire_response_id'),
        sa.UniqueConstraint('candidate_id', 'questionnaire_id', name='uk_candidate_questionnaire'),
        schema=None,
    )

    # candidate_questionnaire_answers
    op.create_table(
        'candidate_questionnaire_answers',
        sa.Column('candidate_questionnaire_answer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_questionnaire_response_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_id', sa.String(500), nullable=False),
        sa.Column('answer', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('candidate_questionnaire_answer_id'),
        sa.UniqueConstraint('candidate_questionnaire_response_id', 'question_id', name='uk_response_question'),
        schema=None,
    )

    # candidate_portal_tokens
    op.create_table(
        'candidate_portal_tokens',
        sa.Column('candidate_portal_token_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('candidate_portal_token_id'),
        sa.Index('idx_portal_tokens_candidate', 'candidate_id'),
        schema=None,
    )

    # organization_email_configs
    op.create_table(
        'organization_email_configs',
        sa.Column('organization_email_config_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('email_notifications_enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('smtp_host', sa.String(253), nullable=True),
        sa.Column('smtp_port', sa.Integer, nullable=True),
        sa.Column('smtp_username', sa.String(254), nullable=True),
        sa.Column('smtp_password', sa.String(512), nullable=True),
        sa.Column('smtp_use_tls', sa.Boolean, nullable=True),
        sa.Column('third_party_api_key', sa.String(512), nullable=True),
        sa.Column('third_party_provider_region', sa.String(100), nullable=True),
        sa.Column('from_address', sa.String(254), nullable=False),
        sa.Column('from_name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint("provider_type IN ('SMTP', 'SENDGRID', 'SES')", name='ck_provider_type'),
        sa.PrimaryKeyConstraint('organization_email_config_id'),
        schema=None,
    )

    # system_settings
    op.create_table(
        'system_settings',
        sa.Column('setting_key', sa.String(500), nullable=False),
        sa.Column('setting_value', sa.String(2000), nullable=False),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('setting_key'),
        schema=None,
    )

    # candidate_availability_slots
    op.create_table(
        'candidate_availability_slots',
        sa.Column('candidate_availability_slot_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_type', sa.String(50), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("interview_type IN ('RECRUITER_SCREEN', 'MANAGER_SCREEN', 'LOOP_INTERVIEW')", name='ck_interview_type'),
        sa.CheckConstraint("status IN ('ACTIVE', 'CANCELLED')", name='ck_availability_status'),
        sa.PrimaryKeyConstraint('candidate_availability_slot_id'),
        schema=None,
    )

    # notification_templates
    op.create_table(
        'notification_templates',
        sa.Column('notification_template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('body_template', sa.String(5000), nullable=False),
        sa.Column('is_enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('locale', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('notification_template_id'),
        sa.UniqueConstraint('organization_id', 'event_type', 'locale', name='uk_template_event_locale'),
        schema=None,
    )

    # notification_records
    op.create_table(
        'notification_records',
        sa.Column('notification_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('recipient_email', sa.String(254), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'DELIVERED', 'RETRYING', 'PERMANENTLY_FAILED')",
            name='ck_notification_status',
        ),
        sa.PrimaryKeyConstraint('notification_record_id'),
        schema=None,
    )

    # candidate_feedback_surveys
    op.create_table(
        'candidate_feedback_surveys',
        sa.Column('candidate_feedback_survey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_journey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('survey_token_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('first_reminder_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('DRAFT', 'SENT', 'COMPLETED', 'EXPIRED')", name='ck_survey_status'),
        sa.PrimaryKeyConstraint('candidate_feedback_survey_id'),
        sa.UniqueConstraint('interview_journey_id', name='uk_survey_journey'),
        schema=None,
    )

    # candidate_feedback_survey_tokens
    op.create_table(
        'candidate_feedback_survey_tokens',
        sa.Column('candidate_feedback_survey_token_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_feedback_survey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(128), nullable=False, unique=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('candidate_feedback_survey_token_id'),
        schema=None,
    )

    # candidate_feedback_survey_questions
    op.create_table(
        'candidate_feedback_survey_questions',
        sa.Column('candidate_feedback_survey_question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.String(500), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('is_required', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("display_order >= 1 AND display_order <= 10", name='ck_display_order'),
        sa.CheckConstraint(
            "category IN ('APPLICATION', 'RECRUITER_EXPERIENCE', 'HIRING_MANAGER_EXPERIENCE', "
            "'LOOP_INTERVIEW_EXPERIENCE', 'OFFER_EXPERIENCE')",
            name='ck_category',
        ),
        sa.PrimaryKeyConstraint('candidate_feedback_survey_question_id'),
        schema=None,
    )

    # candidate_feedback_survey_responses
    op.create_table(
        'candidate_feedback_survey_responses',
        sa.Column('candidate_feedback_survey_response_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_feedback_survey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('additional_comments', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('candidate_feedback_survey_response_id'),
        schema=None,
    )

    # candidate_feedback_survey_answers
    op.create_table(
        'candidate_feedback_survey_answers',
        sa.Column('candidate_feedback_survey_answer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_feedback_survey_response_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_feedback_survey_question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint('rating >= 0 AND rating <= 10', name='ck_rating'),
        sa.PrimaryKeyConstraint('candidate_feedback_survey_answer_id'),
        schema=None,
    )

    # survey_feedback_templates
    op.create_table(
        'survey_feedback_templates',
        sa.Column('survey_feedback_template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_type', sa.String(50), nullable=False),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('body_template', sa.Text, nullable=False),
        sa.Column('is_enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint(
            "template_type IN ('initial_survey_invitation', 'survey_reminder')",
            name='ck_template_type',
        ),
        sa.PrimaryKeyConstraint('survey_feedback_template_id'),
        sa.UniqueConstraint('organization_id', 'template_type', name='uk_survey_template_org_type'),
        schema=None,
    )

    # Seed system_settings with email_notifications_enabled
    # Note: This INSERT will use the current search_path, so it should work in any schema
    # op.execute(
    #     "INSERT INTO system_settings (setting_key, setting_value, description, created_at, updated_at) "
    #     "VALUES ('email_notifications_enabled', 'true', 'Global master switch for all outbound email delivery', "
    #     "NOW(), NOW()) ON CONFLICT DO NOTHING"
    # )


def downgrade() -> None:
    # Safely downgrade by removing only the columns and constraints added in this migration
    # This preserves data from migration 008 for proper rollback
    # (Other tables created in this migration are dropped normally)
    
    # Drop tables in reverse order of creation (all except interview_journeys)
    op.drop_table('survey_feedback_templates', schema=None)
    op.drop_table('candidate_feedback_survey_answers', schema=None)
    op.drop_table('candidate_feedback_survey_responses', schema=None)
    op.drop_table('candidate_feedback_survey_questions', schema=None)
    op.drop_table('candidate_feedback_survey_tokens', schema=None)
    op.drop_table('candidate_feedback_surveys', schema=None)
    op.drop_table('notification_records', schema=None)
    op.drop_table('notification_templates', schema=None)
    op.drop_table('candidate_availability_slots', schema=None)
    op.drop_table('system_settings', schema=None)
    op.drop_table('organization_email_configs', schema=None)
    op.drop_table('candidate_portal_tokens', schema=None)
    op.drop_table('candidate_questionnaire_answers', schema=None)
    op.drop_table('candidate_questionnaire_responses', schema=None)
    op.drop_table('job_requisition_questionnaires', schema=None)
    op.drop_table('questionnaires', schema=None)
    op.drop_table('interview_feedback', schema=None)
    op.drop_table('interviewer_preferences', schema=None)
    op.drop_table('interview_slots', schema=None)
    op.drop_table('candidate_interview_journeys', schema=None)
    op.drop_table('interview_journey_stage_history', schema=None)
    
    # For interview_journeys, use additive rollback (remove only columns added in this migration)
    # This preserves interview_journeys table and its data from migration 008
    
    # Drop new indexes
    op.drop_index('idx_journeys_candidate_stage', table_name='interview_journeys')
    op.drop_index('idx_journeys_org_stage', table_name='interview_journeys')
    
    # Drop check constraints
    op.drop_constraint('ck_interview_journeys_stage_status', 'interview_journeys')
    op.drop_constraint('ck_interview_journeys_current_stage', 'interview_journeys')
    
    # Drop unique constraints
    op.drop_constraint('uk_journey_candidate_req', 'interview_journeys')
    op.drop_constraint('uk_journey_public_id', 'interview_journeys')
    
    # Drop columns in reverse order of addition
    op.drop_column('interview_journeys', 'start_date')
    op.drop_column('interview_journeys', 'offer_responded_at')
    op.drop_column('interview_journeys', 'offer_extended_at')
    op.drop_column('interview_journeys', 'current_stage_status')
    op.drop_column('interview_journeys', 'current_stage')
    op.drop_column('interview_journeys', 'job_requisition_id')
    op.drop_column('interview_journeys', 'journey_public_id')
    
    # Restore overall_status column width (back to VARCHAR(20) from VARCHAR(50))
    op.alter_column('interview_journeys', 'overall_status',
        existing_type=sa.String(50),
        type_=sa.String(20))
