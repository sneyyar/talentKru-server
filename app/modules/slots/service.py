"""Interview slot service (Req 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10)."""

from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from fastapi import HTTPException, BackgroundTasks
from app.base_model import current_user_id_var
from app.modules.slots.models import (
    InterviewSlot,
    InterviewerPreference,
    SlotStatus,
    InvitationStatus,
    AttendanceStatus,
    SlotType,
)
from app.domain_events.publisher import publish_event
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Constants from Requirement 2.10
DEFAULT_MAX_PER_DAY = 5
DEFAULT_MAX_PER_WEEK = 20
ALL_INTERVIEW_TYPES = {"MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"}

# Constants from Requirement 2.4
MIN_SLOT_MINUTES = 15
MAX_SLOT_MINUTES = 480


class InterviewSlotService:
    """Service for managing interview slots and interviewer preferences (Req 2.1-2.10)."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db

    async def create_slot(
        self,
        org_id: UUID,
        journey_id: UUID,
        slot_type: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        timezone_str: str,
        interviewer_user_id: UUID | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> InterviewSlot:
        """
        Create an interview slot (Req 2.1, 2.4, 2.5).

        Validates:
        - scheduled_start < scheduled_end (422)
        - duration 15–480 minutes (422)
        - if interviewer assigned, validates via _validate_interviewer_assignment (409)

        If interviewer assigned, sets invitation_status=PENDING and publishes event.

        Returns:
            InterviewSlot entity
        """
        # Validate basic time constraints (Req 2.4)
        if scheduled_start >= scheduled_end:
            raise HTTPException(
                status_code=422,
                detail="ScheduledStart must be before ScheduledEnd",
            )

        duration_minutes = (scheduled_end - scheduled_start).total_seconds() / 60
        if duration_minutes < MIN_SLOT_MINUTES or duration_minutes > MAX_SLOT_MINUTES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Slot duration must be between {MIN_SLOT_MINUTES} and "
                    f"{MAX_SLOT_MINUTES} minutes"
                ),
            )

        # Validate interviewer assignment if provided (Req 2.2, 2.3, 2.10)
        invitation_status = None
        if interviewer_user_id:
            await self._validate_interviewer_assignment(
                org_id, interviewer_user_id, slot_type, scheduled_start
            )
            invitation_status = InvitationStatus.PENDING.value

        # Create slot
        from uuid import uuid4

        slot = InterviewSlot(
            interview_slot_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=journey_id,
            type=slot_type,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            timezone=timezone_str,
            status=SlotStatus.SCHEDULED.value,
            invitation_status=invitation_status,
            attendance_status=AttendanceStatus.UNKNOWN.value,
            interviewer_user_id=interviewer_user_id,
        )
        self.db.add(slot)
        await self.db.flush()

        # Publish event if interviewer assigned (Req 2.5)
        if interviewer_user_id:
            await publish_event(
                "interview_slot_created",
                {
                    "slot_id": str(slot.interview_slot_id),
                    "org_id": str(org_id),
                    "interviewer_user_id": str(interviewer_user_id),
                    "scheduled_start": scheduled_start.isoformat(),
                },
                self.db,
                background_tasks=background_tasks,
            )

        logger.info(
            "interview_slot_created",
            slot_id=str(slot.interview_slot_id),
            org_id=str(org_id),
            interviewer_user_id=str(interviewer_user_id) if interviewer_user_id else None,
        )

        return slot

    async def _validate_interviewer_assignment(
        self,
        org_id: UUID,
        interviewer_user_id: UUID,
        slot_type: str,
        scheduled_start: datetime,
    ) -> None:
        """
        Validate interviewer can be assigned to slot (Req 2.2, 2.3, 2.10).

        Fetches InterviewerPreference; applies defaults if not found.
        Validates:
        - slot_type in allowed_types (409)
        - daily count < max_per_day (409)
        - weekly count < max_per_week (409)

        Raises:
            HTTPException 409 if any constraint violated
        """
        # Fetch preference or apply defaults (Req 2.10)
        pref_result = await self.db.execute(
            select(InterviewerPreference).where(
                InterviewerPreference.interviewer_user_id == interviewer_user_id,
                InterviewerPreference.organization_id == org_id,
                InterviewerPreference.deleted_at.is_(None),
            )
        )
        pref = pref_result.scalar_one_or_none()

        max_per_day = (
            pref.max_interviews_per_day
            if pref
            else DEFAULT_MAX_PER_DAY
        )
        max_per_week = (
            pref.max_interviews_per_week
            if pref
            else DEFAULT_MAX_PER_WEEK
        )
        allowed_types = (
            set(pref.allowed_interview_types)
            if pref
            else ALL_INTERVIEW_TYPES
        )

        # Validate slot_type (Req 2.3)
        if slot_type not in allowed_types:
            raise HTTPException(
                status_code=409,
                detail=f"Interviewer does not allow interview type: {slot_type}",
            )

        # Count slots on same day (Req 2.3)
        day_start = scheduled_start.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)

        day_count_result = await self.db.execute(
            select(func.count()).where(
                InterviewSlot.interviewer_user_id == interviewer_user_id,
                InterviewSlot.organization_id == org_id,
                InterviewSlot.scheduled_start >= day_start,
                InterviewSlot.scheduled_start < day_end,
                InterviewSlot.status != SlotStatus.CANCELLED.value,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        day_count = day_count_result.scalar() or 0
        if day_count >= max_per_day:
            raise HTTPException(
                status_code=409,
                detail=f"Interviewer has reached maximum interviews per day ({max_per_day})",
            )

        # Count slots in same ISO week (Req 2.3)
        week_start = scheduled_start - timedelta(
            days=scheduled_start.weekday()
        )
        week_start = week_start.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = week_start + timedelta(days=7)

        week_count_result = await self.db.execute(
            select(func.count()).where(
                InterviewSlot.interviewer_user_id == interviewer_user_id,
                InterviewSlot.organization_id == org_id,
                InterviewSlot.scheduled_start >= week_start,
                InterviewSlot.scheduled_start < week_end,
                InterviewSlot.status != SlotStatus.CANCELLED.value,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        week_count = week_count_result.scalar() or 0
        if week_count >= max_per_week:
            raise HTTPException(
                status_code=409,
                detail=f"Interviewer has reached maximum interviews per week ({max_per_week})",
            )

    async def update_invitation_status(
        self,
        slot: InterviewSlot,
        new_status: str,
    ) -> InterviewSlot:
        """
        Update interviewer invitation status (Req 2.6).

        Args:
            slot: InterviewSlot entity to update
            new_status: "ACCEPTED" or "DECLINED"

        Returns:
            Updated InterviewSlot entity
        """
        slot.invitation_status = new_status
        await self.db.flush()

        logger.info(
            "invitation_status_updated",
            slot_id=str(slot.interview_slot_id),
            new_status=new_status,
        )

        return slot

    async def update_attendance_status(
        self,
        slot: InterviewSlot,
        new_status: str,
    ) -> InterviewSlot:
        """
        Update candidate attendance status (Req 2.7).

        Validates that scheduled_end <= now() (409 if future).

        Args:
            slot: InterviewSlot entity to update
            new_status: "ATTENDED" or "NO_SHOW"

        Returns:
            Updated InterviewSlot entity

        Raises:
            HTTPException 409 if slot is in the future
        """
        now = datetime.now(timezone.utc)

        if slot.scheduled_end > now:
            raise HTTPException(
                status_code=409,
                detail="Attendance status can only be updated after the slot has ended",
            )

        slot.attendance_status = new_status
        await self.db.flush()

        logger.info(
            "attendance_status_updated",
            slot_id=str(slot.interview_slot_id),
            new_status=new_status,
        )

        return slot

    async def create_or_update_preference(
        self,
        org_id: UUID,
        interviewer_user_id: UUID,
        current_user_id: UUID,
        current_user_role: str,
        allowed_interview_types: list[str],
        max_interviews_per_day: int,
        max_interviews_per_week: int,
        working_hours: dict | None = None,
    ) -> InterviewerPreference:
        """
        Create or update interviewer preference (Req 2.8, 2.9).

        Validates:
        - max_interviews_per_day 1–20 (422)
        - max_interviews_per_week 1–100 (422)
        - ownership: only interviewer_user_id == current_user_id or
          Administrator/SuperAdministrator (403)

        Args:
            org_id: Organization ID
            interviewer_user_id: Interviewer's user ID
            current_user_id: Current authenticated user ID
            current_user_role: Current user's role
            allowed_interview_types: List of allowed interview types
            max_interviews_per_day: Max per day (1-20)
            max_interviews_per_week: Max per week (1-100)
            working_hours: Optional working hours JSON

        Returns:
            InterviewerPreference entity

        Raises:
            HTTPException 422 if validation fails
            HTTPException 403 if not authorized
        """
        # Validate max values (Req 2.8)
        if not (1 <= max_interviews_per_day <= 20):
            raise HTTPException(
                status_code=422,
                detail="max_interviews_per_day must be between 1 and 20",
            )
        if not (1 <= max_interviews_per_week <= 100):
            raise HTTPException(
                status_code=422,
                detail="max_interviews_per_week must be between 1 and 100",
            )

        # Enforce ownership (Req 2.9)
        if (
            current_user_id != interviewer_user_id
            and current_user_role not in ("Administrator", "SuperAdministrator")
        ):
            raise HTTPException(
                status_code=403,
                detail="Only the interviewer or an administrator can modify this preference",
            )

        # Fetch existing preference or create new
        pref_result = await self.db.execute(
            select(InterviewerPreference).where(
                InterviewerPreference.interviewer_user_id == interviewer_user_id,
                InterviewerPreference.organization_id == org_id,
                InterviewerPreference.deleted_at.is_(None),
            )
        )
        pref = pref_result.scalar_one_or_none()

        from uuid import uuid4

        if pref:
            # Update existing
            pref.allowed_interview_types = allowed_interview_types
            pref.max_interviews_per_day = max_interviews_per_day
            pref.max_interviews_per_week = max_interviews_per_week
            if working_hours is not None:
                pref.working_hours = working_hours
        else:
            # Create new
            pref = InterviewerPreference(
                interviewer_preference_id=uuid4(),
                interviewer_user_id=interviewer_user_id,
                organization_id=org_id,
                allowed_interview_types=allowed_interview_types,
                max_interviews_per_day=max_interviews_per_day,
                max_interviews_per_week=max_interviews_per_week,
                working_hours=working_hours,
            )
            self.db.add(pref)

        await self.db.flush()

        logger.info(
            "interviewer_preference_updated",
            interviewer_user_id=str(interviewer_user_id),
            org_id=str(org_id),
            max_per_day=max_interviews_per_day,
            max_per_week=max_interviews_per_week,
        )

        return pref
