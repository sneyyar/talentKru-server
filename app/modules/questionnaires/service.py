"""Questionnaires service.

Implements questionnaire management functionality.

Requirements: 7.1
"""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.questionnaires.models import (
    Questionnaire,
    CandidateQuestionnaireResponse,
)
from app.observability.logging import get_logger
from app.decorators import transactional, read_only

logger = get_logger(__name__)


class QuestionnairesService:
    """Service for questionnaire operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @read_only
    async def get_questionnaire(
        self,
        questionnaire_id: UUID,
    ) -> Questionnaire | None:
        """
        Get questionnaire by ID.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(Questionnaire).where(
                Questionnaire.questionnaire_id == questionnaire_id
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def get_questionnaire_response(
        self,
        response_id: UUID,
    ) -> CandidateQuestionnaireResponse | None:
        """
        Get candidate questionnaire response by ID.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(CandidateQuestionnaireResponse).where(
                CandidateQuestionnaireResponse.response_id == response_id
            )
        )
        return result.scalar_one_or_none()
