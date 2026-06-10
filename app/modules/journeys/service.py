"""Interview Journey Service.

Implements the interview journey lifecycle FSM with stage history tracking,
OfferAccepted encryption, and event publishing.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import secrets
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_field
from app.decorators import read_only, transactional
from app.domain_events.publisher import publish_event
from app.modules.journeys.models import (
    CandidateInterviewJourney,
    InterviewJourney,
    InterviewJourneyStageHistory,
    JourneyOverallStatus,
    JourneyStage,
    JourneyStageStatus,
)
from app.observability.logging import get_logger

logger = get_logger(__name__)


async def _create_survey_on_loop_exit(
    journey_id: UUID,
    candidate_id: UUID,
    org_id: UUID,
) -> None:
    """
    Background task: Create a survey when journey exits LoopInterview stage.

    Opens a new database session, calls SurveyService.create_survey_for_journey,
    publishes a survey_created event on success, logs ERROR with correlation_id on exception.

    Requirements: 9.7
    """
    from app.database import AsyncSessionFactory
    from app.modules.surveys.service import CandidateFeedbackSurveyService
    from app.observability.middleware import correlation_id_var

    correlation_id = correlation_id_var.get(None)

    try:
        async with AsyncSessionFactory() as db:
            service = CandidateFeedbackSurveyService(db)
            survey, raw_token = await service.create_survey_for_journey(
                journey_id, candidate_id, org_id
            )
            await db.commit()

            logger.info(
                "survey_created_on_loop_exit",
                survey_id=str(survey.candidate_feedback_survey_id),
                journey_id=str(journey_id),
                correlation_id=correlation_id,
            )
    except Exception as exc:
        logger.error(
            "survey_creation_failed",
            journey_id=str(journey_id),
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


# Terminal stages (no sub-status, no further transitions)
TERMINAL_STAGES = {
    JourneyStage.REJECTED,
    JourneyStage.OFFER_DECLINED,
    JourneyStage.OFFER_ACCEPTED,
    JourneyStage.WITHDRAWN,
}

# Valid transitions: from_stage -> set of allowed to_stages
VALID_TRANSITIONS: dict[JourneyStage, set[JourneyStage]] = {
    JourneyStage.SOURCED: {
        JourneyStage.RECRUITER_SCREEN,
        JourneyStage.REJECTED,
        JourneyStage.WITHDRAWN,
    },
    JourneyStage.RECRUITER_SCREEN: {
        JourneyStage.MANAGER_SCREEN,
        JourneyStage.REJECTED,
        JourneyStage.WITHDRAWN,
    },
    JourneyStage.MANAGER_SCREEN: {
        JourneyStage.LOOP_INTERVIEW,
        JourneyStage.REJECTED,
        JourneyStage.WITHDRAWN,
    },
    JourneyStage.LOOP_INTERVIEW: {
        JourneyStage.PANEL_REVIEW,
        JourneyStage.REJECTED,
        JourneyStage.WITHDRAWN,
    },
    JourneyStage.PANEL_REVIEW: {
        JourneyStage.OFFER_PENDING,
        JourneyStage.REJECTED,
        JourneyStage.WITHDRAWN,
    },
    JourneyStage.OFFER_PENDING: {
        JourneyStage.OFFER_EXTENDED,
        JourneyStage.REJECTED,
        JourneyStage.WITHDRAWN,
    },
    JourneyStage.OFFER_EXTENDED: {
        JourneyStage.OFFER_ACCEPTED,
        JourneyStage.OFFER_DECLINED,
        JourneyStage.WITHDRAWN,
    },
    JourneyStage.REJECTED: set(),  # Terminal
    JourneyStage.OFFER_DECLINED: set(),  # Terminal
    JourneyStage.OFFER_ACCEPTED: set(),  # Terminal
    JourneyStage.WITHDRAWN: set(),  # Terminal
}


class InterviewJourneyService:
    """Service for interview journey operations.

    Manages the end-to-end journey lifecycle, stage transitions with FSM validation,
    stage history tracking, and PII encryption on OfferAccepted.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
    """

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    @transactional()
    async def create_journey(
        self,
        org_id: UUID,
        candidate_id: UUID,
        job_requisition_id: UUID,
        created_by: UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> InterviewJourney:
        """
        Create a new interview journey.

        Generates a URL-safe public ID (≥22 chars), initializes with SOURCED stage
        and ACTIVE overall status, creates the CandidateInterviewJourney join record,
        and publishes a 'journey_created' event.

        Requirements: 1.1, 1.2, 1.5, 1.6
        """
        # Generate journey_public_id: secrets.token_urlsafe(16) produces ≥22 URL-safe chars
        journey_public_id = secrets.token_urlsafe(16)

        journey = InterviewJourney(
            interview_journey_id=uuid4(),
            organization_id=org_id,
            journey_public_id=journey_public_id,
            candidate_id=candidate_id,
            job_requisition_id=job_requisition_id,
            current_stage=JourneyStage.SOURCED.value,
            current_stage_status=None,
            overall_status=JourneyOverallStatus.ACTIVE.value,
            start_date=datetime.now(timezone.utc),
        )
        self.db.add(journey)

        # Create CandidateInterviewJourney join record
        join_record = CandidateInterviewJourney(
            candidate_interview_journey_id=uuid4(),
            candidate_id=candidate_id,
            interview_journey_id=journey.interview_journey_id,
            associated_at=datetime.now(timezone.utc),
        )
        self.db.add(join_record)

        await self.db.flush()

        # Publish event
        await publish_event(
            "journey_created",
            {
                "journey_id": str(journey.interview_journey_id),
                "org_id": str(org_id),
                "candidate_id": str(candidate_id),
                "job_requisition_id": str(job_requisition_id),
            },
            self.db,
            background_tasks=background_tasks,
        )

        logger.info(
            "journey_created",
            journey_id=str(journey.interview_journey_id),
            candidate_id=str(candidate_id),
            org_id=str(org_id),
        )

        return journey

    @transactional()
    async def transition_stage(
        self,
        journey: InterviewJourney,
        to_stage: JourneyStage,
        changed_by: UUID,
        comments: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> InterviewJourney:
        """
        Transition journey to a new stage with FSM validation.

        Validates the transition is allowed, checks comments length, updates the stage,
        creates a stage history record, encrypts the join record on OFFER_ACCEPTED,
        sets offer_extended_at on OFFER_EXTENDED, and publishes the event.

        Returns the updated journey (caller must commit).

        Requirements: 1.2, 1.3, 1.4, 1.5, 1.7, 1.8
        """
        # Convert current_stage string to enum for validation
        try:
            current_stage = JourneyStage(journey.current_stage)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid current stage: {journey.current_stage}",
            )

        # Validate transition is allowed (Req 1.2, 1.8)
        if to_stage not in VALID_TRANSITIONS.get(current_stage, set()):
            raise HTTPException(
                status_code=400,
                detail=f"Transition from {current_stage.value} to {to_stage.value} "
                "is not permitted",
            )

        # Validate comments length (Req 1.4)
        if comments and len(comments) > 2000:
            raise HTTPException(
                status_code=422,
                detail="Comments must not exceed 2000 characters",
            )

        # Update stage and sub-status
        from_stage = current_stage
        journey.current_stage = to_stage.value

        # Terminal stages have no sub-status (Req 1.3)
        if to_stage in TERMINAL_STAGES:
            journey.current_stage_status = None

        # OfferAccepted: set OverallStatus=COMPLETED, offer_responded_at, and encrypt (Req 1.7)
        if to_stage == JourneyStage.OFFER_ACCEPTED:
            journey.overall_status = JourneyOverallStatus.COMPLETED.value
            journey.offer_responded_at = datetime.now(timezone.utc)
            await self._encrypt_join_record(
                journey.interview_journey_id, journey.candidate_id
            )

        # OfferExtended: set offer_extended_at
        if to_stage == JourneyStage.OFFER_EXTENDED:
            journey.offer_extended_at = datetime.now(timezone.utc)

        # Create stage history record (Req 1.4)
        history = InterviewJourneyStageHistory(
            interview_journey_stage_history_id=uuid4(),
            interview_journey_id=journey.interview_journey_id,
            organization_id=journey.organization_id,
            from_stage=from_stage.value,
            to_stage=to_stage.value,
            changed_by_user_id=changed_by,
            changed_at=datetime.now(timezone.utc),
            comments=comments,
        )
        self.db.add(history)
        await self.db.flush()

        # Publish event
        await publish_event(
            "journey_stage_changed",
            {
                "journey_id": str(journey.interview_journey_id),
                "org_id": str(journey.organization_id),
                "from_stage": from_stage.value,
                "to_stage": to_stage.value,
            },
            self.db,
            background_tasks=background_tasks,
        )

        # Trigger survey creation when exiting LoopInterview (Req 9.7)
        if (
            from_stage == JourneyStage.LOOP_INTERVIEW
            and to_stage
            in {
                JourneyStage.PANEL_REVIEW,
                JourneyStage.OFFER_PENDING,
                JourneyStage.OFFER_EXTENDED,
                JourneyStage.OFFER_ACCEPTED,
                JourneyStage.OFFER_DECLINED,
                JourneyStage.REJECTED,
                JourneyStage.WITHDRAWN,
            }
        ):
            if background_tasks:
                background_tasks.add_task(
                    _create_survey_on_loop_exit,
                    journey.interview_journey_id,
                    journey.candidate_id,
                    journey.organization_id,
                )

        logger.info(
            "journey_stage_transitioned",
            journey_id=str(journey.interview_journey_id),
            from_stage=from_stage.value,
            to_stage=to_stage.value,
        )

        return journey

    async def _encrypt_join_record(self, journey_id: UUID, candidate_id: UUID) -> None:
        """
        Encrypt the CandidateInterviewJourney join record.

        Called on OFFER_ACCEPTED to make hired candidate data unlinkable after onboarding.
        Encrypts both candidate_id and interview_journey_id, sets is_encrypted=True,
        and logs the encryption.

        Requirements: 1.6, 1.7
        """
        result = await self.db.execute(
            select(CandidateInterviewJourney).where(
                CandidateInterviewJourney.interview_journey_id == journey_id,
                CandidateInterviewJourney.deleted_at.is_(None),
            )
        )
        join_record = result.scalar_one_or_none()

        if join_record:
            join_record.candidate_id_encrypted = encrypt_field(str(candidate_id))
            join_record.interview_journey_id_encrypted = encrypt_field(str(journey_id))
            join_record.is_encrypted = True
            await self.db.flush()

        logger.info(
            "join_record_encrypted",
            journey_id=str(journey_id),
            candidate_id=str(candidate_id),
        )

    @read_only
    async def get_journey(self, journey_id: UUID, org_id: UUID) -> InterviewJourney | None:
        """
        Fetch a journey by ID with org-scoped filtering.

        Requirements: 1.1
        """
        result = await self.db.execute(
            select(InterviewJourney).where(
                InterviewJourney.interview_journey_id == journey_id,
                InterviewJourney.organization_id == org_id,
                InterviewJourney.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @read_only
    async def list_journeys(
        self,
        org_id: UUID,
        candidate_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[InterviewJourney], int]:
        """
        List journeys with org-scoped filtering.

        Optionally filter by candidate_id. Returns (journeys, total_count).

        Requirements: 1.1
        """
        where_clause = (
            InterviewJourney.organization_id == org_id,
            InterviewJourney.deleted_at.is_(None),
        )

        if candidate_id:
            where_clause = (*where_clause, InterviewJourney.candidate_id == candidate_id)

        # Get total count using func.count()
        count_stmt = select(func.count()).select_from(InterviewJourney).where(*where_clause)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated results
        stmt = select(InterviewJourney).where(*where_clause).order_by(
            InterviewJourney.created_at.desc()
        ).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        journeys = result.scalars().all()

        return journeys, total

    @read_only
    async def get_journey_history(
        self,
        journey_id: UUID,
        org_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[InterviewJourneyStageHistory], int]:
        """
        Fetch stage history for a journey.

        Returns (history_records, total_count).

        Requirements: 1.4
        """
        where_clause = (
            InterviewJourneyStageHistory.interview_journey_id == journey_id,
            InterviewJourneyStageHistory.organization_id == org_id,
            InterviewJourneyStageHistory.deleted_at.is_(None),
        )

        # Get total count using func.count()
        count_stmt = select(func.count()).select_from(InterviewJourneyStageHistory).where(*where_clause)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated results
        stmt = select(InterviewJourneyStageHistory).where(
            *where_clause
        ).order_by(
            InterviewJourneyStageHistory.changed_at.desc()
        ).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        history = result.scalars().all()

        return history, total
