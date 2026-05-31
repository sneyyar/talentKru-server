"""
Job posting service.

Provides:
- JobPostingService: Job posting CRUD, salary overlap filtering, location filtering
- create_posting: validate job_profile_id exists and belongs to org, insert JobPosting
- list_postings: org-scoped query with location, salary overlap, and sourcing channel filters
- update_posting / delete_posting: org-scoped with VersionMixin optimistic locking

Requirements: 4.2, 4.3, 4.4, 4.5
"""

from typing import cast
from uuid import UUID
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.modules.job_posting.models import JobPosting
from app.modules.job_profile.models import JobProfile


class JobPostingService:
    """
    Job posting service for managing job postings.
    
    Requirements: 4.2, 4.3, 4.4, 4.5
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the job posting service.
        
        Args:
            db: AsyncSession for database access
        """
        self.db = db

    async def create_posting(
        self,
        org_id: UUID,
        job_profile_id: UUID,
        description: str,
        work_locations: list[str],
        salary_min: float,
        salary_max: float,
        salary_currency: str,
        sourcing_channel: str,
    ) -> JobPosting:
        """
        Create a new job posting.
        
        Validates that the job_profile_id exists, belongs to the organization,
        and is not soft-deleted.
        
        Args:
            org_id: Organization ID
            job_profile_id: Job profile ID to link
            description: Job description
            work_locations: List of work location strings
            salary_min: Minimum salary
            salary_max: Maximum salary
            salary_currency: ISO 4217 currency code
            sourcing_channel: Sourcing channel (e.g., LinkedIn, Indeed)
            
        Returns:
            Created JobPosting entity
            
        Raises:
            HTTPException: 400 if job_profile_id is invalid, deleted, or belongs to different org
            
        Requirements: 4.3, 4.4
        """
        # Validate job_profile_id exists, belongs to org, and is not deleted
        profile = await self.db.get(JobProfile, job_profile_id)
        if (
            not profile
            or profile.organization_id != org_id
            or profile.deleted_at is not None
        ):
            raise HTTPException(
                status_code=400,
                detail="A valid JobProfile is required to create a job posting",
            )
        
        # Create and insert job posting
        posting = JobPosting(
            organization_id=org_id,
            job_profile_id=job_profile_id,
            description=description,
            work_locations=work_locations,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            sourcing_channel=sourcing_channel,
        )
        self.db.add(posting)
        await self.db.flush()
        
        return posting

    async def list_postings(
        self,
        org_id: UUID,
        location: str | None = None,
        salary_filter_min: float | None = None,
        salary_filter_max: float | None = None,
        sourcing_channel: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[JobPosting]:
        """
        List job postings with optional filters.
        
        Applies filters for:
        - Location: exact match in work_locations array
        - Salary overlap: posting.salary_min <= filter_max AND posting.salary_max >= filter_min
        - Sourcing channel: exact match
        
        Args:
            org_id: Organization ID for scoping
            location: Optional location filter (exact match in work_locations)
            salary_filter_min: Optional minimum salary filter
            salary_filter_max: Optional maximum salary filter
            sourcing_channel: Optional sourcing channel filter
            offset: Pagination offset
            limit: Pagination limit (max 50)
            
        Returns:
            List of JobPosting entities matching filters
            
        Requirements: 4.5
        """
        # Start with org-scoped query excluding soft-deleted
        stmt = select(JobPosting).where(
            and_(
                JobPosting.organization_id == org_id,
                JobPosting.deleted_at.is_(None),
            )
        )
        
        # Apply location filter if provided
        if location:
            stmt = stmt.where(JobPosting.work_locations.contains([location]))  # type: ignore[attr-defined]
        
        # Apply salary overlap filter if both min and max provided
        if salary_filter_min is not None and salary_filter_max is not None:
            # Overlap condition: posting.salary_min <= filter_max AND posting.salary_max >= filter_min
            stmt = stmt.where(
                and_(
                    JobPosting.salary_min <= salary_filter_max,  # type: ignore[assignment]
                    JobPosting.salary_max >= salary_filter_min,  # type: ignore[assignment]
                )
            )
        
        # Apply sourcing channel filter if provided
        if sourcing_channel:
            stmt = stmt.where(JobPosting.sourcing_channel == sourcing_channel)  # type: ignore[assignment]
        
        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        
        result = await self.db.execute(stmt)
        return cast(list[JobPosting], result.scalars().all())  # type: ignore[assignment]

    async def update_posting(
        self,
        posting_id: UUID,
        org_id: UUID,
        description: str | None = None,
        work_locations: list[str] | None = None,
        salary_min: float | None = None,
        salary_max: float | None = None,
        salary_currency: str | None = None,
        sourcing_channel: str | None = None,
        version: int | None = None,
    ) -> JobPosting:
        """
        Update a job posting.
        
        Uses VersionMixin optimistic locking. If version is provided and doesn't match,
        raises an exception.
        
        Args:
            posting_id: Job posting ID
            org_id: Organization ID for scoping
            description: New description (optional)
            work_locations: New work locations (optional)
            salary_min: New minimum salary (optional)
            salary_max: New maximum salary (optional)
            salary_currency: New currency (optional)
            sourcing_channel: New sourcing channel (optional)
            version: Expected version for optimistic locking (optional)
            
        Returns:
            Updated JobPosting entity
            
        Raises:
            HTTPException: 404 if posting not found or belongs to different org
            
        Requirements: 4.2, 7.5
        """
        # Fetch posting with org scoping
        stmt = select(JobPosting).where(
            and_(
                JobPosting.job_posting_id == posting_id,
                JobPosting.organization_id == org_id,
                JobPosting.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        posting = result.scalar_one_or_none()  # type: ignore[assignment]  # type: ignore[assignment]
        
        if not posting:
            raise HTTPException(status_code=404, detail="Job posting not found")
        
        # Check version for optimistic locking if provided
        if version is not None and posting.version != version:
            raise HTTPException(
                status_code=409,
                detail="Job posting has been modified by another user",
            )
        
        # Update fields if provided
        if description is not None:
            posting.description = description  # type: ignore[assignment]
        if work_locations is not None:
            posting.work_locations = work_locations  # type: ignore[assignment]
        if salary_min is not None:
            posting.salary_min = salary_min  # type: ignore[assignment]
        if salary_max is not None:
            posting.salary_max = salary_max  # type: ignore[assignment]
        if salary_currency is not None:
            posting.salary_currency = salary_currency  # type: ignore[assignment]
        if sourcing_channel is not None:
            posting.sourcing_channel = sourcing_channel  # type: ignore[assignment]
        
        await self.db.flush()
        return posting

    async def delete_posting(
        self,
        posting_id: UUID,
        org_id: UUID,
        version: int | None = None,
    ) -> None:
        """
        Soft-delete a job posting.
        
        Uses VersionMixin optimistic locking. If version is provided and doesn't match,
        raises an exception.
        
        Args:
            posting_id: Job posting ID
            org_id: Organization ID for scoping
            version: Expected version for optimistic locking (optional)
            
        Raises:
            HTTPException: 404 if posting not found or belongs to different org
            
        Requirements: 4.2, 7.5
        """
        # Fetch posting with org scoping
        stmt = select(JobPosting).where(
            and_(
                JobPosting.job_posting_id == posting_id,
                JobPosting.organization_id == org_id,
                JobPosting.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        posting = result.scalar_one_or_none()  # type: ignore[assignment]
        
        if not posting:
            raise HTTPException(status_code=404, detail="Job posting not found")
        
        # Check version for optimistic locking if provided
        if version is not None and posting.version != version:
            raise HTTPException(
                status_code=409,
                detail="Job posting has been modified by another user",
            )
        
        # Soft delete: set deleted_at (deleted_by is set by AuditMixin listener)
        from datetime import datetime, timezone
        posting.deleted_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        
        await self.db.flush()

    async def get_posting(
        self,
        posting_id: UUID,
        org_id: UUID,
    ) -> JobPosting | None:
        """
        Get a job posting by ID.
        
        Args:
            posting_id: Job posting ID
            org_id: Organization ID for scoping
            
        Returns:
            JobPosting entity or None if not found
            
        Requirements: 4.2
        """
        stmt = select(JobPosting).where(
            and_(
                JobPosting.job_posting_id == posting_id,
                JobPosting.organization_id == org_id,
                JobPosting.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()  # type: ignore[assignment]
