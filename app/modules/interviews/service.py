"""Interviews service.

Implements interview management functionality.

Requirements: 7.1
"""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.interviews.models import (
    InterviewSlot,
    InterviewFeedback,
    InterviewerPreference,
)
from app.observability.logging import get_logger
from app.decorators import transactional, read_only

logger = get_logger(__name__)


class InterviewsService:
    """Service for interview operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @read_only
    async def get_interview_slot(
        self,
        slot_id: UUID,
    ) -> InterviewSlot | None:
        """
        Get interview slot by ID.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(InterviewSlot).where(
                InterviewSlot.slot_id == slot_id
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def get_interview_feedback(
        self,
        feedback_id: UUID,
    ) -> InterviewFeedback | None:
        """
        Get interview feedback by ID.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(InterviewFeedback).where(
                InterviewFeedback.feedback_id == feedback_id
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def get_interviewer_preference(
        self,
        preference_id: UUID,
    ) -> InterviewerPreference | None:
        """
        Get interviewer preference by ID.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(InterviewerPreference).where(
                InterviewerPreference.preference_id == preference_id
            )
        )
        return result.scalar_one_or_none()
