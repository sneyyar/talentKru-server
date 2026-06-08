"""
Tests for questionnaire service.

Feature: interview-workflow
Task: 8.5 - Questionnaire router implementation

Requirements: 4.1, 4.3, 4.4, 4.5, 4.8, 4.9, 4.10
"""

import pytest
import yaml
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.modules.questionnaires.models import (
    Questionnaire,
    JobRequisitionQuestionnaire,
    CandidateQuestionnaireResponse,
    ResponseStatus,
)
from app.modules.questionnaires.service import QuestionnairesService
from app.modules.requisitions.service import RequisitionService
from app.modules.job_profile.service import JobProfileService
from app.modules.job_profile.schemas import JobProfileCreate
from app.modules.users.service import UserService
from app.modules.rbac.service import RBACService
from app.dependencies import Principal


@pytest.fixture
async def recruiter_user(db_session: AsyncSession, org_id, test_run_id, admin_user):
    """Create a recruiter user for testing."""
    user_service = UserService(db_session)
    email = f"recruiter-{test_run_id}@example.com"
    user = await user_service.create_user(
        email=email,
        given_name="Recruiter",
        last_name="User",
        org_id=org_id,
    )
    rbac_service = RBACService(db_session)
    await rbac_service.assign_role(
        user_id=user.user_id,
        role_name="Recruiter",
        actor_id=admin_user,
    )
    return user.user_id


@pytest.fixture
async def hiring_manager_user(db_session: AsyncSession, org_id, test_run_id, admin_user):
    """Create a hiring manager user for testing."""
    user_service = UserService(db_session)
    email = f"hiring-manager-{test_run_id}@example.com"
    user = await user_service.create_user(
        email=email,
        given_name="Hiring",
        last_name="Manager",
        org_id=org_id,
    )
    rbac_service = RBACService(db_session)
    await rbac_service.assign_role(
        user_id=user.user_id,
        role_name="HiringManager",
        actor_id=admin_user,
    )
    return user.user_id


@pytest.fixture
async def candidate_user(db_session: AsyncSession, org_id, test_run_id):
    """Create a candidate user for testing."""
    user_service = UserService(db_session)
    email = f"candidate-{test_run_id}@example.com"
    user = await user_service.create_user(
        email=email,
        given_name="Candidate",
        last_name="User",
        org_id=org_id,
    )
    return user.user_id


@pytest.fixture
def valid_questionnaire_yaml():
    """Valid questionnaire YAML for testing."""
    questions = [
        {"id": "q1", "text": "Python experience?", "type": "text", "required": True},
        {"id": "q2", "text": "Rate skills", "type": "rating", "required": True, "minRating": 1, "maxRating": 5},
        {"id": "q3", "text": "Tech stack", "type": "multipleChoice", "required": False, "options": ["Python", "JS"]},
    ]
    return yaml.dump(questions)


