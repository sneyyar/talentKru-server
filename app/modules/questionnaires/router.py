"""Questionnaire router.

Endpoints:
- POST /api/v1/questionnaires — require_role("Recruiter", "Administrator"); returns 201
- GET /api/v1/questionnaires — require_role("Recruiter", "Administrator", "HiringManager")
- GET /api/v1/questionnaires/{questionnaire_id} — require_role("Recruiter", "Administrator", "HiringManager")
- PATCH /api/v1/questionnaires/{questionnaire_id} — require_role("Recruiter", "Administrator")
- POST /api/v1/questionnaires/{questionnaire_id}/link — require_role("Recruiter", "Administrator"); link to requisition
- PATCH /api/v1/questionnaire-responses/{response_id}/answers — candidate or recruiter

Requirements: 4.1, 4.3, 4.4, 4.5, 4.8, 4.9, 4.10
"""

from uuid import UUID
import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import require_role
from app.modules.questionnaires.models import (
    Questionnaire,
    JobRequisitionQuestionnaire,
    CandidateQuestionnaireResponse,
    ResponseStatus,
)
from app.modules.questionnaires.schemas import (
    QuestionnaireCreate,
    QuestionnaireResponse,
    ResponseCreate,
    CandidateQuestionnaireResponseSchema,
)
from app.modules.questionnaires.service import QuestionnairesService
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/questionnaires", tags=["questionnaires"])


def _validate_questionnaire_yaml(yaml_str: str) -> dict:
    """
    Validate questionnaire YAML schema.
    
    Schema must be a YAML list of question objects where each question contains:
    - id (string)
    - text (string, max 500 characters)
    - type (text, multipleChoice, singleChoice, rating, date)
    - required (boolean)
    - options (array of strings for choice types)
    - minRating, maxRating (integers for rating type)
    - validation rules (object with pattern, minLength, maxLength for text type)
    
    Returns parsed YAML dict if valid.
    Raises HTTPException with 422 if invalid.
    
    Requirement: 4.3
    """
    try:
        questions = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid YAML format: {str(e)}"
        )
    
    if not isinstance(questions, list):
        raise HTTPException(
            status_code=422,
            detail="Questionnaire must be a YAML list of question objects"
        )
    
    if not questions:
        raise HTTPException(
            status_code=422,
            detail="Questionnaire must contain at least one question"
        )
    
    # Validate each question
    for idx, q in enumerate(questions):
        if not isinstance(q, dict):
            raise HTTPException(
                status_code=422,
                detail=f"Question {idx}: must be an object"
            )
        
        # Required fields
        if "id" not in q:
            raise HTTPException(status_code=422, detail=f"Question {idx}: missing 'id'")
        if not isinstance(q["id"], str):
            raise HTTPException(status_code=422, detail=f"Question {idx}: 'id' must be a string")
        
        if "text" not in q:
            raise HTTPException(status_code=422, detail=f"Question {idx}: missing 'text'")
        if not isinstance(q["text"], str) or len(q["text"]) > 500:
            raise HTTPException(
                status_code=422,
                detail=f"Question {idx}: 'text' must be a string (max 500 chars)"
            )
        
        if "type" not in q:
            raise HTTPException(status_code=422, detail=f"Question {idx}: missing 'type'")
        valid_types = {"text", "multipleChoice", "singleChoice", "rating", "date"}
        if q["type"] not in valid_types:
            raise HTTPException(
                status_code=422,
                detail=f"Question {idx}: 'type' must be one of {valid_types}"
            )
        
        if "required" not in q:
            raise HTTPException(status_code=422, detail=f"Question {idx}: missing 'required'")
        if not isinstance(q["required"], bool):
            raise HTTPException(
                status_code=422,
                detail=f"Question {idx}: 'required' must be boolean"
            )
        
        # Type-specific validation
        if q["type"] in {"multipleChoice", "singleChoice"}:
            if "options" not in q:
                raise HTTPException(
                    status_code=422,
                    detail=f"Question {idx}: '{q['type']}' type requires 'options' array"
                )
            if not isinstance(q["options"], list):
                raise HTTPException(
                    status_code=422,
                    detail=f"Question {idx}: 'options' must be an array"
                )
        
        if q["type"] == "rating":
            if "minRating" in q or "maxRating" in q:
                min_r = q.get("minRating", 1)
                max_r = q.get("maxRating", 5)
                if not isinstance(min_r, int) or not isinstance(max_r, int):
                    raise HTTPException(
                        status_code=422,
                        detail=f"Question {idx}: minRating and maxRating must be integers"
                    )
    
    return questions


