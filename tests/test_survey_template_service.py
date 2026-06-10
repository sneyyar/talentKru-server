"""Candidate feedback survey template service tests."""

from uuid import uuid4

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.surveys.models import (
    SurveyFeedbackTemplate,
    SurveyTemplateType,
)
from app.modules.surveys.service import CandidateFeedbackSurveyTemplateService


@pytest.mark.asyncio
async def test_create_template_success(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Create survey template successfully."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    template = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Survey Invitation - {test_run_id}",
        body_template="Please complete our survey at {{survey_link}}",
        is_enabled=True,
    )
    
    assert template.survey_feedback_template_id is not None
    assert template.organization_id == org_id
    assert template.template_type == "initial_survey_invitation"
    assert template.subject == f"Survey Invitation - {test_run_id}"
    assert template.body_template == "Please complete our survey at {{survey_link}}"
    assert template.is_enabled is True
    assert template.version == 1


@pytest.mark.asyncio
async def test_create_template_invalid_template_type(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Invalid template_type should raise 422."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    with pytest.raises(Exception) as exc_info:
        await service.create_template(
            org_id=org_id,
            template_type="invalid_type",
            subject=f"Subject - {test_run_id}",
            body_template="Body template",
            is_enabled=True,
        )
    
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_template_subject_too_long(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Subject > 200 chars should raise 422."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    long_subject = "x" * 201
    with pytest.raises(Exception) as exc_info:
        await service.create_template(
            org_id=org_id,
            template_type="initial_survey_invitation",
            subject=long_subject,
            body_template="Body template",
            is_enabled=True,
        )
    
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_template_empty_body(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Empty body_template should raise 422."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    with pytest.raises(Exception) as exc_info:
        await service.create_template(
            org_id=org_id,
            template_type="initial_survey_invitation",
            subject=f"Subject - {test_run_id}",
            body_template="",
            is_enabled=True,
        )
    
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_template_duplicate_raises_409(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Creating duplicate template_type for same org should raise 409."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    # Create first template
    await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject 1 - {test_run_id}",
        body_template="Body 1",
        is_enabled=True,
    )
    
    # Try to create duplicate
    with pytest.raises(Exception) as exc_info:
        await service.create_template(
            org_id=org_id,
            template_type="initial_survey_invitation",
            subject=f"Subject 2 - {test_run_id}",
            body_template="Body 2",
            is_enabled=True,
        )
    
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_get_template_success(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Get template by org_id and template_type."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject - {test_run_id}",
        body_template="Body",
        is_enabled=True,
    )
    
    retrieved = await service.get_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
    )
    
    assert retrieved is not None
    assert retrieved.survey_feedback_template_id == created.survey_feedback_template_id
    assert retrieved.subject == created.subject


@pytest.mark.asyncio
async def test_get_template_not_found(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Get non-existent template should return None."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    result = await service.get_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_list_templates_success(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """List all templates for organization."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    # Create two templates
    await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Invitation - {test_run_id}",
        body_template="Body 1",
        is_enabled=True,
    )
    
    await service.create_template(
        org_id=org_id,
        template_type="survey_reminder",
        subject=f"Reminder - {test_run_id}",
        body_template="Body 2",
        is_enabled=True,
    )
    
    templates = await service.list_templates(org_id)
    
    assert len(templates) == 2
    assert all(t.organization_id == org_id for t in templates)


@pytest.mark.asyncio
async def test_list_templates_empty(
    db_session: AsyncSession, org_id
):
    """List templates for org with no templates."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    templates = await service.list_templates(org_id)
    
    assert templates == []


@pytest.mark.asyncio
async def test_update_template_subject(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Update template subject."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Old Subject - {test_run_id}",
        body_template="Body",
        is_enabled=True,
    )
    
    new_subject = f"New Subject - {test_run_id}"
    updated = await service.update_template(
        org_id=org_id,
        template_id=created.survey_feedback_template_id,
        subject=new_subject,
    )
    
    assert updated.subject == new_subject
    assert updated.body_template == "Body"
    assert updated.is_enabled is True
    assert updated.version == 2  # Version incremented


@pytest.mark.asyncio
async def test_update_template_body(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Update template body."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject - {test_run_id}",
        body_template="Old body",
        is_enabled=True,
    )
    
    new_body = "New body with {{placeholder}}"
    updated = await service.update_template(
        org_id=org_id,
        template_id=created.survey_feedback_template_id,
        body_template=new_body,
    )
    
    assert updated.body_template == new_body


@pytest.mark.asyncio
async def test_update_template_is_enabled(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Update template enabled status."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject - {test_run_id}",
        body_template="Body",
        is_enabled=True,
    )
    
    updated = await service.update_template(
        org_id=org_id,
        template_id=created.survey_feedback_template_id,
        is_enabled=False,
    )
    
    assert updated.is_enabled is False


@pytest.mark.asyncio
async def test_update_template_not_found(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Update non-existent template should raise 404."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    with pytest.raises(Exception) as exc_info:
        await service.update_template(
            org_id=org_id,
            template_id=uuid4(),
            subject="New subject",
        )
    
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_template_invalid_subject_length(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Update with invalid subject length should raise 422."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject - {test_run_id}",
        body_template="Body",
        is_enabled=True,
    )
    
    with pytest.raises(Exception) as exc_info:
        await service.update_template(
            org_id=org_id,
            template_id=created.survey_feedback_template_id,
            subject="x" * 201,
        )
    
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_update_template_empty_body(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Update with empty body should raise 422."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject - {test_run_id}",
        body_template="Body",
        is_enabled=True,
    )
    
    with pytest.raises(Exception) as exc_info:
        await service.update_template(
            org_id=org_id,
            template_id=created.survey_feedback_template_id,
            body_template="",
        )
    
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_delete_template_success(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Soft delete template."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject - {test_run_id}",
        body_template="Body",
        is_enabled=True,
    )
    
    # Delete
    await service.delete_template(org_id, created.survey_feedback_template_id)
    
    # Verify soft delete (deleted_at is set)
    result = await db_session.execute(
        select(SurveyFeedbackTemplate).where(
            SurveyFeedbackTemplate.survey_feedback_template_id
            == created.survey_feedback_template_id
        )
    )
    template = result.scalar_one_or_none()
    assert template is not None
    assert template.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_template_not_found(
    db_session: AsyncSession, org_id
):
    """Delete non-existent template should raise 404."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    with pytest.raises(Exception) as exc_info:
        await service.delete_template(org_id, uuid4())
    
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_template_org_scoped(
    db_session: AsyncSession, test_run_id: str, org_id
):
    """Delete should fail if template belongs to different org."""
    service = CandidateFeedbackSurveyTemplateService(db_session)
    
    created = await service.create_template(
        org_id=org_id,
        template_type="initial_survey_invitation",
        subject=f"Subject - {test_run_id}",
        body_template="Body",
        is_enabled=True,
    )
    
    different_org_id = uuid4()
    
    with pytest.raises(Exception) as exc_info:
        await service.delete_template(different_org_id, created.survey_feedback_template_id)
    
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
