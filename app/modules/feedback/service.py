"""Interview feedback service (Req 3.1-3.9)."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.observability.logging import get_logger
from app.domain_events.publisher import publish_event
from app.modules.feedback.models import InterviewFeedback, FeedbackStatus, FeedbackType
from app.modules.slots.models import InterviewSlot

logger = get_logger(__name__)


class InterviewFeedbackService:
    """Service for managing interview feedback (Req 3.1-3.9)."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db

    async def create_feedback(
        self,
        org_id: UUID,
        slot_id: UUID,
        competency_ratings: dict[str, int],
        narrative: str,
        hiring_recommendation: str,
        requesting_user_id: UUID,
    ) -> InterviewFeedback:
        """
        Create manual interview feedback (Req 3.1, 3.3, 3.6).

        Validates:
        - Requesting user is the assigned interviewer (403)
        - narrative <= 5000 chars (422)
        - competency ratings are integers 1-5 (422)

        Args:
            org_id: Organization ID from authenticated context
            slot_id: Interview slot ID to attach feedback to
            competency_ratings: Dict mapping competency names to ratings (1-5)
            narrative: Narrative summary (max 5000 chars)
            hiring_recommendation: Recommendation (StrongYes, Yes, Neutral, No, StrongNo)
            requesting_user_id: User ID making the request

        Returns:
            Created InterviewFeedback entity with status=DRAFT

        Raises:
            HTTPException: 403 if not assigned interviewer, 404 if slot not found,
                         422 if validation fails
        """
        # Get slot and verify interviewer authorization (Req 3.6)
        slot = await self._get_slot_and_authorize_write(org_id, slot_id, requesting_user_id)

        # Validate feedback fields (Req 3.3)
        self._validate_feedback_fields(competency_ratings, narrative, hiring_recommendation)

        # Create feedback with status=DRAFT (Req 3.1, 3.2)
        feedback = InterviewFeedback(
            interview_feedback_id=uuid4(),
            interview_slot_id=slot_id,
            organization_id=org_id,
            type=FeedbackType.MANUAL.value,
            status=FeedbackStatus.DRAFT.value,
            competency_ratings=competency_ratings,
            narrative=narrative,
            hiring_recommendation=hiring_recommendation,
        )

        self.db.add(feedback)
        await self.db.flush()

        # Update slot with feedback ID
        slot.feedback_id = feedback.interview_feedback_id
        await self.db.flush()

        logger.info(
            "feedback_created",
            feedback_id=str(feedback.interview_feedback_id),
            slot_id=str(slot_id),
            org_id=str(org_id),
            feedback_type="manual",
        )

        return feedback

    async def submit_feedback(
        self,
        org_id: UUID,
        feedback_id: UUID,
        requesting_user_id: UUID,
    ) -> InterviewFeedback:
        """
        Submit feedback, changing status from DRAFT to SUBMITTED (Req 3.8, 3.9).

        After submission, feedback cannot be edited.

        Args:
            org_id: Organization ID from authenticated context
            feedback_id: Feedback ID to submit
            requesting_user_id: User ID making the request

        Returns:
            Updated InterviewFeedback with status=SUBMITTED

        Raises:
            HTTPException: 403 if not assigned interviewer, 404 if not found,
                         409 if already submitted
        """
        # Get feedback and verify slot/interviewer authorization
        feedback = await self._get_feedback_by_id(org_id, feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        # Get slot to verify interviewer
        slot = await self._get_slot_and_authorize_write(org_id, feedback.interview_slot_id, requesting_user_id)

        # Check if already submitted (Req 3.9)
        if feedback.status == FeedbackStatus.SUBMITTED.value:
            raise HTTPException(
                status_code=409,
                detail="Feedback has already been submitted and cannot be modified",
            )

        # Update status to SUBMITTED (Req 3.9)
        feedback.status = FeedbackStatus.SUBMITTED.value
        await self.db.flush()

        logger.info(
            "feedback_submitted",
            feedback_id=str(feedback_id),
            slot_id=str(feedback.interview_slot_id),
            org_id=str(org_id),
        )

        return feedback

    async def update_feedback(
        self,
        org_id: UUID,
        feedback_id: UUID,
        competency_ratings: dict[str, int] | None = None,
        narrative: str | None = None,
        hiring_recommendation: str | None = None,
        requesting_user_id: UUID | None = None,
    ) -> InterviewFeedback:
        """
        Update draft feedback (Req 3.6, 3.8).

        Can only update feedback in DRAFT status. Once submitted (status=SUBMITTED),
        further modifications are rejected with 409.

        Args:
            org_id: Organization ID from authenticated context
            feedback_id: Feedback ID to update
            competency_ratings: Updated ratings (optional)
            narrative: Updated narrative (optional, max 5000 chars)
            hiring_recommendation: Updated recommendation (optional)
            requesting_user_id: User ID making the request

        Returns:
            Updated InterviewFeedback

        Raises:
            HTTPException: 403 if not assigned interviewer, 404 if not found,
                         409 if already submitted, 422 if validation fails
        """
        feedback = await self._get_feedback_by_id(org_id, feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        # Get slot to verify interviewer authorization
        slot = await self._get_slot_and_authorize_write(org_id, feedback.interview_slot_id, requesting_user_id)

        # Check if already submitted (Req 3.8)
        if feedback.status == FeedbackStatus.SUBMITTED.value:
            raise HTTPException(
                status_code=409,
                detail="Feedback has been submitted and cannot be modified",
            )

        # Validate and update fields (only non-None fields)
        if competency_ratings is not None or narrative is not None or hiring_recommendation is not None:
            # Build update dict with current values + new values
            updated_ratings = competency_ratings or feedback.competency_ratings
            updated_narrative = narrative or feedback.narrative
            updated_recommendation = hiring_recommendation or feedback.hiring_recommendation

            self._validate_feedback_fields(updated_ratings, updated_narrative, updated_recommendation)

            if competency_ratings is not None:
                feedback.competency_ratings = competency_ratings
            if narrative is not None:
                feedback.narrative = narrative
            if hiring_recommendation is not None:
                feedback.hiring_recommendation = hiring_recommendation

        await self.db.flush()

        logger.info(
            "feedback_updated",
            feedback_id=str(feedback_id),
            slot_id=str(feedback.interview_slot_id),
            org_id=str(org_id),
        )

        return feedback

    async def submit_transcript(
        self,
        org_id: UUID,
        slot_id: UUID,
        transcript: str,
        requesting_user_id: UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> InterviewFeedback:
        """
        Submit transcript for AI-generated behavioral feedback (Req 3.4, 3.5).

        Validates transcript <= 50000 chars, creates InterviewFeedback with
        type=AI_GENERATED and status=DRAFT, then queues background task
        to invoke BehavioralFeedbackAgent.

        Returns 202 Accepted.

        Args:
            org_id: Organization ID from authenticated context
            slot_id: Interview slot ID
            transcript: Interview transcript (max 50000 chars)
            requesting_user_id: User ID making the request
            background_tasks: FastAPI background tasks for AI agent invocation

        Returns:
            Created InterviewFeedback with status=DRAFT, type=AI_GENERATED

        Raises:
            HTTPException: 403 if not assigned interviewer, 404 if slot not found,
                         422 if transcript exceeds 50000 chars
        """
        # Get slot and verify interviewer authorization
        slot = await self._get_slot_and_authorize_write(org_id, slot_id, requesting_user_id)

        # Validate transcript length (Req 3.4)
        if len(transcript) > 50000:
            raise HTTPException(
                status_code=422,
                detail="Transcript must not exceed 50000 characters",
            )

        # Create AI-generated feedback draft (Req 3.4)
        feedback = InterviewFeedback(
            interview_feedback_id=uuid4(),
            interview_slot_id=slot_id,
            organization_id=org_id,
            type=FeedbackType.AI_GENERATED.value,
            status=FeedbackStatus.DRAFT.value,
            competency_ratings=None,
            narrative=None,
            hiring_recommendation=None,
        )

        self.db.add(feedback)
        await self.db.flush()

        # Update slot with feedback ID
        slot.feedback_id = feedback.interview_feedback_id
        await self.db.flush()

        # Queue background task to invoke BehavioralFeedbackAgent (Req 3.4, 3.5)
        if background_tasks:
            background_tasks.add_task(
                self._run_behavioral_feedback,
                feedback.interview_feedback_id,
                transcript,
                org_id,
            )

        logger.info(
            "transcript_submitted",
            feedback_id=str(feedback.interview_feedback_id),
            slot_id=str(slot_id),
            org_id=str(org_id),
            transcript_length=len(transcript),
        )

        return feedback

    async def get_feedback(
        self,
        org_id: UUID,
        feedback_id: UUID,
        requesting_user_id: UUID,
        is_admin: bool = False,
        hiring_manager_for_req_id: UUID | None = None,
    ) -> InterviewFeedback:
        """
        Get feedback with authorization (Req 3.7).

        Authorized users:
        - Assigned interviewer for the slot
        - Hiring manager for the requisition
        - Administrator/SuperAdministrator

        Args:
            org_id: Organization ID from authenticated context
            feedback_id: Feedback ID to retrieve
            requesting_user_id: User ID making the request
            is_admin: True if user has Administrator or SuperAdministrator role
            hiring_manager_for_req_id: If set, user is hiring manager for this requisition

        Returns:
            InterviewFeedback if authorized

        Raises:
            HTTPException: 403 if not authorized, 404 if not found
        """
        feedback = await self._get_feedback_by_id(org_id, feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        # Get the slot to check interviewer
        slot = await self._get_slot_by_id(org_id, feedback.interview_slot_id)
        if not slot:
            raise HTTPException(status_code=404, detail="Interview slot not found")

        # Check authorization (Req 3.7)
        is_assigned_interviewer = slot.interviewer_user_id == requesting_user_id
        is_hiring_manager = (
            hiring_manager_for_req_id is not None
            and hiring_manager_for_req_id == requesting_user_id
        )

        if not (is_assigned_interviewer or is_hiring_manager or is_admin):
            raise HTTPException(status_code=403, detail="Forbidden")

        return feedback

    async def list_feedback_for_slot(
        self,
        org_id: UUID,
        slot_id: UUID,
    ) -> list[InterviewFeedback]:
        """
        List all feedback records for a slot (admin utility).

        Args:
            org_id: Organization ID from authenticated context
            slot_id: Interview slot ID

        Returns:
            List of InterviewFeedback records for the slot
        """
        stmt = select(InterviewFeedback).where(
            InterviewFeedback.organization_id == org_id,
            InterviewFeedback.interview_slot_id == slot_id,
            InterviewFeedback.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ========== Private helper methods ==========

    async def _get_slot_and_authorize_write(
        self,
        org_id: UUID,
        slot_id: UUID,
        requesting_user_id: UUID,
    ) -> InterviewSlot:
        """
        Get slot and verify requesting user is the assigned interviewer (Req 3.6).

        Args:
            org_id: Organization ID from authenticated context
            slot_id: Interview slot ID
            requesting_user_id: User ID making the request

        Returns:
            InterviewSlot if authorized

        Raises:
            HTTPException: 403 if not assigned interviewer, 404 if slot not found
        """
        slot = await self._get_slot_by_id(org_id, slot_id)
        if not slot:
            raise HTTPException(status_code=404, detail="Interview slot not found")

        # Verify requester is the assigned interviewer (Req 3.6)
        if slot.interviewer_user_id != requesting_user_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Only the assigned interviewer can perform this action",
            )

        return slot

    async def _get_slot_by_id(
        self,
        org_id: UUID,
        slot_id: UUID,
    ) -> InterviewSlot | None:
        """Get interview slot by ID with org filtering."""
        stmt = select(InterviewSlot).where(
            InterviewSlot.organization_id == org_id,
            InterviewSlot.interview_slot_id == slot_id,
            InterviewSlot.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_feedback_by_id(
        self,
        org_id: UUID,
        feedback_id: UUID,
    ) -> InterviewFeedback | None:
        """Get feedback by ID with org filtering."""
        stmt = select(InterviewFeedback).where(
            InterviewFeedback.organization_id == org_id,
            InterviewFeedback.interview_feedback_id == feedback_id,
            InterviewFeedback.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _validate_feedback_fields(
        self,
        competency_ratings: dict[str, int],
        narrative: str,
        hiring_recommendation: str,
    ) -> None:
        """
        Validate feedback fields (Req 3.3).

        Args:
            competency_ratings: Dict of competency names to ratings
            narrative: Narrative summary
            hiring_recommendation: Hiring recommendation enum value

        Raises:
            HTTPException: 422 if validation fails
        """
        errors = []

        # Validate narrative length (Req 3.3)
        if len(narrative) > 5000:
            errors.append("narrative: must not exceed 5000 characters")

        # Validate competency ratings are integers 1-5
        if competency_ratings:
            for competency_name, rating in competency_ratings.items():
                if not isinstance(rating, int):
                    errors.append(f"competency_ratings[{competency_name}]: must be an integer")
                elif not (1 <= rating <= 5):
                    errors.append(f"competency_ratings[{competency_name}]: must be between 1 and 5")

        # Validate hiring recommendation is one of the valid values
        valid_recommendations = {"STRONG_YES", "YES", "NEUTRAL", "NO", "STRONG_NO"}
        if hiring_recommendation and hiring_recommendation not in valid_recommendations:
            errors.append(f"hiring_recommendation: must be one of {valid_recommendations}")

        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))

    async def _run_behavioral_feedback(
        self,
        feedback_id: UUID,
        transcript: str,
        org_id: UUID,
    ) -> None:
        """
        Background task to invoke BehavioralFeedbackAgent (Req 3.4, 3.5).

        Posts transcript to /internal/agents/behavioral-feedback and updates
        feedback with generated ratings, narrative, and recommendation.

        On failure, logs error and leaves feedback in DRAFT status for manual fallback.

        Args:
            feedback_id: Feedback record ID to update
            transcript: Interview transcript
            org_id: Organization ID
        """
        import httpx
        from app.config import settings

        try:
            # Get the feedback record again (new session)
            from app.database import AsyncSessionFactory

            async with AsyncSessionFactory() as new_session:
                feedback = await self._get_feedback_by_id_session(
                    new_session,
                    org_id,
                    feedback_id,
                )

                if not feedback:
                    logger.error(
                        "behavioral_feedback_task_feedback_not_found",
                        feedback_id=str(feedback_id),
                    )
                    return

                # Call agent endpoint
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{settings.INTERNAL_API_BASE_URL}/internal/agents/behavioral-feedback",
                        json={"transcript": transcript, "feedback_id": str(feedback_id)},
                        headers={
                            "X-Agent-API-Key": settings.AGENT_API_KEY,
                        },
                        timeout=60.0,
                    )
                    response.raise_for_status()

                    result = response.json()
                    feedback.competency_ratings = result.get("competency_ratings")
                    feedback.narrative = result.get("narrative")
                    feedback.hiring_recommendation = result.get("hiring_recommendation")

                    new_session.add(feedback)
                    await new_session.commit()

                    logger.info(
                        "behavioral_feedback_generated",
                        feedback_id=str(feedback_id),
                    )

        except Exception as e:
            logger.error(
                "behavioral_feedback_agent_failed",
                feedback_id=str(feedback_id),
                error=str(e),
            )
            # Feedback remains in DRAFT status; interviewer can submit manually

    async def _get_feedback_by_id_session(
        self,
        db_session: AsyncSession,
        org_id: UUID,
        feedback_id: UUID,
    ) -> InterviewFeedback | None:
        """Get feedback by ID with org filtering (alternate session)."""
        stmt = select(InterviewFeedback).where(
            InterviewFeedback.organization_id == org_id,
            InterviewFeedback.interview_feedback_id == feedback_id,
            InterviewFeedback.deleted_at.is_(None),
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
