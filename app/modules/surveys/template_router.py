"""Survey feedback template router (Req 9.17, 9.18)."""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db_session
from app.dependencies import Principal, get_current_principal
from app.modules.auth.dependencies import require_role
from app.modules.surveys.schemas import (
    SurveyTemplateCreate,
    SurveyTemplateUpdate,
    SurveyTemplateResponse,
)
from app.modules.surveys.service import CandidateFeedbackSurveyTemplateService
from app.observability.logging import get_logger

logger = get_logger(__name__)

template_router = APIRouter(prefix="/api/v1/survey-templates", tags=["survey-templates"])


@template_router.get(
    "",
    response_model=list[SurveyTemplateResponse],
    status_code=status.HTTP_200_OK,
    summary="List survey templates",
    description=(
        "List all survey feedback templates for the current organization. "
        "Requires Administrator or SuperAdministrator role."
    ),
    dependencies=[Depends(require_role("Administrator", "SuperAdministrator"))],
    openapi_extra={
        "x-internal": False,
    },
)
async def list_survey_templates(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> list[SurveyTemplateResponse]:
    """
    List all survey templates for the organization.

    Requires Administrator or SuperAdministrator role.
    Returns all templates scoped to the organization.

    Requirements: 9.17, 9.18
    """
    service = CandidateFeedbackSurveyTemplateService(db)
    templates = await service.list_templates(principal.organization_id)

    logger.info(
        "survey_templates_listed",
        org_id=str(principal.organization_id),
        count=len(templates),
    )

    return [SurveyTemplateResponse.from_orm(t) for t in templates]


@template_router.post(
    "",
    response_model=SurveyTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create survey template",
    description=(
        "Create a new survey feedback template for the organization. "
        "Requires Administrator or SuperAdministrator role. "
        "Returns 409 if template type already exists for the organization."
    ),
    dependencies=[Depends(require_role("Administrator", "SuperAdministrator"))],
    openapi_extra={
        "x-internal": False,
    },
)
async def create_survey_template(
    request: SurveyTemplateCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> SurveyTemplateResponse:
    """
    Create a new survey template.

    Requires Administrator or SuperAdministrator role.
    Validates template_type, subject (max 200 chars), and body_template (required).

    Returns:
    - 201: Template created successfully
    - 409: Template type already exists for this organization
    - 422: Validation failed (invalid template_type, subject length, empty body)

    Requirements: 9.17, 9.18
    """
    service = CandidateFeedbackSurveyTemplateService(db)
    template = await service.create_template(
        org_id=principal.organization_id,
        template_type=request.template_type,
        subject=request.subject,
        body_template=request.body_template,
        is_enabled=request.is_enabled,
    )

    logger.info(
        "survey_template_created",
        template_id=str(template.survey_feedback_template_id),
        org_id=str(principal.organization_id),
        template_type=template.template_type,
    )

    return SurveyTemplateResponse.from_orm(template)


@template_router.patch(
    "/{template_id}",
    response_model=SurveyTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update survey template",
    description=(
        "Update a survey feedback template. "
        "Requires Administrator or SuperAdministrator role. "
        "Updates are org-scoped; returns 404 if template not found."
    ),
    dependencies=[Depends(require_role("Administrator", "SuperAdministrator"))],
    openapi_extra={
        "x-internal": False,
    },
)
async def update_survey_template(
    template_id: UUID,
    request: SurveyTemplateUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> SurveyTemplateResponse:
    """
    Update a survey template.

    Requires Administrator or SuperAdministrator role.
    All fields are optional; only provided fields are updated.

    Returns:
    - 200: Template updated successfully
    - 404: Template not found for this organization
    - 422: Validation failed (subject length, empty body)

    Requirements: 9.17, 9.18
    """
    service = CandidateFeedbackSurveyTemplateService(db)
    template = await service.update_template(
        org_id=principal.organization_id,
        template_id=template_id,
        subject=request.subject,
        body_template=request.body_template,
        is_enabled=request.is_enabled,
    )

    logger.info(
        "survey_template_updated",
        template_id=str(template.survey_feedback_template_id),
        org_id=str(principal.organization_id),
    )

    return SurveyTemplateResponse.from_orm(template)


@template_router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete survey template",
    description=(
        "Soft delete a survey feedback template. "
        "Requires Administrator or SuperAdministrator role. "
        "Returns 404 if template not found."
    ),
    dependencies=[Depends(require_role("Administrator", "SuperAdministrator"))],
    openapi_extra={
        "x-internal": False,
    },
)
async def delete_survey_template(
    template_id: UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Soft delete a survey template.

    Requires Administrator or SuperAdministrator role.
    Sets deleted_at timestamp for audit trail.

    Returns:
    - 204: Template deleted successfully
    - 404: Template not found for this organization

    Requirements: 9.17, 9.18
    """
    service = CandidateFeedbackSurveyTemplateService(db)
    await service.delete_template(
        org_id=principal.organization_id,
        template_id=template_id,
    )

    logger.info(
        "survey_template_deleted",
        template_id=str(template_id),
        org_id=str(principal.organization_id),
    )
