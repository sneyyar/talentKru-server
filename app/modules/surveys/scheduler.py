"""Survey background scheduler for reminders and expiry.

Implements periodic scheduler that:
- Sends reminders for surveys 7+ days old without reminder sent (Requirement 9.10)
- Expires surveys 30+ days old with status Sent (Requirement 9.11)
- Runs periodically configurable via SURVEY_SCHEDULER_INTERVAL_MINUTES env var
- Logs all scheduler actions at INFO level (Requirement 9.26)
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionFactory
from app.domain_events.publisher import publish_event
from app.modules.surveys.models import CandidateFeedbackSurvey, SurveyStatus
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Default scheduler interval: 15 minutes
DEFAULT_SCHEDULER_INTERVAL_MINUTES = 15


async def run_survey_scheduler() -> None:
    """
    Background task: Run survey reminder and expiry scheduler.

    Periodically:
    1. Call SurveyService.send_reminder() — selects surveys 7+ days old with no reminder sent
    2. Call SurveyService.expire_surveys() — selects surveys 30+ days old with status Sent

    Runs every SURVEY_SCHEDULER_INTERVAL_MINUTES (default 15, configurable via env var).
    Logs all scheduler actions at INFO level.

    Requirements: 9.10, 9.11, 9.26
    """
    # Get scheduler interval from env or use default
    interval_str = os.getenv("SURVEY_SCHEDULER_INTERVAL_MINUTES", str(DEFAULT_SCHEDULER_INTERVAL_MINUTES))
    try:
        interval_minutes = int(interval_str)
    except ValueError:
        logger.warning(
            "invalid_survey_scheduler_interval",
            value=interval_str,
            using_default=DEFAULT_SCHEDULER_INTERVAL_MINUTES,
        )
        interval_minutes = DEFAULT_SCHEDULER_INTERVAL_MINUTES

    interval_seconds = interval_minutes * 60

    logger.info(
        "survey_scheduler_started",
        interval_minutes=interval_minutes,
        interval_seconds=interval_seconds,
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await _run_scheduler_iteration()
        except Exception as e:
            logger.error(
                "survey_scheduler_error",
                error=str(e),
                exc_info=True,
            )


async def _run_scheduler_iteration() -> None:
    """Run a single iteration of the scheduler: reminders + expiry."""
    logger.info("survey_scheduler_iteration_started")

    try:
        async with AsyncSessionFactory() as db:
            # Step 1: Send reminders for 7+ days old surveys
            await _send_reminders(db)

            # Step 2: Expire 30+ days old surveys
            await _expire_old_surveys(db)

            await db.commit()
            logger.info("survey_scheduler_iteration_completed")

    except Exception as e:
        logger.error(
            "survey_scheduler_iteration_error",
            error=str(e),
            exc_info=True,
        )


async def _send_reminders(db: AsyncSession) -> None:
    """
    Send reminders for surveys 7+ days old with no reminder sent.

    Selects surveys with:
    - Status = SENT
    - Created 7+ days ago
    - FirstReminderSentAt IS NULL
    - DeletedAt IS NULL

    Updates first_reminder_sent_at and publishes survey_reminder event.

    Requirements: 9.10, 9.26
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    result = await db.execute(
        select(CandidateFeedbackSurvey).where(
            CandidateFeedbackSurvey.status == SurveyStatus.SENT.value,
            CandidateFeedbackSurvey.created_at <= seven_days_ago,
            CandidateFeedbackSurvey.first_reminder_sent_at.is_(None),
            CandidateFeedbackSurvey.deleted_at.is_(None),
        )
    )
    surveys = result.scalars().all()

    reminder_count = 0
    for survey in surveys:
        try:
            survey.first_reminder_sent_at = now
            await db.flush()

            # Publish survey_reminder event
            await publish_event(
                "survey_reminder",
                {
                    "survey_id": str(survey.candidate_feedback_survey_id),
                    "journey_id": str(survey.interview_journey_id),
                    "candidate_id": str(survey.candidate_id),
                    "org_id": str(survey.organization_id),
                },
                db,
                background_tasks=None,
            )

            reminder_count += 1

        except Exception as e:
            logger.error(
                "survey_reminder_failed",
                survey_id=str(survey.candidate_feedback_survey_id),
                error=str(e),
                exc_info=True,
            )

    if reminder_count > 0:
        logger.info(
            "survey_reminders_sent",
            count=reminder_count,
        )


async def _expire_old_surveys(db: AsyncSession) -> None:
    """
    Expire surveys 30+ days old with status Sent.

    Selects surveys with:
    - Status = SENT
    - ExpiresAt <= now
    - DeletedAt IS NULL

    Updates status to EXPIRED and deactivates related tokens.

    Requirements: 9.11, 9.26
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(CandidateFeedbackSurvey).where(
            CandidateFeedbackSurvey.status == SurveyStatus.SENT.value,
            CandidateFeedbackSurvey.expires_at <= now,
            CandidateFeedbackSurvey.deleted_at.is_(None),
        )
    )
    surveys = result.scalars().all()

    expire_count = 0
    for survey in surveys:
        try:
            survey.status = SurveyStatus.EXPIRED.value
            await db.flush()

            # Deactivate related tokens
            from app.modules.surveys.models import CandidateFeedbackSurveyToken

            token_result = await db.execute(
                select(CandidateFeedbackSurveyToken).where(
                    CandidateFeedbackSurveyToken.candidate_feedback_survey_id
                    == survey.candidate_feedback_survey_id,
                    CandidateFeedbackSurveyToken.is_active.is_(True),
                    CandidateFeedbackSurveyToken.deleted_at.is_(None),
                )
            )
            tokens = token_result.scalars().all()
            for token in tokens:
                token.is_active = False

            await db.flush()
            expire_count += 1

        except Exception as e:
            logger.error(
                "survey_expiry_failed",
                survey_id=str(survey.candidate_feedback_survey_id),
                error=str(e),
                exc_info=True,
            )

    if expire_count > 0:
        logger.info(
            "surveys_expired",
            count=expire_count,
        )