@router.post(
    "",
    response_model=QuestionnaireResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_questionnaire",
    summary="Create a new questionnaire",
    description="Create a new questionnaire with YAML-formatted questions. Validates YAML schema before creation. Requires Recruiter or Administrator role. Returns 201 Created.",
    responses={
        201: {"description": "Questionnaire created successfully", "model": QuestionnaireResponse},
        422: {"description": "Invalid YAML schema or missing required fields"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def create_questionnaire(
    request: QuestionnaireCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> QuestionnaireResponse:
    """
    Create a new questionnaire with YAML-formatted questions.
    
    Validates YAML against the required schema (list of question objects).
    If YAML is invalid, returns 422 with validation error details.
    
    Requirement: 4.1, 4.3
    """
    # Validate YAML schema
    _validate_questionnaire_yaml(request.questions_yaml)
    
    service = QuestionnairesService(db)
    questionnaire = await service.create_questionnaire(
        org_id=principal.organization_id,
        title=request.title,
        questions_yaml=request.questions_yaml,
        created_by=principal.user_id,
    )
    
    return QuestionnaireResponse.from_orm(questionnaire)


@router.get(
    "",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="list_questionnaires",
    summary="List questionnaires",
    description="List all questionnaires in the organization with optional pagination. Requires Recruiter, Administrator, or HiringManager role. Returns paginated list with total count.",
    responses={
        200: {"description": "Questionnaires retrieved successfully"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_questionnaires(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List all questionnaires in the organization with pagination.
    
    Requirement: 4.1
    """
    service = QuestionnairesService(db)
    
    questionnaires, total = await service.list_questionnaires(
        org_id=principal.organization_id,
        page=page,
        page_size=page_size,
    )
    
    return {
        "data": [QuestionnaireResponse.from_orm(q) for q in questionnaires],
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    }


@router.get(
    "/{questionnaire_id}",
    response_model=QuestionnaireResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_questionnaire",
    summary="Get questionnaire details",
    description="Retrieve a specific questionnaire by ID with full questions. Requires Recruiter, Administrator, or HiringManager role.",
    responses={
        200: {"description": "Questionnaire found", "model": QuestionnaireResponse},
        404: {"description": "Questionnaire not found"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def get_questionnaire(
    questionnaire_id: UUID,
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> QuestionnaireResponse:
    """
    Get questionnaire details by ID.
    
    Requirement: 4.1
    """
    service = QuestionnairesService(db)
    questionnaire = await service.get_questionnaire_in_org(
        questionnaire_id=questionnaire_id,
        org_id=principal.organization_id,
    )
    
    if not questionnaire:
        raise HTTPException(
            status_code=404,
            detail="Questionnaire not found"
        )
    
    return QuestionnaireResponse.from_orm(questionnaire)


@router.patch(
    "/{questionnaire_id}",
    response_model=QuestionnaireResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_questionnaire",
    summary="Update questionnaire",
    description="Update title and/or questions YAML of a questionnaire. Validates YAML schema. Requires Recruiter or Administrator role.",
    responses={
        200: {"description": "Questionnaire updated successfully", "model": QuestionnaireResponse},
        404: {"description": "Questionnaire not found"},
        422: {"description": "Invalid YAML schema"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def update_questionnaire(
    questionnaire_id: UUID,
    request: QuestionnaireCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> QuestionnaireResponse:
    """
    Update questionnaire title and/or questions YAML.
    
    If questions_yaml is provided, it is validated against the YAML schema.
    
    Requirement: 4.1, 4.3
    """
    # Validate YAML if provided
    if request.questions_yaml:
        _validate_questionnaire_yaml(request.questions_yaml)
    
    service = QuestionnairesService(db)
    questionnaire = await service.update_questionnaire(
        questionnaire_id=questionnaire_id,
        org_id=principal.organization_id,
        title=request.title,
        questions_yaml=request.questions_yaml,
        updated_by=principal.user_id,
    )
    
    if not questionnaire:
        raise HTTPException(
            status_code=404,
            detail="Questionnaire not found"
        )
    
    return QuestionnaireResponse.from_orm(questionnaire)


@router.post(
    "/{questionnaire_id}/link",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    operation_id="link_questionnaire_to_requisition",
    summary="Link questionnaire to job requisition",
    description="Link a questionnaire to a job requisition so candidates complete it during the process. Requires Recruiter or Administrator role. Returns 201 Created.",
    responses={
        201: {"description": "Questionnaire linked successfully"},
        404: {"description": "Questionnaire or requisition not found"},
        409: {"description": "Link already exists"},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def link_questionnaire_to_requisition(
    questionnaire_id: UUID,
    requisition_id: UUID = Query(..., description="Job requisition ID to link to"),
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict:
    """
    Link a questionnaire to a job requisition.
    
    When a questionnaire is linked to a requisition, candidates associated
    with that requisition will be offered the questionnaire.
    
    Requirement: 4.4
    """
    service = QuestionnairesService(db)
    
    result = await service.link_questionnaire_to_requisition(
        questionnaire_id=questionnaire_id,
        requisition_id=requisition_id,
        org_id=principal.organization_id,
        created_by=principal.user_id,
        background_tasks=background_tasks,
    )
    
    return {
        "link_id": str(result.job_requisition_questionnaire_id),
        "questionnaire_id": str(questionnaire_id),
        "requisition_id": str(requisition_id),
        "message": "Questionnaire successfully linked to requisition"
    }


@router.get(
    "/{response_id}",
    response_model=CandidateQuestionnaireResponseSchema,
    status_code=status.HTTP_200_OK,
    operation_id="get_questionnaire_response",
    summary="Get questionnaire response",
    description="Retrieve a candidate's response record for a questionnaire. Authorized roles can view responses.",
    responses={
        200: {"description": "Response found", "model": CandidateQuestionnaireResponseSchema},
        404: {"description": "Response not found"},
        403: {"description": "Forbidden: Not authorized to view this response"},
    },
)
async def get_questionnaire_response(
    response_id: UUID,
    principal: Principal = Depends(),
    db: AsyncSession = Depends(get_db_session),
) -> CandidateQuestionnaireResponseSchema:
    """
    Get a candidate's questionnaire response record.
    
    Authorization: candidate can view own responses, recruiters and admins can view any response.
    
    Requirement: 4.10
    """
    service = QuestionnairesService(db)
    response = await service.get_questionnaire_response_authorized(
        response_id=response_id,
        org_id=principal.organization_id,
        principal=principal,
    )
    
    if not response:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this response"
        )
    
    return CandidateQuestionnaireResponseSchema.from_orm(response)


@router.patch(
    "/{response_id}/answers",
    response_model=CandidateQuestionnaireResponseSchema,
    status_code=status.HTTP_200_OK,
    operation_id="save_questionnaire_answers",
    summary="Save or submit questionnaire answers",
    description="Save draft answers or submit final answers for a questionnaire. Requires all required questions answered for submission. Candidate or recruiter authorized.",
    responses={
        200: {"description": "Answers saved/submitted successfully", "model": CandidateQuestionnaireResponseSchema},
        404: {"description": "Response not found"},
        409: {"description": "Response already submitted or conflict"},
        422: {"description": "Invalid answers or required questions missing"},
        403: {"description": "Forbidden: Not authorized to modify this response"},
    },
)
async def save_questionnaire_answers(
    response_id: UUID,
    request: ResponseCreate,
    principal: Principal = Depends(),
    db: AsyncSession = Depends(get_db_session),
) -> CandidateQuestionnaireResponseSchema:
    """
    Save draft answers or submit final answers for a questionnaire.
    
    When is_final_submit=False: saves answers as draft, sets status to INCOMPLETE if not all required answered.
    When is_final_submit=True: validates all required questions answered, sets status to SUBMITTED, prevents further changes.
    
    Authorization: candidate can save own responses, recruiter/admin can save any response.
    If response already SUBMITTED, returns 403 Forbidden.
    If required questions missing on final submit, returns 422.
    
    Requirement: 4.8, 4.9, 4.10
    """
    service = QuestionnairesService(db)
    
    response = await service.save_answers(
        response_id=response_id,
        org_id=principal.organization_id,
        answers=request.answers,
        is_final_submit=request.is_final_submit,
        principal=principal,
    )
    
    if not response:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to modify this response"
        )
    
    return CandidateQuestionnaireResponseSchema.from_orm(response)
