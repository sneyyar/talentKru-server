"""
Questionnaire ORM model stubs: Questionnaire, CandidateQuestionnaireResponse.

Both inherit Base, AuditMixin, and VersionMixin to satisfy Requirements 7.1 and 7.5
(optimistic locking on all mutable entities).
"""

import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

from app.base_model import AuditMixin, Base, VersionMixin


class Questionnaire(Base, AuditMixin, VersionMixin):
    """
    Questionnaire entity stub.

    Requirements: 7.1, 7.5
    """

    __tablename__ = "questionnaires"

    questionnaire_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)


class CandidateQuestionnaireResponse(Base, AuditMixin, VersionMixin):
    """
    CandidateQuestionnaireResponse entity stub.

    Requirements: 7.1, 7.5
    """

    __tablename__ = "candidate_questionnaire_responses"

    response_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Org-scoping — required by the org-scoped query helper (Req 2.4)
    organization_id = Column(UUID(as_uuid=True), nullable=True)
