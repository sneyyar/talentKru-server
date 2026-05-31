"""Job requisition service.

Implements requisition lifecycle management including creation, status transitions,
candidate association, and required skill management.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from typing import cast
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm.exc import StaleDataError

from app.modules.requisitions.models import (
    JobRequisition,
    RequisitionStatus,
    CandidateRequisition,
)
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.skills.models import Skill, RequisitionRequiredSkill
from app.domain_events.publisher import publish_event
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Valid requisition status transitions
VALID_REQUISITION_TRANSITIONS = {
    RequisitionStatus.OPEN: [RequisitionStatus.ON_HOLD, RequisitionStatus.CLOSED, RequisitionStatus.CANCELLED],
    RequisitionStatus.ON_HOLD: [RequisitionStatus.OPEN, RequisitionStatus.CANCELLED],
    RequisitionStatus.CLOSED: [],
    RequisitionStatus.CANCELLED: [],
}


class RequisitionService:
    """Service for managing job requisitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_requisition(
        self,
        org_id: UUID,
        job_profile_id: UUID,
        hiring_manager_user_id: UUID,
        title: str,
        department: str,
        location: str,
        created_by: UUID,
        description: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> JobRequisition:
        """
        Create a new job requisition.
        
        Status is always set to OPEN regardless of any value in the request body.
        Publishes requisition_status_changed event.
        
        Requirements: 5.1, 5.2
        """
        requisition = JobRequisition(
            job_requisition_id=uuid4(),
            organization_id=org_id,
            job_profile_id=job_profile_id,
            hiring_manager_user_id=hiring_manager_user_id,
            title=title,
            department=department,
            location=location,
            description=description,
            status=RequisitionStatus.OPEN.value,
            created_by=created_by,
        )
        
        self.db.add(requisition)
        await self.db.flush()
        
        # Publish event
        await publish_event(
            event_type="requisition_status_changed",
            payload={
                "requisition_id": str(requisition.job_requisition_id),
                "organization_id": str(org_id),
                "status": RequisitionStatus.OPEN.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            db=self.db,
            background_tasks=background_tasks,
        )
        
        return requisition

    async def transition_status(
        self,
        requisition_id: UUID,
        org_id: UUID,
        new_status: str,
        version: int,
        updated_by: UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> JobRequisition:
        """
        Transition requisition status with FSM validation.
        
        Validates against VALID_REQUISITION_TRANSITIONS dict.
        Publishes requisition_status_changed event on success.
        
        Requirements: 5.2, 5.6
        """
        # Fetch requisition
        result = await self.db.execute(
            select(JobRequisition).where(
                and_(
                    JobRequisition.job_requisition_id == requisition_id,
                    JobRequisition.organization_id == org_id,
                    JobRequisition.deleted_at.is_(None),
                )
            )
        )
        requisition = result.scalar_one_or_none()  # type: ignore[assignment]
        
        if not requisition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requisition not found",
            )
        
        # Validate status transition
        try:
            current_status = RequisitionStatus(requisition.status)
            target_status = RequisitionStatus(new_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {new_status}",
            )
        
        if target_status not in VALID_REQUISITION_TRANSITIONS.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transition from {current_status} to {target_status}",
            )
        
        # Update status
        requisition.status = target_status  # type: ignore[assignment]
        requisition.updated_by = updated_by
        
        try:
            await self.db.flush()
        except StaleDataError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource has been modified by another request",
            )
        
        # Publish event
        await publish_event(
            event_type="requisition_status_changed",
            payload={
                "requisition_id": str(requisition_id),
                "organization_id": str(org_id),
                "status": target_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            db=self.db,
            background_tasks=background_tasks,
        )
        
        return requisition

    async def associate_candidate(
        self,
        requisition_id: UUID,
        candidate_id: UUID,
        org_id: UUID,
        created_by: UUID,
    ) -> CandidateRequisition:
        """
        Associate a candidate with a requisition.
        
        Validates:
        - Requisition status is OPEN
        - Candidate status is ACTIVE or INTERVIEWING
        - No duplicate association exists
        
        Requirements: 5.3
        """
        # Fetch requisition
        result = await self.db.execute(
            select(JobRequisition).where(
                and_(
                    JobRequisition.job_requisition_id == requisition_id,
                    JobRequisition.organization_id == org_id,
                    JobRequisition.deleted_at.is_(None),
                )
            )
        )
        requisition = result.scalar_one_or_none()  # type: ignore[assignment]
        
        if not requisition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requisition not found",
            )
        
        # Validate requisition status is OPEN
        if requisition.status != RequisitionStatus.OPEN.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requisition status must be OPEN, not {requisition.status}",
            )
        
        # Fetch candidate
        result = await self.db.execute(
            select(Candidate).where(
                and_(
                    Candidate.candidate_id == candidate_id,
                    Candidate.organization_id == org_id,
                    Candidate.deleted_at.is_(None),
                )
            )
        )
        candidate = result.scalar_one_or_none()
        
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found",
            )
        
        # Validate candidate status
        if candidate.global_status not in (GlobalStatus.ACTIVE, GlobalStatus.INTERVIEWING):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Candidate status must be ACTIVE or INTERVIEWING, not {candidate.global_status}",
            )
        
        # Check for duplicate association
        result = await self.db.execute(
            select(CandidateRequisition).where(
                and_(
                    CandidateRequisition.candidate_id == candidate_id,
                    CandidateRequisition.job_requisition_id == requisition_id,
                    CandidateRequisition.deleted_at.is_(None),
                )
            )
        )
        
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate is already associated with this requisition",
            )
        
        # Create association
        candidate_requisition = CandidateRequisition(
            candidate_requisition_id=uuid4(),
            candidate_id=candidate_id,
            job_requisition_id=requisition_id,
            created_by=created_by,
        )
        
        self.db.add(candidate_requisition)
        await self.db.flush()
        
        return candidate_requisition

    async def add_required_skill(
        self,
        requisition_id: UUID,
        skill_id: UUID,
        org_id: UUID,
        required_proficiency_rank: int,
        weight: int,
        created_by: UUID,
    ) -> RequisitionRequiredSkill:
        """
        Add a required skill to a requisition.
        
        Validates:
        - proficiency_rank is 1-5
        - weight is 1-10
        - No duplicate skill requirement exists
        
        Requirements: 5.5
        """
        # Validate proficiency_rank
        if not (1 <= required_proficiency_rank <= 5):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Proficiency rank must be between 1 and 5",
            )
        
        # Validate weight
        if not (1 <= weight <= 10):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Weight must be between 1 and 10",
            )
        
        # Fetch requisition
        result = await self.db.execute(
            select(JobRequisition).where(
                and_(
                    JobRequisition.job_requisition_id == requisition_id,
                    JobRequisition.organization_id == org_id,
                    JobRequisition.deleted_at.is_(None),
                )
            )
        )
        requisition = result.scalar_one_or_none()
        
        if not requisition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requisition not found",
            )
        
        # Fetch skill
        result = await self.db.execute(
            select(Skill).where(
                and_(
                    Skill.skill_id == skill_id,
                    Skill.deleted_at.is_(None),
                )
            )
        )
        skill = result.scalar_one_or_none()
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Skill not found",
            )
        
        # Check for duplicate
        result = await self.db.execute(
            select(RequisitionRequiredSkill).where(
                and_(
                    RequisitionRequiredSkill.job_requisition_id == requisition_id,
                    RequisitionRequiredSkill.skill_id == skill_id,
                    RequisitionRequiredSkill.deleted_at.is_(None),
                )
            )
        )
        
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Skill is already required for this requisition",
            )
        
        # Create required skill
        required_skill = RequisitionRequiredSkill(
            requisition_required_skill_id=uuid4(),
            job_requisition_id=requisition_id,
            skill_id=skill_id,
            required_proficiency_rank=required_proficiency_rank,
            weight=weight,
            created_by=created_by,
        )
        
        self.db.add(required_skill)
        await self.db.flush()
        
        return required_skill

    async def get_requisition(
        self,
        requisition_id: UUID,
        org_id: UUID,
    ) -> JobRequisition:
        """
        Fetch a requisition by ID.
        
        Requirements: 5.4
        """
        result = await self.db.execute(
            select(JobRequisition).where(
                and_(
                    JobRequisition.job_requisition_id == requisition_id,
                    JobRequisition.organization_id == org_id,
                    JobRequisition.deleted_at.is_(None),
                )
            )
        )
        requisition = result.scalar_one_or_none()
        
        if not requisition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requisition not found",
            )
        
        return requisition

    async def list_requisitions(
        self,
        org_id: UUID,
        status: str | None = None,
        hiring_manager_user_id: UUID | None = None,
        department: str | None = None,
        domain: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[JobRequisition], int]:
        """
        List requisitions with optional filters.
        
        Supports filtering by status, hiring manager, department, and domain.
        
        Requirements: 5.4
        """
        # Build base query
        stmt = select(JobRequisition).where(
            and_(
                JobRequisition.organization_id == org_id,
                JobRequisition.deleted_at.is_(None),
            )
        )
        
        # Apply filters
        if status:
            try:
                status_enum = RequisitionStatus(status)
                stmt = stmt.where(JobRequisition.status == status_enum)
            except ValueError:
                pass
        
        if hiring_manager_user_id:
            stmt = stmt.where(JobRequisition.hiring_manager_user_id == hiring_manager_user_id)
        
        if department:
            stmt = stmt.where(JobRequisition.department == department)
        
        # Get total count
        count_stmt = select(func.count(JobRequisition.job_requisition_id)).where(
            and_(
                JobRequisition.organization_id == org_id,
                JobRequisition.deleted_at.is_(None),
            )
        )
        
        if status:
            try:
                status_enum = RequisitionStatus(status)
                count_stmt = count_stmt.where(JobRequisition.status == status_enum)
            except ValueError:
                pass
        
        if hiring_manager_user_id:
            count_stmt = count_stmt.where(JobRequisition.hiring_manager_user_id == hiring_manager_user_id)
        
        if department:
            count_stmt = count_stmt.where(JobRequisition.department == department)
        
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar() or 0
        
        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        
        result = await self.db.execute(stmt)
        requisitions = cast(list[JobRequisition], result.scalars().all())
        
        return requisitions, total_count
