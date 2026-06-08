"""Questionnaires service.

Implements questionnaire management functionality.

Requirements: 7.1
"""

from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.questionnaires.models import (
    Questionnaire,
    CandidateQuestionnaireResponse,
    JobRequisitionQuestionnaire,
    ResponseStatus,
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

    @transactional()
    async def auto_create_responses(
        self,
        candidate_id: UUID,
        job_requisition_id: UUID,
        org_id: UUID,
    ) -> list[CandidateQuestionnaireResponse]:
        """
        Auto-create questionnaire responses for a candidate on requisition association.
        
        Called when a candidate is first associated with a requisition.
        For each linked questionnaire, creates a CandidateQuestionnaireResponse
        with status=DRAFT if one doesn't already exist.
        
        Requirements: 4.5, 5.1
        """
        links_result = await self.db.execute(
            select(JobRequisitionQuestionnaire).where(
                JobRequisitionQuestionnaire.job_requisition_id == job_requisition_id,
                JobRequisitionQuestionnaire.deleted_at.is_(None),
            )
        )
        links = links_result.scalars().all()
        created = []
        
        for link in links:
            existing = await self.db.execute(
                select(CandidateQuestionnaireResponse).where(
                    CandidateQuestionnaireResponse.candidate_id == candidate_id,
                    CandidateQuestionnaireResponse.questionnaire_id == link.questionnaire_id,
                    CandidateQuestionnaireResponse.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            response = CandidateQuestionnaireResponse(
                candidate_questionnaire_response_id=uuid4(),
                candidate_id=candidate_id,
                questionnaire_id=link.questionnaire_id,
                organization_id=org_id,
                status=ResponseStatus.DRAFT.value,
            )
            self.db.add(response)
            created.append(response)
        
        await self.db.flush()
        
        # Wire portal token creation: after creating first response for this candidate,
        # generate or get a portal token
        if created:
            from app.modules.portal.service import CandidatePortalService
            portal_service = CandidatePortalService(self.db)
            await portal_service.get_or_create_token(candidate_id, org_id)
            logger.info(
                "portal_token_auto_created",
                candidate_id=str(candidate_id),
                org_id=str(org_id),
                response_count=len(created),
            )
        
        return created
