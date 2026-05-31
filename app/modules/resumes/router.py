"""Resume router.

Endpoints:
- POST /api/v1/resumes/upload — Upload a resume file (multipart/form-data)
- GET /api/v1/resumes/{resume_id} — Retrieve resume metadata and parsed data

Note: GET /api/v1/candidates/{candidate_id}/resumes is implemented in the candidates router.

Requirements: 2.2, 2.9, 2.10
"""

from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import require_role
from app.modules.resumes.models import Resume, ParseStatus
from app.modules.resumes.schemas import ResumeUploadResponse, ResumeResponse
from app.modules.resumes.service import ResumeService
from app.modules.resumes.storage import get_storage_service
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="upload_resume",
    summary="Upload a resume file",
    description="Upload a resume file in PDF, DOC, or DOCX format (max 10 MB). Requires Recruiter or Administrator role. Returns 202 Accepted with resume ID and parsing status.",
    responses={
        202: {"description": "Resume accepted for processing", "model": ResumeUploadResponse},
        400: {"description": "Invalid request data"},
        403: {"description": "Forbidden: User does not have required role"},
        422: {"description": "Unprocessable Entity: Unsupported file format or size exceeds 10 MB"},
    },
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (PDF, DOC, or DOCX)"),
    candidate_id: UUID | None = Query(None, description="Optional candidate ID to associate with the resume"),
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> ResumeUploadResponse:
    """
    Upload a resume file.
    
    Requirement 2.2: Accept only PDF, DOC, DOCX formats with max 10 MB.
    Requirement 2.3: Return 422 for unsupported format or size > 10 MB.
    Requirement 2.5: Enqueue background task for resume ingestion.
    
    Requirements: 2.2, 2.9, 2.10
    """
    # Read file content
    file_bytes = await file.read()
    
    # Use ResumeService to handle upload
    storage_service = get_storage_service()
    resume_service = ResumeService(db, storage_service)
    
    resume = await resume_service.upload_resume(
        file_bytes=file_bytes,
        filename=file.filename or "resume",
        mime_type=file.content_type,
        org_id=principal.organization_id,
        uploaded_by=principal.user_id,
        candidate_id=candidate_id,
        background_tasks=background_tasks,
    )
    
    await db.commit()
    
    return ResumeUploadResponse(
        resume_id=resume.resume_id,
        parse_status=resume.parse_status,
    )


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_resume",
    summary="Retrieve resume metadata and parsed data",
    description="Retrieve a resume by ID with all metadata and parsed fields. Requires Recruiter, Administrator, or HiringManager role.",
    responses={
        200: {"description": "Resume retrieved successfully", "model": ResumeResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Resume not found"},
    },
)
async def get_resume(
    resume_id: UUID,
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> ResumeResponse:
    """
    Retrieve resume metadata and parsed data.
    
    Requirement 2.9: Support retrieving resume metadata and parsed fields.
    Requirement 2.10: Restrict to Recruiter, Administrator, HiringManager roles.
    
    Requirements: 2.9, 2.10
    """
    result = await db.execute(
        select(Resume).where(
            and_(
                Resume.resume_id == resume_id,
                Resume.organization_id == principal.organization_id,
                Resume.deleted_at.is_(None),
            )
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )
    
    return ResumeResponse.from_orm(resume)
