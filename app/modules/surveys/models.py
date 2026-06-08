"""Candidate feedback survey models (Req 9)."""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE, BOOLEAN

from app.base_model import Base, AuditMixin


class SurveyStatus(str, enum.Enum):
    """Candidate feedback survey status."""
    DRAFT = "DRAFT"
    SENT = "SENT"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class SurveyCategory(str, enum.Enum):
    """Survey question category."""
    APPLICATION = "APPLICATION"
    RECRUITER_EXPERIENCE = "RECRUITER_EXPERIENCE"
    HIRING_MANAGER_EXPERIENCE = "HIRING_MANAGER_EXPERIENCE"
    LOOP_INTERVIEW_EXPERIENCE = "LOOP_INTERVIEW_EXPERIENCE"
    OFFER_EXPERIENCE = "OFFER_EXPERIENCE"


class CandidateFeedbackSurvey(Base, AuditMixin):
    """Candidate feedback survey (Req 9.1)."""
    __tablename__ = "candidate_feedback_surveys"

    candidate_feedback_survey_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    interview_journey_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    candidate_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    survey_token_id = Column(UUID_TYPE(as_uuid=True), nullable=True)
    status = Column(String(50), nullable=False, default=SurveyStatus.DRAFT.value)  # type: ignore[var-annotated]
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    first_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("interview_journey_id", name="uk_survey_journey"),
        CheckConstraint("status IN ('DRAFT', 'SENT', 'COMPLETED', 'EXPIRED')", name="ck_survey_status"),
    )


class CandidateFeedbackSurveyToken(Base, AuditMixin):
    """Unique token for survey access (Req 9.2)."""
    __tablename__ = "candidate_feedback_survey_tokens"

    candidate_feedback_survey_token_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_feedback_survey_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    token = Column(String(128), nullable=False, unique=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(BOOLEAN, nullable=False, default=True)


class CandidateFeedbackSurveyQuestion(Base, AuditMixin):
    """Survey question (Req 9.3)."""
    __tablename__ = "candidate_feedback_survey_questions"

    candidate_feedback_survey_question_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    display_order = Column(Integer, nullable=False)
    question_text = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False)  # type: ignore[var-annotated]
    is_required = Column(BOOLEAN, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "display_order >= 1 AND display_order <= 10",
            name="ck_display_order",
        ),
        CheckConstraint(
            "category IN ('APPLICATION', 'RECRUITER_EXPERIENCE', 'HIRING_MANAGER_EXPERIENCE', "
            "'LOOP_INTERVIEW_EXPERIENCE', 'OFFER_EXPERIENCE')",
            name="ck_category",
        ),
    )


class CandidateFeedbackSurveyResponse(Base, AuditMixin):
    """Candidate's survey response (Req 9.4)."""
    __tablename__ = "candidate_feedback_survey_responses"

    candidate_feedback_survey_response_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_feedback_survey_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    additional_comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class CandidateFeedbackSurveyAnswer(Base, AuditMixin):
    """Individual answer to survey question (Req 9.5)."""
    __tablename__ = "candidate_feedback_survey_answers"

    candidate_feedback_survey_answer_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_feedback_survey_response_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    candidate_feedback_survey_question_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    rating = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("rating >= 0 AND rating <= 10", name="ck_rating"),
    )


class SurveyFeedbackTemplate(Base, AuditMixin):
    """Survey email template (Req 9.17)."""
    __tablename__ = "survey_feedback_templates"

    survey_feedback_template_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    template_type = Column(String(50), nullable=False)  # type: ignore[var-annotated]
    subject = Column(String(200), nullable=False)
    body_template = Column(Text, nullable=False)
    is_enabled = Column(BOOLEAN, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "template_type", name="uk_survey_template_org_type"),
        CheckConstraint(
            "template_type IN ('initial_survey_invitation', 'survey_reminder')",
            name="ck_template_type",
        ),
    )
