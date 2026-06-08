"""Questionnaire models (Req 4.1)."""

import enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE, JSON

from app.base_model import Base, AuditMixin, VersionMixin


class ResponseStatus(str, enum.Enum):
    """Questionnaire response status."""
    DRAFT = "DRAFT"
    INCOMPLETE = "INCOMPLETE"
    SUBMITTED = "SUBMITTED"


class Questionnaire(Base, AuditMixin, VersionMixin):
    """Questionnaire definition (Req 4.1)."""
    __tablename__ = "questionnaires"

    questionnaire_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    questions_yaml = Column(Text, nullable=False)


class JobRequisitionQuestionnaire(Base, AuditMixin):
    """Link questionnaire to job requisition (Req 4.4)."""
    __tablename__ = "job_requisition_questionnaires"

    job_requisition_questionnaire_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    job_requisition_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    questionnaire_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("job_requisition_id", "questionnaire_id", name="uk_req_questionnaire"),
    )


class CandidateQuestionnaireResponse(Base, AuditMixin, VersionMixin):
    """Candidate's response to a questionnaire (Req 4.6)."""
    __tablename__ = "candidate_questionnaire_responses"

    candidate_questionnaire_response_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    questionnaire_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    organization_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    status = Column(String(50), nullable=False, default=ResponseStatus.DRAFT.value)  # type: ignore[var-annotated]

    __table_args__ = (
        UniqueConstraint("candidate_id", "questionnaire_id", name="uk_candidate_questionnaire"),
        CheckConstraint(
            "status IN ('DRAFT', 'INCOMPLETE', 'SUBMITTED')",
            name="ck_response_status",
        ),
    )


class CandidateQuestionnaireAnswer(Base, AuditMixin):
    """Individual answer to questionnaire question (Req 4.7)."""
    __tablename__ = "candidate_questionnaire_answers"

    candidate_questionnaire_answer_id = Column(UUID_TYPE(as_uuid=True), primary_key=True, default=uuid4)
    candidate_questionnaire_response_id = Column(UUID_TYPE(as_uuid=True), nullable=False)
    question_id = Column(String(500), nullable=False)
    answer = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("candidate_questionnaire_response_id", "question_id", name="uk_response_question"),
    )
