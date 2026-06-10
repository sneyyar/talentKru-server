"""
24-hour reminder background scheduler for interview slots.

Provides:
- run_reminder_check(): Async function that queries for interview slots within 24 hours
  of their scheduled start time and sends reminder notifications to assigned interviewers.
- Designed to run periodically (e.g., every 15 minutes via APScheduler or similar).

Requirements: 8.5
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.modules.slots.models import InterviewSlot, SlotStatus, InvitationStatus
from app.modules.notifications.service import NotificationService
from app.observability.logging import get_logger

logger = get_logger(__name__)


async def run_reminder_check() -> None:
    """
    Query for interview slots within 24 hours of scheduled start and send reminders.

    Query:
    - InterviewSlot WHERE status=SCHEDULED AND invitation_status IN ('Pending', 'Accepted')
      AND scheduled_start BETWEEN now() AND now()+24h AND deleted_at IS NULL

    For each slot, call NotificationService.send_24h_reminder(slot_id, org_id).

    This function is designed to be called periodically by a scheduler (e.g., every
    15 minutes via APScheduler).

    Requirements: 8.5
    """
    try:
        async with AsyncSessionFactory() as db:
            now = datetime.now(timezone.utc)
            window_start = now
            window_end = now + timedelta(hours=24)

            logger.info(
                "reminder_check_started",
                window_start=window_start.isoformat(),
                window_end=window_end.isoformat(),
            )

            # Query slots within 24-hour window
            result = await db.execute(
                select(InterviewSlot).where(
                    InterviewSlot.status == SlotStatus.SCHEDULED.value,
                    InterviewSlot.invitation_status.in_([
                        InvitationStatus.PENDING.value,
                        InvitationStatus.ACCEPTED.value,
                    ]),
                    InterviewSlot.scheduled_start >= window_start,
                    InterviewSlot.scheduled_start <= window_end,
                    InterviewSlot.deleted_at.is_(None),
                )
            )
            slots = result.scalars().all()

            logger.info(
                "reminder_check_found_slots",
                slot_count=len(slots),
            )

            if not slots:
                logger.info("reminder_check_no_slots_found")
                return

            # Send reminders for each slot
            notification_service = NotificationService(db)
            for slot in slots:
                await notification_service.send_24h_reminder(slot.interview_slot_id, slot.organization_id)

            logger.info(
                "reminder_check_completed",
                slots_processed=len(slots),
            )

    except Exception as exc:
        logger.error(
            "reminder_check_failed",
            error=str(exc),
            exc_info=True,
        )