class TestQuestionnaireService:
    """Tests for questionnaire service."""

    @pytest.mark.asyncio
    async def test_create_questionnaire(self, db_session, org_id, recruiter_user, valid_questionnaire_yaml, test_run_id):
        """Test: Create questionnaire. Validates: 4.1, 4.3"""
        service = QuestionnairesService(db_session)
        title = f"Tech-{test_run_id}"
        
        questionnaire = await service.create_questionnaire(
            org_id=org_id,
            title=title,
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        assert questionnaire.questionnaire_id is not None
        assert questionnaire.organization_id == org_id
        assert questionnaire.title == title

    @pytest.mark.asyncio
    async def test_list_questionnaires(self, db_session, org_id, recruiter_user, valid_questionnaire_yaml, test_run_id):
        """Test: List questionnaires. Validates: 4.1"""
        service = QuestionnairesService(db_session)
        
        for i in range(3):
            await service.create_questionnaire(
                org_id=org_id,
                title=f"Q{i}-{test_run_id}",
                questions_yaml=valid_questionnaire_yaml,
                created_by=recruiter_user,
            )
        
        questionnaires, total = await service.list_questionnaires(org_id=org_id, page=1, page_size=2)
        assert total >= 3
        assert len(questionnaires) == 2

    @pytest.mark.asyncio
    async def test_get_questionnaire(self, db_session, org_id, recruiter_user, valid_questionnaire_yaml, test_run_id):
        """Test: Get questionnaire. Validates: 4.1"""
        service = QuestionnairesService(db_session)
        
        created = await service.create_questionnaire(
            org_id=org_id,
            title=f"Get-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        retrieved = await service.get_questionnaire_in_org(created.questionnaire_id, org_id)
        assert retrieved is not None
        assert retrieved.questionnaire_id == created.questionnaire_id

    @pytest.mark.asyncio
    async def test_update_questionnaire(self, db_session, org_id, recruiter_user, valid_questionnaire_yaml, test_run_id):
        """Test: Update questionnaire. Validates: 4.1, 4.3"""
        service = QuestionnairesService(db_session)
        
        created = await service.create_questionnaire(
            org_id=org_id,
            title=f"Orig-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        new_title = f"Updated-{test_run_id}"
        updated = await service.update_questionnaire(
            created.questionnaire_id,
            org_id,
            title=new_title,
        )
        
        assert updated.title == new_title

    @pytest.mark.asyncio
    async def test_link_questionnaire(self, db_session, org_id, recruiter_user, hiring_manager_user, valid_questionnaire_yaml, test_run_id):
        """Test: Link questionnaire. Validates: 4.4"""
        q_service = QuestionnairesService(db_session)
        r_service = RequisitionService(db_session)
        p_service = JobProfileService(db_session)
        
        questionnaire = await q_service.create_questionnaire(
            org_id=org_id,
            title=f"Link-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        profile = await p_service.create_job_profile(
            org_id=org_id,
            data=JobProfileCreate(name=f"Prof-{test_run_id}", skills=[]),
            created_by=recruiter_user,
        )
        
        requisition = await r_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Role",
            department="Eng",
            location="Remote",
            hiring_manager_user_id=hiring_manager_user,
            created_by=recruiter_user,
        )
        
        link = await q_service.link_questionnaire_to_requisition(
            questionnaire_id=questionnaire.questionnaire_id,
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            created_by=recruiter_user,
        )
        
        assert link.questionnaire_id == questionnaire.questionnaire_id

    @pytest.mark.asyncio
    async def test_link_duplicate_fails(self, db_session, org_id, recruiter_user, hiring_manager_user, valid_questionnaire_yaml, test_run_id):
        """Test: Cannot link twice. Validates: 4.4"""
        q_service = QuestionnairesService(db_session)
        r_service = RequisitionService(db_session)
        p_service = JobProfileService(db_session)
        
        questionnaire = await q_service.create_questionnaire(
            org_id=org_id,
            title=f"Dup-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        profile = await p_service.create_job_profile(
            org_id=org_id,
            data=JobProfileCreate(name=f"Prof2-{test_run_id}", skills=[]),
            created_by=recruiter_user,
        )
        
        requisition = await r_service.create_requisition(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Role",
            department="Eng",
            location="Remote",
            hiring_manager_user_id=hiring_manager_user,
            created_by=recruiter_user,
        )
        
        await q_service.link_questionnaire_to_requisition(
            questionnaire_id=questionnaire.questionnaire_id,
            requisition_id=requisition.job_requisition_id,
            org_id=org_id,
            created_by=recruiter_user,
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await q_service.link_questionnaire_to_requisition(
                questionnaire_id=questionnaire.questionnaire_id,
                requisition_id=requisition.job_requisition_id,
                org_id=org_id,
                created_by=recruiter_user,
            )
        
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_save_answers_draft(self, db_session, org_id, recruiter_user, candidate_user, valid_questionnaire_yaml, test_run_id):
        """Test: Save draft answers. Validates: 4.8, 4.9"""
        q_service = QuestionnairesService(db_session)
        
        questionnaire = await q_service.create_questionnaire(
            org_id=org_id,
            title=f"Answer-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        response = CandidateQuestionnaireResponse(
            candidate_questionnaire_response_id=uuid4(),
            candidate_id=candidate_user,
            questionnaire_id=questionnaire.questionnaire_id,
            organization_id=org_id,
            status=ResponseStatus.DRAFT.value,
        )
        db_session.add(response)
        await db_session.flush()
        
        answers = {"q1": "Python experience"}
        principal = Principal(
            user_id=candidate_user,
            organization_id=org_id,
            role="Candidate",
            roles=["Candidate"],
        )
        
        updated = await q_service.save_answers(
            response_id=response.candidate_questionnaire_response_id,
            org_id=org_id,
            answers=answers,
            is_final_submit=False,
            principal=principal,
        )
        
        assert updated.status == ResponseStatus.INCOMPLETE.value

    @pytest.mark.asyncio
    async def test_submit_complete(self, db_session, org_id, recruiter_user, candidate_user, valid_questionnaire_yaml, test_run_id):
        """Test: Submit complete. Validates: 4.9"""
        q_service = QuestionnairesService(db_session)
        
        questionnaire = await q_service.create_questionnaire(
            org_id=org_id,
            title=f"Submit-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        response = CandidateQuestionnaireResponse(
            candidate_questionnaire_response_id=uuid4(),
            candidate_id=candidate_user,
            questionnaire_id=questionnaire.questionnaire_id,
            organization_id=org_id,
            status=ResponseStatus.DRAFT.value,
        )
        db_session.add(response)
        await db_session.flush()
        
        answers = {"q1": "Experience", "q2": "5"}
        principal = Principal(
            user_id=candidate_user,
            organization_id=org_id,
            role="Candidate",
            roles=["Candidate"],
        )
        
        updated = await q_service.save_answers(
            response_id=response.candidate_questionnaire_response_id,
            org_id=org_id,
            answers=answers,
            is_final_submit=True,
            principal=principal,
        )
        
        assert updated.status == ResponseStatus.SUBMITTED.value

    @pytest.mark.asyncio
    async def test_submit_missing_required(self, db_session, org_id, recruiter_user, candidate_user, valid_questionnaire_yaml, test_run_id):
        """Test: Cannot submit incomplete. Validates: 4.9"""
        q_service = QuestionnairesService(db_session)
        
        questionnaire = await q_service.create_questionnaire(
            org_id=org_id,
            title=f"Missing-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        response = CandidateQuestionnaireResponse(
            candidate_questionnaire_response_id=uuid4(),
            candidate_id=candidate_user,
            questionnaire_id=questionnaire.questionnaire_id,
            organization_id=org_id,
            status=ResponseStatus.DRAFT.value,
        )
        db_session.add(response)
        await db_session.flush()
        
        answers = {"q1": "Experience"}
        principal = Principal(
            user_id=candidate_user,
            organization_id=org_id,
            role="Candidate",
            roles=["Candidate"],
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await q_service.save_answers(
                response_id=response.candidate_questionnaire_response_id,
                org_id=org_id,
                answers=answers,
                is_final_submit=True,
                principal=principal,
            )
        
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_cannot_modify_submitted(self, db_session, org_id, recruiter_user, candidate_user, valid_questionnaire_yaml, test_run_id):
        """Test: Cannot modify submitted. Validates: 4.9, 4.10"""
        q_service = QuestionnairesService(db_session)
        
        questionnaire = await q_service.create_questionnaire(
            org_id=org_id,
            title=f"NoMod-{test_run_id}",
            questions_yaml=valid_questionnaire_yaml,
            created_by=recruiter_user,
        )
        
        response = CandidateQuestionnaireResponse(
            candidate_questionnaire_response_id=uuid4(),
            candidate_id=candidate_user,
            questionnaire_id=questionnaire.questionnaire_id,
            organization_id=org_id,
            status=ResponseStatus.SUBMITTED.value,
        )
        db_session.add(response)
        await db_session.flush()
        
        answers = {"q1": "New"}
        principal = Principal(
            user_id=candidate_user,
            organization_id=org_id,
            role="Candidate",
            roles=["Candidate"],
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await q_service.save_answers(
                response_id=response.candidate_questionnaire_response_id,
                org_id=org_id,
                answers=answers,
                is_final_submit=False,
                principal=principal,
            )
        
        assert exc_info.value.status_code == 409
