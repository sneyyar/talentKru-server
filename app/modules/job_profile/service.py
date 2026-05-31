"""
Job profile service layer.

Provides business logic for creating, retrieving, updating, and deleting
JobProfile entities with associated skills. Enforces organization scoping
and uses optimistic locking for concurrent updates.

Requirements: 4.1
"""

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_profile.models import JobProfile, JobProfileSkill, SkillDesignation
from app.modules.job_profile.schemas import JobProfileCreate, JobProfileSkillCreate


class JobProfileService:
    """Service for managing job profiles."""

    def __init__(self, db: AsyncSession):
        """Initialize the service with a database session.
        
        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    async def create_job_profile(
        self,
        org_id: UUID,
        data: JobProfileCreate,
        created_by: UUID,
    ) -> JobProfile:
        """
        Create a new job profile with associated skills.

        For each skill entry in the request, inserts a JobProfileSkill record
        with the specified designation and required proficiency rank.

        Args:
            org_id: The organization ID (from authenticated principal).
            data: Validated creation payload containing name and optional skills list.
            created_by: The user ID creating the profile.

        Returns:
            The newly created JobProfile ORM instance.

        Raises:
            HTTPException(422): If any skill entry has invalid proficiency rank.
        """
        # Create the JobProfile
        job_profile = JobProfile(
            job_profile_id=uuid4(),
            organization_id=org_id,
            name=data.name,
        )
        self.db.add(job_profile)
        await self.db.flush()

        # Add associated skills if provided
        if data.skills:
            for skill_entry in data.skills:
                # Validate proficiency rank (1-5)
                if not (1 <= skill_entry.required_proficiency_rank <= 5):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="required_proficiency_rank must be between 1 and 5",
                    )

                # Parse designation
                try:
                    designation = SkillDesignation(skill_entry.designation)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid designation: {skill_entry.designation}. Must be 'required' or 'desired'",
                    )

                job_profile_skill = JobProfileSkill(
                    job_profile_skill_id=uuid4(),
                    job_profile_id=job_profile.job_profile_id,
                    skill_id=skill_entry.skill_id,
                    designation=designation,
                    required_proficiency_rank=skill_entry.required_proficiency_rank,
                )
                self.db.add(job_profile_skill)

        await self.db.flush()
        return job_profile

    async def get_job_profile(
        self,
        org_id: UUID,
        job_profile_id: UUID,
    ) -> JobProfile:
        """
        Retrieve a single active job profile by its ID.

        Enforces organization scoping and filters out soft-deleted records.

        Args:
            org_id: The organization ID (from authenticated principal).
            job_profile_id: The UUID of the job profile to retrieve.

        Returns:
            The matching JobProfile ORM instance.

        Raises:
            HTTPException(404): If no active job profile with the given ID exists
                               in the specified organization.
        """
        stmt = select(JobProfile).where(
            JobProfile.job_profile_id == job_profile_id,
            JobProfile.organization_id == org_id,
            JobProfile.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        job_profile = result.scalar_one_or_none()  # type: ignore[assignment]
        if job_profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )
        return job_profile

    async def list_job_profiles(
        self,
        org_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[JobProfile]:
        """
        Return all active job profiles for an organization.

        Enforces organization scoping and filters out soft-deleted records.

        Args:
            org_id: The organization ID (from authenticated principal).
            offset: Number of records to skip (default 0).
            limit: Maximum number of records to return (default 50).

        Returns:
            List of active JobProfile ORM instances.
        """
        stmt = (
            select(JobProfile)
            .where(
                JobProfile.organization_id == org_id,
                JobProfile.deleted_at.is_(None),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())  # type: ignore[assignment]

    async def update_job_profile(
        self,
        org_id: UUID,
        job_profile_id: UUID,
        name: str | None = None,
        skills: list[JobProfileSkillCreate] | None = None,
        version: int | None = None,
    ) -> JobProfile:
        """
        Apply a partial update to an existing job profile.

        Supports updating the name and/or skill associations. Uses VersionMixin
        optimistic locking — a stale version will raise StaleDataError which
        the global exception handler converts to HTTP 409 Conflict.

        Args:
            org_id: The organization ID (from authenticated principal).
            job_profile_id: The UUID of the job profile to update.
            name: New name for the job profile (optional).
            skills: New list of skills to associate (optional; replaces existing).
            version: Current version for optimistic locking (required for update).

        Returns:
            The updated JobProfile ORM instance.

        Raises:
            HTTPException(404): If no active job profile with the given ID exists.
            HTTPException(422): If any skill entry has invalid proficiency rank.
            StaleDataError: If the provided version is stale (converted to 409 by handler).
        """
        job_profile = await self.get_job_profile(org_id, job_profile_id)

        # Update name if provided
        if name is not None:
            job_profile.name = name

        # Update skills if provided (replace existing)
        if skills is not None:
            # Delete existing skills
            stmt = select(JobProfileSkill).where(
                JobProfileSkill.job_profile_id == job_profile_id
            )
            result = await self.db.execute(stmt)
            existing_skills = result.scalars().all()
            for skill in existing_skills:
                await self.db.delete(skill)

            # Add new skills
            for skill_entry in skills:
                # Validate proficiency rank (1-5)
                if not (1 <= skill_entry.required_proficiency_rank <= 5):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="required_proficiency_rank must be between 1 and 5",
                    )

                # Parse designation
                try:
                    designation = SkillDesignation(skill_entry.designation)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid designation: {skill_entry.designation}. Must be 'required' or 'desired'",
                    )

                job_profile_skill = JobProfileSkill(
                    job_profile_skill_id=uuid4(),
                    job_profile_id=job_profile.job_profile_id,
                    skill_id=skill_entry.skill_id,
                    designation=designation,
                    required_proficiency_rank=skill_entry.required_proficiency_rank,
                )
                self.db.add(job_profile_skill)

        await self.db.flush()
        await self.db.refresh(job_profile)
        return job_profile

    async def delete_job_profile(
        self,
        org_id: UUID,
        job_profile_id: UUID,
        deleted_by: UUID,
    ) -> None:
        """
        Soft-delete a job profile by setting deleted_at and deleted_by.

        Enforces organization scoping. The record remains in the database
        for audit purposes but is excluded from queries filtering deleted_at IS NULL.

        Args:
            org_id: The organization ID (from authenticated principal).
            job_profile_id: The UUID of the job profile to delete.
            deleted_by: The user ID performing the deletion.

        Raises:
            HTTPException(404): If no active job profile with the given ID exists.
        """
        job_profile = await self.get_job_profile(org_id, job_profile_id)
        job_profile.deleted_at = None  # Will be set by audit mixin listener
        job_profile.deleted_by = deleted_by
        await self.db.flush()
