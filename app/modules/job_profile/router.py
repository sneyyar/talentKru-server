"""
Job profile router for CRUD operations.

Endpoints:
- POST /api/v1/job-profiles: Create a new job profile (Recruiter only)
- GET /api/v1/job-profiles: List job profiles (Recruiter, Administrator, HiringManager)
- GET /api/v1/job-profiles/{job_profile_id}: Get a specific job profile (Recruiter, Administrator, HiringManager)
- PATCH /api/v1/job-profiles/{job_profile_id}: Update a job profile (Recruiter only)
- DELETE /api/v1/job-profiles/{job_profile_id}: Delete a job profile (Recruiter only)

Requirements: 4.1, 4.6
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.job_profile.schemas import (
    JobProfileCreate,
    JobProfileResponse,
)
from app.modules.job_profile.service import JobProfileService

router = APIRouter(prefix="/job-profiles", tags=["job-profiles"])


@router.post(
    "",
    response_model=JobProfileResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_job_profile",
    summary="Create a new job profile",
    description="Create a new job profile with optional associated skills. Only users with the Recruiter role can create job profiles.",
    responses={
        201: {
            "description": "Job profile created successfully",
            "model": JobProfileResponse,
        },
        400: {
            "description": "Invalid request data (e.g., invalid proficiency rank or designation)",
        },
        403: {
            "description": "Forbidden: User does not have the Recruiter role",
        },
        422: {
            "description": "Unprocessable Entity: Invalid skill proficiency rank or designation",
        },
    },
)
async def create_job_profile_endpoint(
    request: JobProfileCreate,
    principal: Principal = Depends(require_role("Recruiter")),
    db: AsyncSession = Depends(get_db_session),
) -> JobProfileResponse:
    """
    Create a new job profile.
    
    Requirements: 4.1, 4.6
    
    Args:
        request: Job profile creation request with name and optional skills
        principal: Authenticated principal with Recruiter role
        db: Database session
        
    Returns:
        JobProfileResponse with created job profile details
        
    Raises:
        HTTPException(403): If user does not have Recruiter role
        HTTPException(422): If skill proficiency rank is not 1-5 or designation is invalid
    """
    service = JobProfileService(db)
    job_profile = await service.create_job_profile(
        org_id=principal.organization_id,
        data=request,
        created_by=principal.user_id,
    )
    await db.commit()
    return JobProfileResponse.from_orm(job_profile)


@router.get(
    "",
    response_model=list[JobProfileResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_job_profiles",
    summary="List job profiles",
    description="List all job profiles in the organization with pagination. Accessible to Recruiters, Administrators, and HiringManagers.",
    responses={
        200: {
            "description": "List of job profiles retrieved successfully",
            "model": list[JobProfileResponse],
        },
        403: {
            "description": "Forbidden: User does not have required role (Recruiter, Administrator, or HiringManager)",
        },
    },
)
async def list_job_profiles_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        50, ge=1, le=100, description="Number of job profiles per page"
    ),
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> list[JobProfileResponse]:
    """
    List job profiles in the organization.
    
    Requirements: 4.1, 4.6
    
    Args:
        page: Page number for pagination (1-indexed, default 1)
        page_size: Number of records per page (default 50, max 100)
        principal: Authenticated principal with required role
        db: Database session
        
    Returns:
        List of JobProfileResponse objects
        
    Raises:
        HTTPException(403): If user does not have required role
    """
    service = JobProfileService(db)
    offset = (page - 1) * page_size
    job_profiles = await service.list_job_profiles(
        org_id=principal.organization_id,
        offset=offset,
        limit=page_size,
    )
    return [JobProfileResponse.from_orm(jp) for jp in job_profiles]


@router.get(
    "/{job_profile_id}",
    response_model=JobProfileResponse,
    status_code=status.HTTP_200_OK,
    operation_id="get_job_profile",
    summary="Get a job profile",
    description="Retrieve a specific job profile by ID. Accessible to Recruiters, Administrators, and HiringManagers.",
    responses={
        200: {
            "description": "Job profile retrieved successfully",
            "model": JobProfileResponse,
        },
        403: {
            "description": "Forbidden: User does not have required role (Recruiter, Administrator, or HiringManager)",
        },
        404: {
            "description": "Not Found: Job profile does not exist or has been deleted",
        },
    },
)
async def get_job_profile_endpoint(
    job_profile_id: UUID,
    principal: Principal = Depends(require_role("Recruiter", "Administrator", "HiringManager")),
    db: AsyncSession = Depends(get_db_session),
) -> JobProfileResponse:
    """
    Get a specific job profile.
    
    Requirements: 4.1, 4.6
    
    Args:
        job_profile_id: UUID of the job profile to retrieve
        principal: Authenticated principal with required role
        db: Database session
        
    Returns:
        JobProfileResponse with job profile details
        
    Raises:
        HTTPException(403): If user does not have required role
        HTTPException(404): If job profile does not exist or is deleted
    """
    service = JobProfileService(db)
    job_profile = await service.get_job_profile(
        org_id=principal.organization_id,
        job_profile_id=job_profile_id,
    )
    return JobProfileResponse.from_orm(job_profile)


@router.patch(
    "/{job_profile_id}",
    response_model=JobProfileResponse,
    status_code=status.HTTP_200_OK,
    operation_id="update_job_profile",
    summary="Update a job profile",
    description="Update a job profile name and/or associated skills. Only users with the Recruiter role can update job profiles.",
    responses={
        200: {
            "description": "Job profile updated successfully",
            "model": JobProfileResponse,
        },
        400: {
            "description": "Invalid request data (e.g., invalid proficiency rank or designation)",
        },
        403: {
            "description": "Forbidden: User does not have the Recruiter role",
        },
        404: {
            "description": "Not Found: Job profile does not exist or has been deleted",
        },
        409: {
            "description": "Conflict: Optimistic locking version mismatch",
        },
        422: {
            "description": "Unprocessable Entity: Invalid skill proficiency rank or designation",
        },
    },
)
async def update_job_profile_endpoint(
    job_profile_id: UUID,
    request: JobProfileCreate,
    principal: Principal = Depends(require_role("Recruiter")),
    db: AsyncSession = Depends(get_db_session),
) -> JobProfileResponse:
    """
    Update a job profile.
    
    Requirements: 4.1, 4.6
    
    Args:
        job_profile_id: UUID of the job profile to update
        request: Job profile update request with name and/or skills
        principal: Authenticated principal with Recruiter role
        db: Database session
        
    Returns:
        JobProfileResponse with updated job profile details
        
    Raises:
        HTTPException(403): If user does not have Recruiter role
        HTTPException(404): If job profile does not exist or is deleted
        HTTPException(409): If optimistic locking version is stale
        HTTPException(422): If skill proficiency rank is not 1-5 or designation is invalid
    """
    service = JobProfileService(db)
    job_profile = await service.update_job_profile(
        org_id=principal.organization_id,
        job_profile_id=job_profile_id,
        name=request.name,
        skills=request.skills,
    )
    await db.commit()
    return JobProfileResponse.from_orm(job_profile)


@router.delete(
    "/{job_profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_job_profile",
    summary="Delete a job profile",
    description="Soft-delete a job profile. Only users with the Recruiter role can delete job profiles. Returns 403 Forbidden for any other role.",
    responses={
        204: {
            "description": "Job profile deleted successfully",
        },
        403: {
            "description": "Forbidden: User does not have the Recruiter role",
        },
        404: {
            "description": "Not Found: Job profile does not exist or has been deleted",
        },
    },
)
async def delete_job_profile_endpoint(
    job_profile_id: UUID,
    principal: Principal = Depends(require_role("Recruiter")),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete a job profile.
    
    Requirements: 4.1, 4.6
    
    Args:
        job_profile_id: UUID of the job profile to delete
        principal: Authenticated principal with Recruiter role
        db: Database session
        
    Raises:
        HTTPException(403): If user does not have Recruiter role
        HTTPException(404): If job profile does not exist or is deleted
    """
    service = JobProfileService(db)
    await service.delete_job_profile(
        org_id=principal.organization_id,
        job_profile_id=job_profile_id,
        deleted_by=principal.user_id,
    )
    await db.commit()
