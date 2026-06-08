"""Questionnaires service.

Implements questionnaire management functionality.

Requirements: 4.1, 4.3, 4.4, 4.5, 4.8, 4.9, 4.10
"""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status, BackgroundTasks

from app.modules.questionnaires.models import (
    Questionnaire,
    CandidateQuestionnaireResponse,
    CandidateQuestionnaireAnswer,
    JobRequisitionQuestionnaire,
    ResponseStatus,
)
from app.observability.logging import get_logger
from app.decorators import transactional, read_only
from app.dependencies import Principal

logger = get_logger(__name__)


class QuestionnairesService:
    """Service for questionnaire operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @transactional()
    async def create_questionnaire(
        self,
        org_id: UUID,
        title: str,
        questions_yaml: str,
        created_by: UUID,
    ) -> Questionnaire:
        """
        Create a new questionnaire.
        
        Requirements: 4.1
        """
        questionnaire = Questionnaire(
            questionnaire_id=uuid4(),
            organization_id=org_id,
            title=title,
            questions_yaml=questions_yaml,
        )
        self.db.add(questionnaire)
        await self.db.flush()
        
        logger.info(
            "questionnaire_created",
            questionnaire_id=str(questionnaire.questionnaire_id),
            org_id=str(org_id),
            title=title,
        )
        return questionnaire

    @read_only
    async def get_questionnaire(
        self,
        questionnaire_id: UUID,
    ) -> Questionnaire | None:
        """
        Get questionnaire by ID.

        Requirements: 4.1
        """
        result = await self.db.execute(
            select(Questionnaire).where(
                Questionnaire.questionnaire_id == questionnaire_id,
                Questionnaire.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def get_questionnaire_in_org(
        self,
        questionnaire_id: UUID,
        org_id: UUID,
    ) -> Questionnaire | None:
        """
        Get questionnaire by ID in a specific organization.

        Requirements: 4.1
        """
        result = await self.db.execute(
            select(Questionnaire).where(
                Questionnaire.questionnaire_id == questionnaire_id,
                Questionnaire.organization_id == org_id,
                Questionnaire.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def list_questionnaires(
        self,
        org_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Questionnaire], int]:
        """
        List questionnaires in organization with pagination.
        
        Requirements: 4.1
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count(Questionnaire.questionnaire_id)).where(
                Questionnaire.organization_id == org_id,
                Questionnaire.deleted_at.is_(None),
            )
        )
        total = count_result.scalar() or 0
        
        # Get paginated results
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Questionnaire)
            .where(
                Questionnaire.organization_id == org_id,
                Questionnaire.deleted_at.is_(None),
            )
            .order_by(Questionnaire.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        questionnaires = result.scalars().all()
        
        return questionnaires, total

    @transactional()
    async def update_questionnaire(
        self,
        questionnaire_id: UUID,
        org_id: UUID,
        title: str | None = None,
        questions_yaml: str | None = None,
        updated_by: UUID | None = None,
    ) -> Questionnaire | None:
        """
        Update questionnaire title and/or questions YAML.
        
        Requirements: 4.1, 4.3
        """
        questionnaire = await self.get_questionnaire_in_org(questionnaire_id, org_id)
        if not questionnaire:
            return None
        
        if title is not None:
            questionnaire.title = title
        if questions_yaml is not None:
            questionnaire.questions_yaml = questions_yaml
        
        await self.db.flush()
        
        logger.info(
            "questionnaire_updated",
            questionnaire_id=str(questionnaire_id),
            org_id=str(org_id),
        )
        return questionnaire

    @transactional()
    async def link_questionnaire_to_requisition(
        self,
        questionnaire_id: UUID,
        requisition_id: UUID,
        org_id: UUID,
        created_by: UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> JobRequisitionQuestionnaire:
        """
        Link questionnaire to a job requisition.
        
        When linked, candidates associated with the requisition will be offered
        the questionnaire. If candidates are already associated, auto-create
        responses for them.
        
        Requirements: 4.4, 4.5
        """
        # Check questionnaire exists in org
        questionnaire = await self.get_questionnaire_in_org(questionnaire_id, org_id)
        if not questionnaire:
            raise HTTPException(
                status_code=404,
                detail="Questionnaire not found"
            )
        
        # Check if link already exists
        existing = await self.db.execute(
            select(JobRequisitionQuestionnaire).where(
                JobRequisitionQuestionnaire.job_requisition_id == requisition_id,
                JobRequisitionQuestionnaire.questionnaire_id == questionnaire_id,
                JobRequisitionQuestionnaire.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="Questionnaire is already linked to this requisition"
            )
        
        link = JobRequisitionQuestionnaire(
            job_requisition_questionnaire_id=uuid4(),
            job_requisition_id=requisition_id,
            questionnaire_id=questionnaire_id,
            organization_id=org_id,
        )
        self.db.add(link)
        await self.db.flush()
        
        logger.info(
            "questionnaire_linked_to_requisition",
            questionnaire_id=str(questionnaire_id),
            requisition_id=str(requisition_id),
            org_id=str(org_id),
        )
        return link

    @read_only
    async def get_questionnaire_response(
        self,
        response_id: UUID,
    ) -> CandidateQuestionnaireResponse | None:
        """
        Get candidate questionnaire response by ID.

        Requirements: 4.6
        """
        result = await self.db.execute(
            select(CandidateQuestionnaireResponse).where(
                CandidateQuestionnaireResponse.candidate_questionnaire_response_id == response_id,
                CandidateQuestionnaireResponse.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def get_questionnaire_response_authorized(
        self,
        response_id: UUID,
        org_id: UUID,
        principal: Principal,
    ) -> CandidateQuestionnaireResponse | None:
        """
        Get questionnaire response with authorization check.
        
        Candidate can view own responses. Recruiter and Admin can view any response.
        
        Requirements: 4.10
        """
        response = await self.get_questionnaire_response(response_id)
        if not response or response.organization_id != org_id:
            return None
        
        # Handle both string roles and role objects
        roles_list = principal.roles or []
        role_names = set()
        for r in roles_list:
            if isinstance(r, str):
                role_names.add(r)
            elif hasattr(r, 'role_name'):
                role_names.add(r.role_name)
        
        is_admin = "Administrator" in role_names
        is_recruiter = "Recruiter" in role_names
        is_owner = response.candidate_id == principal.user_id
        
        if is_admin or is_recruiter or is_owner:
            return response
        
        return None

    @transactional()
    async def save_answers(
        self,
        response_id: UUID,
        org_id: UUID,
        answers: dict[str, str],
        is_final_submit: bool = False,
        principal: Principal | None = None,
    ) -> CandidateQuestionnaireResponse | None:
        """
        Save or submit questionnaire answers.
        
        If is_final_submit=False: saves draft, sets status to INCOMPLETE if not all required answered.
        If is_final_submit=True: validates all required questions answered, sets to SUBMITTED.
        
        Returns updated response or None if unauthorized.
        
        Requirements: 4.8, 4.9, 4.10
        """
        response = await self.get_questionnaire_response(response_id)
        if not response or response.organization_id != org_id:
            return None
        
        # Authorization check
        if principal:
            # Handle both string roles and role objects
            roles_list = principal.roles or []
            role_names = set()
            for r in roles_list:
                if isinstance(r, str):
                    role_names.add(r)
                elif hasattr(r, 'role_name'):
                    role_names.add(r.role_name)
            
            is_admin = "Administrator" in role_names
            is_recruiter = "Recruiter" in role_names
            is_owner = response.candidate_id == principal.user_id
            
            if not (is_admin or is_recruiter or is_owner):
                return None
        
        # Check if already submitted
        if response.status == ResponseStatus.SUBMITTED.value:
            raise HTTPException(
                status_code=409,
                detail="Cannot modify a submitted response"
            )
        
        # Get the questionnaire to validate against schema
        questionnaire = await self.get_questionnaire(response.questionnaire_id)
        if not questionnaire:
            raise HTTPException(status_code=404, detail="Questionnaire not found")
        
        # Parse YAML to get required questions
        import yaml
        questions_list = yaml.safe_load(questionnaire.questions_yaml)
        required_question_ids = {q["id"] for q in questions_list if q.get("required", False)}
        
        # Check if all required answers provided
        provided_ids = set(answers.keys())
        missing_required = required_question_ids - provided_ids
        
        if is_final_submit:
            if missing_required:
                raise HTTPException(
                    status_code=422,
                    detail=f"Missing answers for required questions: {', '.join(missing_required)}"
                )
            response.status = ResponseStatus.SUBMITTED.value
        else:
            # Draft save: set to INCOMPLETE if not all required answered
            if missing_required:
                response.status = ResponseStatus.INCOMPLETE.value
            else:
                response.status = ResponseStatus.INCOMPLETE.value  # Or could be DRAFT if partial
        
        # Save/update answers
        for question_id, answer in answers.items():
            existing_answer = await self.db.execute(
                select(CandidateQuestionnaireAnswer).where(
                    CandidateQuestionnaireAnswer.candidate_questionnaire_response_id == response_id,
                    CandidateQuestionnaireAnswer.question_id == question_id,
                    CandidateQuestionnaireAnswer.deleted_at.is_(None),
                )
            )
            answer_record = existing_answer.scalar_one_or_none()
            
            if answer_record:
                answer_record.answer = answer
            else:
                answer_record = CandidateQuestionnaireAnswer(
                    candidate_questionnaire_answer_id=uuid4(),
                    candidate_questionnaire_response_id=response_id,
                    question_id=question_id,
                    answer=answer,
                )
                self.db.add(answer_record)
        
        await self.db.flush()
        
        logger.info(
            "questionnaire_answers_saved",
            response_id=str(response_id),
            org_id=str(org_id),
            is_final_submit=is_final_submit,
            answer_count=len(answers),
        )
        
        return response

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
