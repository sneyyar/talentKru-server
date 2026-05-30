"""
Job posting router for CRUD operations.

Endpoints:
- POST /api/v1/job-postings: Create a new job posting (Recruiter only)
- GET /api/v1/job-postings: List job postings (Recruiter, Administrator, HiringManager)
- GET /api/v1/job-postings/{job_posting_id}: Get a specific job posting (Recruiter, Administrator, HiringManager)
- PATCH /api/v1/job-postings/{job_posting_id}: Update a job posting (Recruiter only)
- DELETE /api/v1/job-postings/{job_posting_id}: Delete a job posting (Recruiter only)

Requirements: 4.2, 4.5, 4.6
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.job_posting.schemas import (
    JobPostingCreate,
    JobPostingFilter,
    JobPostingResponse,
)
from app.modules.job_posting.service import JobPostingService

router = APIRouter(prefix="/api/v1/job-postings", tags=["job-postings"])


@router.post(
    "",
    response_model=JobPostingResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_job_posting",
    summary="Create a new job posting",
    description="Create a new job posting with job profile, description, locations, and salary range. Only Recruiters can create job postings. Returns 201 Created.",
    responses={
        201: {"description": "Job posting created successfully", "model": JobPostingResponse},
        400: {"description": "Invalid job profile or request data"},
        403: {"description": "Forbidden: User does not have Recruiter role"},
    },
)
async def create_job_posting_endpoint(
    request: JobPostingCreate,
    principal: Principal = Depends(require_role("Recruiter")),
    db: AsyncSession = Depends(get_db_session),
) -> JobPostingResponse:
    """
    Create a new job posting.
    
    Validates that the job_profile_id exists, belongs to the organization,
    and is not soft-deleted. Returns 201 Created on success.
    
    Requirements: 4.2, 4.3, 4.6
    
    Args:
        request: Job posting creation request with job_profile_id, description, locations, and salary range
        principal: Authenticated principal with Recruiter role and organization context
        db: Database session
        
    Returns:
        JobPostingResponse with created job posting details
        
    Raises:
        HTTPException: 400 if job_profile_id is invalid, deleted, or belongs to different org
    """
    service = JobPostingService(db)
    job_posting = await service.create_posting(
        org_id=principal.organization_id,
        job_profile_id=request.job_profile_id,
        description=request.description,
        work_locations=request.work_locations,
        salary_min=request.salary_min,
        salary_max=request.salary_max,
        salary_currency=request.salary_currency,
        sourcing_channel=request.sourcing_channel,
    )
    await db.commit()
    return JobPostingResponse.from_orm(job_posting)


@router.get(
    "",
    response_model=list[JobPostingResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_job_postings",
    summary="List job postings with optional filters",
    description="List all job postings in the organization with optional filters for location, salary range, and sourcing channel. Supports pagination with max 50 per page. Requires Recruiter, Administrator, or HiringManager role.",
    responses={
        200: {"description": "Job postings retrieved successfully", "model": list[JobPostingResponse]},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_job_postings_endpoint(
    location: str | None = Query(None, description="Filter by work location (exact match in work_locations array)"),
    salary_filter_min: float | None = Query(None, ge=0, description="Minimum salary filter value for overlap check"),
    salary_filter_max: float | None = Query(None, ge=0, description="Maximum salary filter value for overlap check"),
    sourcing_channel: str | None = Query(None, description="Filter by sourcing channel (exact match)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        50, ge=1, le=50, description="Number of job postings per page (max 50)"
    ),
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> list[JobPostingResponse]:
    """
    List job postings in the organization with optional filters.
    
    Applies filters for:
    - Location: exact match in work_locations array
    - Salary overlap: posting.salary_min <= filter_max AND posting.salary_max >= filter_min
    - Sourcing channel: exact match
    
    Supports pagination with max 50 results per page.
    
    Requirements: 4.2, 4.5, 4.6
    
    Args:
        location: Optional location filter (exact match in work_locations)
        salary_filter_min: Optional minimum salary filter value
        salary_filter_max: Optional maximum salary filter value
        sourcing_channel: Optional sourcing channel filter
        page: Page number (1-indexed)
        page_size: Results per page (max 50)
        principal: Authenticated principal with organization context
        db: Database session
        
    Returns:
        List of JobPostingResponse objects matching filters
    """
    offset = (page - 1) * page_size
    service = JobPostingService(db)
    job_postings = await service.list_postings(
        org_id=principal.organization_id,
        location=location,
        salary_filter_min=salary_filter_min,
        salary_filter_max=salary_filter_max,
        sourcing_channel=sourcing_channel,
        offset=offset,
        limit=page_size,
    )
    return [JobPostingResponse.from_orm(jp) for jp in job_postings]


@router.get(
    "/{job_posting_id}",
    response_model=JobPostingResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_job_posting",
    summary="Retrieve a job posting by ID",
    description="Retrieve a specific job posting by ID. Requires Recruiter, Administrator, or HiringManager role.",
    responses={
        200: {"description": "Job posting retrieved successfully", "model": JobPostingResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Job posting not found"},
    },
)
async def get_job_posting_endpoint(
    job_posting_id: UUID,
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> JobPostingResponse:
    """
    Get a specific job posting.
    
    Retrieves a job posting by ID with organization scoping.
    
    Requirements: 4.2, 4.6
    
    Args:
        job_posting_id: Job posting ID to retrieve
        principal: Authenticated principal with organization context
        db: Database session
        
    Returns:
        JobPostingResponse with job posting details
        
    Raises:
        HTTPException: 404 if job posting not found or belongs to different org
    """
    service = JobPostingService(db)
    job_posting = await service.get_posting(
        posting_id=job_posting_id,
        org_id=principal.organization_id,
    )
    if not job_posting:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return JobPostingResponse.from_orm(job_posting)


@router.patch(
    "/{job_posting_id}",
    response_model=JobPostingResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_job_posting",
    summary="Update a job posting",
    description="Update a job posting details. Only Recruiters can update job postings. Returns 403 for any other role.",
    responses={
        200: {"description": "Job posting updated successfully", "model": JobPostingResponse},
        403: {"description": "Forbidden: User does not have Recruiter role"},
        404: {"description": "Not Found: Job posting not found"},
        409: {"description": "Conflict: Optimistic locking version mismatch"},
    },
)
async def update_job_posting_endpoint(
    job_posting_id: UUID,
    request: JobPostingCreate,
    principal: Principal = Depends(require_role("Recruiter")),
    db: AsyncSession = Depends(get_db_session),
) -> JobPostingResponse:
    """
    Update a job posting.
    
    Updates job posting details with organization scoping. Uses optimistic locking
    via VersionMixin to prevent concurrent modification conflicts.
    
    Requirements: 4.2, 4.6
    
    Args:
        job_posting_id: Job posting ID to update
        request: Update request with job posting details
        principal: Authenticated principal with Recruiter role and organization context
        db: Database session
        
    Returns:
        JobPostingResponse with updated job posting details
        
    Raises:
        HTTPException: 404 if job posting not found or belongs to different org
        HTTPException: 409 if job posting has been modified by another user (version mismatch)
    """
    service = JobPostingService(db)
    job_posting = await service.update_posting(
        posting_id=job_posting_id,
        org_id=principal.organization_id,
        description=request.description,
        work_locations=request.work_locations,
        salary_min=request.salary_min,
        salary_max=request.salary_max,
        salary_currency=request.salary_currency,
        sourcing_channel=request.sourcing_channel,
    )
    await db.commit()
    return JobPostingResponse.from_orm(job_posting)


@router.delete(
    "/{job_posting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_job_posting",
    summary="Delete a job posting",
    description="Soft-delete a job posting. Only Recruiters can delete job postings. Returns 403 for any other role.",
    responses={
        204: {"description": "Job posting deleted successfully"},
        403: {"description": "Forbidden: User does not have Recruiter role"},
        404: {"description": "Not Found: Job posting not found"},
        409: {"description": "Conflict: Optimistic locking version mismatch"},
    },
)
async def delete_job_posting_endpoint(
    job_posting_id: UUID,
    principal: Principal = Depends(require_role("Recruiter")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a job posting.
    
    Soft-deletes a job posting by setting deleted_at timestamp. The record is retained
    for audit purposes but excluded from search and listing results.
    
    Requirements: 4.2, 4.6
    
    Args:
        job_posting_id: Job posting ID to delete
        principal: Authenticated principal with Recruiter role and organization context
        db: Database session
        
    Raises:
        HTTPException: 404 if job posting not found or belongs to different org
        HTTPException: 409 if job posting has been modified by another user (version mismatch)
    """
    service = JobPostingService(db)
    await service.delete_posting(
        posting_id=job_posting_id,
        org_id=principal.organization_id,
    )
    await db.commit()
