"""Candidate availability service."""

from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.decorators import transactional, read_only
from app.modules.availability.models import (
    CandidateAvailabilitySlot,
    AvailabilityStatus,
    AvailabilityInterviewType,
)
from app.modules.slots.models import InterviewSlot, SlotStatus
from app.observability.logging import get_logger

logger = get_logger(__name__)

MIN_AVAILABILITY_MINUTES = 30
MAX_AVAILABILITY_MINUTES = 480
MIN_HOURS_IN_FUTURE = 1
MAX_ACTIVE_SLOTS = 50


class CandidateAvailabilityService:
    """Service for managing candidate availability slots.
    
    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
    """

    def __init__(self, db: AsyncSession):
        """Initialize the service with a database session.
        
        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    @transactional()
    async def create_availability(
        self,
        candidate_id: UUID,
        org_id: UUID,
        interview_type: str,
        start_time: datetime,
        end_time: datetime,
        timezone_str: str,
        created_by: UUID,
    ) -> CandidateAvailabilitySlot:
        """Create a new availability slot for a candidate.
        
        Validates slot duration, future timing, and active slot limit.
        
        Args:
            candidate_id: The candidate's ID
            org_id: The organization ID
            interview_type: Type of interview (RECRUITER_SCREEN, MANAGER_SCREEN, LOOP_INTERVIEW)
            start_time: UTC start time of availability
            end_time: UTC end time of availability
            timezone_str: IANA timezone identifier
            created_by: User ID of the creator
            
        Returns:
            The created CandidateAvailabilitySlot
            
        Raises:
            HTTPException 422: If validation fails
            HTTPException 409: If active slot limit exceeded
            
        Requirements: 7.1, 7.2, 7.3, 7.6
        """
        # Validate interview type
        valid_types = {AvailabilityInterviewType.RECRUITER_SCREEN.value,
                       AvailabilityInterviewType.MANAGER_SCREEN.value,
                       AvailabilityInterviewType.LOOP_INTERVIEW.value}
        if interview_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid interview type: {interview_type}",
            )

        # Validate slot timing and duration
        await self._validate_slot(start_time, end_time)

        # Check active slot limit
        await self._check_active_slot_limit(candidate_id, org_id)

        # Create the slot
        slot = CandidateAvailabilitySlot(
            candidate_id=candidate_id,
            organization_id=org_id,
            interview_type=interview_type,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone_str,
            status=AvailabilityStatus.ACTIVE.value,
        )
        self.db.add(slot)
        await self.db.flush()

        logger.info(
            "availability_slot_created",
            slot_id=str(slot.candidate_availability_slot_id),
            candidate_id=str(candidate_id),
            org_id=str(org_id),
            interview_type=interview_type,
        )

        return slot

    @transactional()
    async def cancel_availability(
        self,
        slot_id: UUID,
        org_id: UUID,
        candidate_id: UUID,
        cancelled_by: UUID,
    ) -> CandidateAvailabilitySlot:
        """Cancel a candidate availability slot.
        
        Automatically cancels any overlapping interview slots that are in SCHEDULED status.
        
        Args:
            slot_id: The availability slot ID to cancel
            org_id: The organization ID
            candidate_id: The candidate ID
            cancelled_by: User ID of the canceller
            
        Returns:
            The cancelled CandidateAvailabilitySlot
            
        Requirements: 7.1, 7.4, 7.5
        """
        # Fetch the availability slot
        result = await self.db.execute(
            select(CandidateAvailabilitySlot).where(
                CandidateAvailabilitySlot.candidate_availability_slot_id == slot_id,
                CandidateAvailabilitySlot.organization_id == org_id,
                CandidateAvailabilitySlot.candidate_id == candidate_id,
                CandidateAvailabilitySlot.deleted_at.is_(None),
            )
        )
        slot = result.scalar_one_or_none()
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found",
            )

        # Set slot status to CANCELLED
        slot.status = AvailabilityStatus.CANCELLED.value
        await self.db.flush()

        # Find and cancel overlapping interview slots
        # Query for interview slots that overlap with this availability slot's time range
        overlapping_result = await self.db.execute(
            select(InterviewSlot).where(
                InterviewSlot.organization_id == org_id,
                InterviewSlot.status == SlotStatus.SCHEDULED.value,
                InterviewSlot.scheduled_start >= slot.start_time,
                InterviewSlot.scheduled_end <= slot.end_time,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        overlapping_slots = overlapping_result.scalars().all()

        for interview_slot in overlapping_slots:
            interview_slot.status = SlotStatus.CANCELLED.value
            logger.info(
                "interview_slot_cascade_cancelled",
                interview_slot_id=str(interview_slot.interview_slot_id),
                availability_slot_id=str(slot_id),
                candidate_id=str(candidate_id),
            )

        await self.db.flush()

        logger.info(
            "availability_slot_cancelled",
            slot_id=str(slot_id),
            candidate_id=str(candidate_id),
            cascaded_interview_slots=len(overlapping_slots),
        )

        return slot

    @read_only
    async def list_availability(
        self,
        candidate_id: UUID,
        org_id: UUID,
    ) -> list[CandidateAvailabilitySlot]:
        """List availability slots for a candidate.
        
        Only returns non-deleted slots.
        
        Args:
            candidate_id: The candidate ID
            org_id: The organization ID
            
        Returns:
            List of non-deleted CandidateAvailabilitySlot records
            
        Requirements: 7.1, 7.6
        """
        result = await self.db.execute(
            select(CandidateAvailabilitySlot).where(
                CandidateAvailabilitySlot.candidate_id == candidate_id,
                CandidateAvailabilitySlot.organization_id == org_id,
                CandidateAvailabilitySlot.deleted_at.is_(None),
            )
        )
        return result.scalars().all()

    async def _validate_slot(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Validate availability slot timing and duration.
        
        Args:
            start_time: UTC start time
            end_time: UTC end time
            
        Raises:
            HTTPException 422: If validation fails
            
        Requirements: 7.2, 7.3
        """
        # Validate start < end
        if start_time >= end_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_time must be before end_time",
            )

        # Validate duration is 30–480 minutes
        duration_minutes = (end_time - start_time).total_seconds() / 60
        if duration_minutes < MIN_AVAILABILITY_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Availability duration must be at least {MIN_AVAILABILITY_MINUTES} minutes",
            )
        if duration_minutes > MAX_AVAILABILITY_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Availability duration must not exceed {MAX_AVAILABILITY_MINUTES} minutes",
            )

        # Validate start_time >= now + 1 hour
        now = datetime.now(timezone.utc)
        min_start_time = now + timedelta(hours=MIN_HOURS_IN_FUTURE)
        if start_time < min_start_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_time must be at least 1 hour in the future",
            )

    async def _check_active_slot_limit(
        self,
        candidate_id: UUID,
        org_id: UUID,
    ) -> None:
        """Check that candidate has not exceeded active slot limit.
        
        Args:
            candidate_id: The candidate ID
            org_id: The organization ID
            
        Raises:
            HTTPException 409: If active slot limit exceeded
            
        Requirements: 7.6
        """
        count_result = await self.db.execute(
            select(func.count()).where(
                CandidateAvailabilitySlot.candidate_id == candidate_id,
                CandidateAvailabilitySlot.organization_id == org_id,
                CandidateAvailabilitySlot.status == AvailabilityStatus.ACTIVE.value,
                CandidateAvailabilitySlot.deleted_at.is_(None),
            )
        )
        active_count = count_result.scalar() or 0
        if active_count >= MAX_ACTIVE_SLOTS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Candidate has reached the maximum of {MAX_ACTIVE_SLOTS} active availability slots",
            )
