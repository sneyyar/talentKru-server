"""Journeys service.

Implements interview journey management.

Requirements: 7.1, 7.5
"""

from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.journeys.models import InterviewJourney, JourneyOverallStatus
from app.observability.logging import get_logger
from app.decorators import transactional, read_only

logger = get_logger(__name__)


class JourneysService:
    """Service for interview journey operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @transactional()
    async def create_journey(
        self,
        organization_id: UUID,
        candidate_id: UUID,
    ) -> InterviewJourney:
        """
        Create a new interview journey.

        Sets overall_status=ACTIVE by default.

        Requirements: 7.1
        """
        journey = InterviewJourney(
            interview_journey_id=uuid4(),
            organization_id=organization_id,
            candidate_id=candidate_id,
            overall_status=JourneyOverallStatus.ACTIVE.value,
        )

        self.db.add(journey)
        await self.db.flush()

        logger.info(
            "journey_created",
            journey_id=str(journey.interview_journey_id),
            candidate_id=str(candidate_id),
            organization_id=str(organization_id),
        )

        return journey

    @transactional()
    async def transition_journey_stage(
        self,
        journey_id: UUID,
        new_status: str,
    ) -> InterviewJourney:
        """
        Transition journey to a new stage.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(InterviewJourney).where(
                InterviewJourney.interview_journey_id == journey_id
            )
        )
        journey = result.scalar_one_or_none()

        if not journey:
            raise ValueError(f"Journey {journey_id} not found")

        journey.overall_status = new_status
        await self.db.flush()

        logger.info(
            "journey_transitioned",
            journey_id=str(journey_id),
            new_status=new_status,
        )

        return journey

    @transactional()
    async def cancel_journey(
        self,
        journey_id: UUID,
    ) -> InterviewJourney:
        """
        Cancel an interview journey.

        Sets overall_status=CANCELLED.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(InterviewJourney).where(
                InterviewJourney.interview_journey_id == journey_id
            )
        )
        journey = result.scalar_one_or_none()

        if not journey:
            raise ValueError(f"Journey {journey_id} not found")

        journey.overall_status = JourneyOverallStatus.CANCELLED.value
        await self.db.flush()

        logger.info(
            "journey_cancelled",
            journey_id=str(journey_id),
        )

        return journey

    @read_only
    async def get_journey(
        self,
        journey_id: UUID,
    ) -> InterviewJourney | None:
        """
        Get interview journey by ID.

        Requirements: 7.1
        """
        result = await self.db.execute(
            select(InterviewJourney).where(
                InterviewJourney.interview_journey_id == journey_id
            )
        )
        return result.scalar_one_or_none()
