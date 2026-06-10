"""
Domain event handler registry and dispatcher.

Provides:
- HandlerRegistry: maps event type strings to lists of async handler callables
- register_handler(): appends a handler to the registry for a given event type
- dispatch_event(): looks up and calls all handlers for an event; logs a warning
  if no handler is registered for the event type
- Pre-registered stub handlers for all 8 required event types (Requirement 3.7)
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from app.domain_events.models import DomainEvent
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Maps event_type string -> list of async handler callables
HandlerRegistry: dict[str, list[Callable]] = defaultdict(list)


def register_handler(event_type: str, handler: Callable) -> None:
    """Append an async handler callable to the registry for the given event type."""
    HandlerRegistry[event_type].append(handler)


async def dispatch_event(event: DomainEvent, correlation_id: str | None = None) -> None:
    """
    Look up all handlers registered for event.event_type and call each one.
    If no handler is registered, log a warning but do not raise.
    """
    handlers = HandlerRegistry.get(event.event_type, [])  # type: ignore[call-overload]
    if not handlers:
        logger.warning(
            "no_handler_registered",
            event_type=event.event_type,
            event_id=str(event.event_id),
            correlation_id=correlation_id,
        )
        return

    for handler in handlers:
        await handler(event, correlation_id)


# ---------------------------------------------------------------------------
# Stub handlers — pre-registered for all required event types (Requirement 3.7)
# Each stub logs the event type and event_id; real implementations will be
# added by the modules that own each event.
# ---------------------------------------------------------------------------

async def _stub_journey_stage_changed(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


async def _stub_questionnaire_submitted(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


async def _stub_interview_slot_created(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


async def _stub_offer_accepted(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


async def _stub_candidate_created(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


async def _stub_candidate_status_changed(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


async def _stub_role_assignment_changed(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


async def _stub_requisition_status_changed(event: DomainEvent, correlation_id: str | None) -> None:
    logger.info(
        "stub_handler_called",
        event_type=event.event_type,
        event_id=str(event.event_id),
        correlation_id=correlation_id,
    )


# Pre-register stub handlers — will be overridden by real handlers below
register_handler("journey_stage_changed", _stub_journey_stage_changed)
register_handler("questionnaire_submitted", _stub_questionnaire_submitted)
register_handler("interview_slot_created", _stub_interview_slot_created)
register_handler("offer_accepted", _stub_offer_accepted)
register_handler("candidate_created", _stub_candidate_created)
register_handler("candidate_status_changed", _stub_candidate_status_changed)
register_handler("role_assignment_changed", _stub_role_assignment_changed)
register_handler("requisition_status_changed", _stub_requisition_status_changed)


# ---------------------------------------------------------------------------
# Interview workflow event handlers (Requirement 8.2, 8.3, 8.4, 8.6)
# ---------------------------------------------------------------------------


async def _handle_journey_stage_changed(event: DomainEvent, correlation_id: str | None) -> None:
    """
    Handler for journey_stage_changed event.

    Notifies:
    - Candidate associated with the journey (Requirement 8.2)
    - Recruiter assigned to the requisition (Requirement 8.2)
    - Hiring manager assigned to the requisition (Requirement 8.2)

    Requirements: 8.1, 8.2
    """
    from app.database import AsyncSessionFactory
    from app.modules.notifications.service import NotificationService

    try:
        payload = event.payload or {}
        journey_id = payload.get("journey_id")
        org_id = payload.get("org_id")
        from_stage = payload.get("from_stage")
        to_stage = payload.get("to_stage")

        if not all([journey_id, org_id]):
            logger.warning(
                "journey_stage_changed_handler_missing_payload",
                event_id=str(event.event_id),
                correlation_id=correlation_id,
            )
            return

        async with AsyncSessionFactory() as db:
            from sqlalchemy import select
            from app.modules.journeys.models import InterviewJourney
            from app.modules.candidates.models import Candidate
            from app.modules.requisitions.models import JobRequisition
            from app.crypto import decrypt_field
            from uuid import UUID

            journey_id_uuid = UUID(journey_id) if isinstance(journey_id, str) else journey_id
            org_id_uuid = UUID(org_id) if isinstance(org_id, str) else org_id

            # Fetch journey and candidate
            journey_result = await db.execute(
                select(InterviewJourney).where(
                    InterviewJourney.interview_journey_id == journey_id_uuid,
                    InterviewJourney.deleted_at.is_(None),
                )
            )
            journey = journey_result.scalar_one_or_none()

            if not journey:
                logger.warning(
                    "journey_stage_changed_handler_journey_not_found",
                    journey_id=journey_id,
                    correlation_id=correlation_id,
                )
                return

            candidate_result = await db.execute(
                select(Candidate).where(
                    Candidate.candidate_id == journey.candidate_id,
                    Candidate.deleted_at.is_(None),
                )
            )
            candidate = candidate_result.scalar_one_or_none()

            if not candidate:
                logger.warning(
                    "journey_stage_changed_handler_candidate_not_found",
                    candidate_id=journey.candidate_id,
                    correlation_id=correlation_id,
                )
                return

            # Fetch requisition for recruiter and hiring manager
            req_result = await db.execute(
                select(JobRequisition).where(
                    JobRequisition.job_requisition_id == journey.job_requisition_id,
                    JobRequisition.deleted_at.is_(None),
                )
            )
            requisition = req_result.scalar_one_or_none()

            if not requisition:
                logger.warning(
                    "journey_stage_changed_handler_requisition_not_found",
                    requisition_id=journey.job_requisition_id,
                    correlation_id=correlation_id,
                )
                return

            # Prepare notification payload
            notification_payload = {
                "journey_id": journey_id,
                "candidate_name": candidate.first_name or "Candidate",
                "from_stage": from_stage or journey.current_stage,
                "to_stage": to_stage or journey.current_stage,
            }

            # Decrypt candidate email
            candidate_email = decrypt_field(candidate.email_encrypted) if candidate.email_encrypted else None
            if candidate_email:
                notification_service = NotificationService(db)
                await notification_service.deliver(
                    event_type="journey_stage_changed",
                    payload=notification_payload,
                    org_id=org_id_uuid,
                    recipient_email=candidate_email,
                    locale=None,
                )
                logger.info(
                    "journey_stage_changed_notification_sent",
                    journey_id=journey_id,
                    recipient="candidate",
                    recipient_email=candidate_email,
                    correlation_id=correlation_id,
                )

            # Fetch and notify recruiter if available
            if requisition.recruiter_user_id:
                from app.modules.users.models import User

                recruiter_result = await db.execute(
                    select(User).where(
                        User.user_id == requisition.recruiter_user_id,
                        User.deleted_at.is_(None),
                    )
                )
                recruiter = recruiter_result.scalar_one_or_none()

                if recruiter:
                    recruiter_email = decrypt_field(recruiter.email_encrypted) if recruiter.email_encrypted else None
                    if recruiter_email:
                        notification_service = NotificationService(db)
                        await notification_service.deliver(
                            event_type="journey_stage_changed",
                            payload=notification_payload,
                            org_id=org_id_uuid,
                            recipient_email=recruiter_email,
                            locale=None,
                        )
                        logger.info(
                            "journey_stage_changed_notification_sent",
                            journey_id=journey_id,
                            recipient="recruiter",
                            recipient_email=recruiter_email,
                            correlation_id=correlation_id,
                        )

            # Fetch and notify hiring manager if available
            if requisition.hiring_manager_user_id:
                from app.modules.users.models import User

                hiring_manager_result = await db.execute(
                    select(User).where(
                        User.user_id == requisition.hiring_manager_user_id,
                        User.deleted_at.is_(None),
                    )
                )
                hiring_manager = hiring_manager_result.scalar_one_or_none()

                if hiring_manager:
                    hiring_manager_email = decrypt_field(hiring_manager.email_encrypted) if hiring_manager.email_encrypted else None
                    if hiring_manager_email:
                        notification_service = NotificationService(db)
                        await notification_service.deliver(
                            event_type="journey_stage_changed",
                            payload=notification_payload,
                            org_id=org_id_uuid,
                            recipient_email=hiring_manager_email,
                            locale=None,
                        )
                        logger.info(
                            "journey_stage_changed_notification_sent",
                            journey_id=journey_id,
                            recipient="hiring_manager",
                            recipient_email=hiring_manager_email,
                            correlation_id=correlation_id,
                        )

    except Exception as exc:
        logger.error(
            "journey_stage_changed_handler_error",
            event_id=str(event.event_id),
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


async def _handle_candidate_questionnaire_response_created(event: DomainEvent, correlation_id: str | None) -> None:
    """
    Handler for candidate_questionnaire_response_created event.

    Notifies candidate with portal URL containing their portal token for questionnaire completion.

    Requirements: 8.1, 8.3
    """
    from app.database import AsyncSessionFactory
    from app.modules.notifications.service import NotificationService

    try:
        payload = event.payload or {}
        candidate_id = payload.get("candidate_id")
        response_id = payload.get("response_id")
        org_id = payload.get("org_id")
        portal_token = payload.get("portal_token")

        if not all([candidate_id, response_id, org_id]):
            logger.warning(
                "questionnaire_response_created_handler_missing_payload",
                event_id=str(event.event_id),
                correlation_id=correlation_id,
            )
            return

        async with AsyncSessionFactory() as db:
            from sqlalchemy import select
            from app.modules.candidates.models import Candidate
            from app.crypto import decrypt_field
            from uuid import UUID

            candidate_id_uuid = UUID(candidate_id) if isinstance(candidate_id, str) else candidate_id
            org_id_uuid = UUID(org_id) if isinstance(org_id, str) else org_id

            # Fetch candidate
            candidate_result = await db.execute(
                select(Candidate).where(
                    Candidate.candidate_id == candidate_id_uuid,
                    Candidate.deleted_at.is_(None),
                )
            )
            candidate = candidate_result.scalar_one_or_none()

            if not candidate:
                logger.warning(
                    "questionnaire_response_created_handler_candidate_not_found",
                    candidate_id=candidate_id,
                    correlation_id=correlation_id,
                )
                return

            # Decrypt candidate email
            candidate_email = decrypt_field(candidate.email_encrypted) if candidate.email_encrypted else None
            if not candidate_email:
                logger.warning(
                    "questionnaire_response_created_handler_no_email",
                    candidate_id=candidate_id,
                    correlation_id=correlation_id,
                )
                return

            # Build portal URL
            # The portal_token is passed in the payload from the service
            portal_url = f"https://portal.example.com/questionnaires?token={portal_token}" if portal_token else "https://portal.example.com/questionnaires"

            notification_payload = {
                "candidate_name": candidate.first_name or "Candidate",
                "portal_url": portal_url,
            }

            notification_service = NotificationService(db)
            await notification_service.deliver(
                event_type="candidate_questionnaire_response_created",
                payload=notification_payload,
                org_id=org_id_uuid,
                recipient_email=candidate_email,
                locale=None,
            )

            logger.info(
                "questionnaire_response_created_notification_sent",
                response_id=response_id,
                candidate_email=candidate_email,
                correlation_id=correlation_id,
            )

    except Exception as exc:
        logger.error(
            "questionnaire_response_created_handler_error",
            event_id=str(event.event_id),
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


async def _handle_interview_slot_created(event: DomainEvent, correlation_id: str | None) -> None:
    """
    Handler for interview_slot_created event.

    Notifies assigned interviewer of new interview invitation.

    Requirements: 8.1, 8.4
    """
    from app.database import AsyncSessionFactory
    from app.modules.notifications.service import NotificationService

    try:
        payload = event.payload or {}
        slot_id = payload.get("slot_id")
        org_id = payload.get("org_id")
        interviewer_user_id = payload.get("interviewer_user_id")
        scheduled_start = payload.get("scheduled_start")

        if not all([slot_id, org_id, interviewer_user_id]):
            logger.warning(
                "interview_slot_created_handler_missing_payload",
                event_id=str(event.event_id),
                correlation_id=correlation_id,
            )
            return

        async with AsyncSessionFactory() as db:
            from sqlalchemy import select
            from app.modules.slots.models import InterviewSlot
            from app.modules.users.models import User
            from app.crypto import decrypt_field
            from uuid import UUID

            slot_id_uuid = UUID(slot_id) if isinstance(slot_id, str) else slot_id
            org_id_uuid = UUID(org_id) if isinstance(org_id, str) else org_id
            interviewer_id_uuid = UUID(interviewer_user_id) if isinstance(interviewer_user_id, str) else interviewer_user_id

            # Fetch slot
            slot_result = await db.execute(
                select(InterviewSlot).where(
                    InterviewSlot.interview_slot_id == slot_id_uuid,
                    InterviewSlot.deleted_at.is_(None),
                )
            )
            slot = slot_result.scalar_one_or_none()

            if not slot:
                logger.warning(
                    "interview_slot_created_handler_slot_not_found",
                    slot_id=slot_id,
                    correlation_id=correlation_id,
                )
                return

            # Fetch interviewer user
            interviewer_result = await db.execute(
                select(User).where(
                    User.user_id == interviewer_id_uuid,
                    User.deleted_at.is_(None),
                )
            )
            interviewer = interviewer_result.scalar_one_or_none()

            if not interviewer:
                logger.warning(
                    "interview_slot_created_handler_interviewer_not_found",
                    interviewer_id=interviewer_user_id,
                    correlation_id=correlation_id,
                )
                return

            # Decrypt interviewer email
            interviewer_email = decrypt_field(interviewer.email_encrypted) if interviewer.email_encrypted else None
            if not interviewer_email:
                logger.warning(
                    "interview_slot_created_handler_no_email",
                    interviewer_id=interviewer_user_id,
                    correlation_id=correlation_id,
                )
                return

            notification_payload = {
                "interviewer_name": interviewer.first_name or "Interviewer",
                "slot_type": slot.type or "Interview",
                "scheduled_start": scheduled_start or slot.scheduled_start.isoformat(),
                "scheduled_end": slot.scheduled_end.isoformat(),
                "timezone": slot.timezone,
            }

            notification_service = NotificationService(db)
            await notification_service.deliver(
                event_type="interview_slot_created",
                payload=notification_payload,
                org_id=org_id_uuid,
                recipient_email=interviewer_email,
                locale=None,
            )

            logger.info(
                "interview_slot_created_notification_sent",
                slot_id=slot_id,
                interviewer_email=interviewer_email,
                correlation_id=correlation_id,
            )

    except Exception as exc:
        logger.error(
            "interview_slot_created_handler_error",
            event_id=str(event.event_id),
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


async def _handle_offer_accepted(event: DomainEvent, correlation_id: str | None) -> None:
    """
    Handler for offer_accepted event.

    Notifies all interviewers who were assigned to InterviewSlots on the journey.

    Requirements: 8.1, 8.6
    """
    from app.database import AsyncSessionFactory
    from app.modules.notifications.service import NotificationService

    try:
        payload = event.payload or {}
        journey_id = payload.get("journey_id")
        org_id = payload.get("org_id")

        if not all([journey_id, org_id]):
            logger.warning(
                "offer_accepted_handler_missing_payload",
                event_id=str(event.event_id),
                correlation_id=correlation_id,
            )
            return

        async with AsyncSessionFactory() as db:
            from sqlalchemy import select
            from app.modules.journeys.models import InterviewJourney
            from app.modules.slots.models import InterviewSlot
            from app.modules.users.models import User
            from app.modules.candidates.models import Candidate
            from app.crypto import decrypt_field
            from uuid import UUID

            journey_id_uuid = UUID(journey_id) if isinstance(journey_id, str) else journey_id
            org_id_uuid = UUID(org_id) if isinstance(org_id, str) else org_id

            # Fetch journey and candidate for context
            journey_result = await db.execute(
                select(InterviewJourney).where(
                    InterviewJourney.interview_journey_id == journey_id_uuid,
                    InterviewJourney.deleted_at.is_(None),
                )
            )
            journey = journey_result.scalar_one_or_none()

            if not journey:
                logger.warning(
                    "offer_accepted_handler_journey_not_found",
                    journey_id=journey_id,
                    correlation_id=correlation_id,
                )
                return

            candidate_result = await db.execute(
                select(Candidate).where(
                    Candidate.candidate_id == journey.candidate_id,
                    Candidate.deleted_at.is_(None),
                )
            )
            candidate = candidate_result.scalar_one_or_none()

            # Fetch all interview slots on this journey
            slots_result = await db.execute(
                select(InterviewSlot).where(
                    InterviewSlot.interview_journey_id == journey_id_uuid,
                    InterviewSlot.deleted_at.is_(None),
                )
            )
            slots = slots_result.scalars().all()

            if not slots:
                logger.info(
                    "offer_accepted_handler_no_slots",
                    journey_id=journey_id,
                    correlation_id=correlation_id,
                )
                return

            # Collect unique interviewer IDs
            interviewer_ids = set()
            for slot in slots:
                if slot.interviewer_user_id:
                    interviewer_ids.add(slot.interviewer_user_id)

            if not interviewer_ids:
                logger.info(
                    "offer_accepted_handler_no_interviewers",
                    journey_id=journey_id,
                    correlation_id=correlation_id,
                )
                return

            # Notify each interviewer
            notification_payload = {
                "candidate_name": candidate.first_name if candidate else "Candidate",
                "journey_id": journey_id,
            }

            notification_service = NotificationService(db)

            for interviewer_id in interviewer_ids:
                interviewer_result = await db.execute(
                    select(User).where(
                        User.user_id == interviewer_id,
                        User.deleted_at.is_(None),
                    )
                )
                interviewer = interviewer_result.scalar_one_or_none()

                if not interviewer:
                    logger.warning(
                        "offer_accepted_handler_interviewer_not_found",
                        interviewer_id=str(interviewer_id),
                        correlation_id=correlation_id,
                    )
                    continue

                interviewer_email = decrypt_field(interviewer.email_encrypted) if interviewer.email_encrypted else None
                if not interviewer_email:
                    logger.warning(
                        "offer_accepted_handler_no_email",
                        interviewer_id=str(interviewer_id),
                        correlation_id=correlation_id,
                    )
                    continue

                await notification_service.deliver(
                    event_type="offer_accepted",
                    payload=notification_payload,
                    org_id=org_id_uuid,
                    recipient_email=interviewer_email,
                    locale=None,
                )

                logger.info(
                    "offer_accepted_notification_sent",
                    journey_id=journey_id,
                    interviewer_email=interviewer_email,
                    correlation_id=correlation_id,
                )

    except Exception as exc:
        logger.error(
            "offer_accepted_handler_error",
            event_id=str(event.event_id),
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


# Override stub handlers with real implementations
# Clear the stub entries and replace with real handlers
HandlerRegistry["journey_stage_changed"] = [_handle_journey_stage_changed]
HandlerRegistry["candidate_questionnaire_response_created"] = [_handle_candidate_questionnaire_response_created]
HandlerRegistry["interview_slot_created"] = [_handle_interview_slot_created]
HandlerRegistry["offer_accepted"] = [_handle_offer_accepted]


# ---------------------------------------------------------------------------
# Survey event handlers (Requirement 9.9, 9.10, 9.17, 9.18)
# ---------------------------------------------------------------------------


async def _handle_survey_created(event: DomainEvent, correlation_id: str | None) -> None:
    """
    Handler for survey_created event.

    Calls NotificationService.deliver("survey_invitation", {survey_link, candidate_email}, org_id)
    using SurveyFeedbackTemplate for rendering.

    Requirements: 9.9, 9.17
    """
    from app.database import AsyncSessionFactory
    from app.modules.notifications.service import NotificationService

    try:
        payload = event.payload or {}
        survey_id = payload.get("survey_id")
        candidate_id = payload.get("candidate_id")
        org_id = payload.get("org_id")

        if not all([survey_id, candidate_id, org_id]):
            logger.warning(
                "survey_created_handler_missing_payload",
                event_id=str(event.event_id),
                correlation_id=correlation_id,
            )
            return

        async with AsyncSessionFactory() as db:
            from sqlalchemy import select
            from app.modules.surveys.models import CandidateFeedbackSurvey, CandidateFeedbackSurveyToken
            from app.modules.candidates.models import Candidate
            from app.crypto import decrypt_field
            from uuid import UUID

            survey_id_uuid = UUID(survey_id) if isinstance(survey_id, str) else survey_id
            candidate_id_uuid = UUID(candidate_id) if isinstance(candidate_id, str) else candidate_id
            org_id_uuid = UUID(org_id) if isinstance(org_id, str) else org_id

            # Fetch survey and candidate
            survey_result = await db.execute(
                select(CandidateFeedbackSurvey).where(
                    CandidateFeedbackSurvey.candidate_feedback_survey_id == survey_id_uuid,
                    CandidateFeedbackSurvey.deleted_at.is_(None),
                )
            )
            survey = survey_result.scalar_one_or_none()

            candidate_result = await db.execute(
                select(Candidate).where(
                    Candidate.candidate_id == candidate_id_uuid,
                    Candidate.deleted_at.is_(None),
                )
            )
            candidate = candidate_result.scalar_one_or_none()

            if not survey or not candidate:
                logger.warning(
                    "survey_created_handler_not_found",
                    survey_id=survey_id,
                    candidate_id=candidate_id,
                    correlation_id=correlation_id,
                )
                return

            # Decrypt candidate email
            candidate_email = decrypt_field(candidate.email_encrypted) if candidate.email_encrypted else None
            if not candidate_email:
                logger.warning(
                    "survey_created_handler_no_email",
                    candidate_id=candidate_id,
                    correlation_id=correlation_id,
                )
                return

            # Build survey link using token
            # The token is stored in the database as token_hash (never in plaintext)
            # The raw token is generated and sent in the email link
            # For the notification payload, we use a URL with a placeholder that will be
            # replaced by the actual token during email template rendering
            survey_link = f"https://portal.example.com/surveys/{{{{token}}}}"

            # Call NotificationService to deliver survey invitation
            notification_service = NotificationService(db)
            await notification_service.deliver(
                event_type="survey_invitation",
                payload={
                    "survey_link": survey_link,
                    "candidate_email": candidate_email,
                    "candidate_name": candidate.first_name or "Candidate",
                },
                org_id=org_id_uuid,
                recipient_email=candidate_email,
                locale=None,
                use_survey_template=True,  # Try SurveyFeedbackTemplate first (Requirement 9.17)
            )

            logger.info(
                "survey_invitation_delivered",
                survey_id=survey_id,
                candidate_email=candidate_email,
                correlation_id=correlation_id,
            )

    except Exception as exc:
        logger.error(
            "survey_created_handler_error",
            event_id=str(event.event_id),
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


async def _handle_survey_reminder(event: DomainEvent, correlation_id: str | None) -> None:
    """
    Handler for survey_reminder event.

    Calls NotificationService.deliver("survey_reminder", {survey_link, candidate_email}, org_id)
    using SurveyFeedbackTemplate for rendering.

    Requirements: 9.10, 9.18
    """
    from app.database import AsyncSessionFactory
    from app.modules.notifications.service import NotificationService

    try:
        payload = event.payload or {}
        survey_id = payload.get("survey_id")
        candidate_id = payload.get("candidate_id")
        org_id = payload.get("org_id")

        if not all([survey_id, candidate_id, org_id]):
            logger.warning(
                "survey_reminder_handler_missing_payload",
                event_id=str(event.event_id),
                correlation_id=correlation_id,
            )
            return

        async with AsyncSessionFactory() as db:
            from sqlalchemy import select
            from app.modules.surveys.models import CandidateFeedbackSurvey
            from app.modules.candidates.models import Candidate
            from app.crypto import decrypt_field
            from uuid import UUID

            survey_id_uuid = UUID(survey_id) if isinstance(survey_id, str) else survey_id
            candidate_id_uuid = UUID(candidate_id) if isinstance(candidate_id, str) else candidate_id
            org_id_uuid = UUID(org_id) if isinstance(org_id, str) else org_id

            # Fetch survey and candidate
            survey_result = await db.execute(
                select(CandidateFeedbackSurvey).where(
                    CandidateFeedbackSurvey.candidate_feedback_survey_id == survey_id_uuid,
                    CandidateFeedbackSurvey.deleted_at.is_(None),
                )
            )
            survey = survey_result.scalar_one_or_none()

            candidate_result = await db.execute(
                select(Candidate).where(
                    Candidate.candidate_id == candidate_id_uuid,
                    Candidate.deleted_at.is_(None),
                )
            )
            candidate = candidate_result.scalar_one_or_none()

            if not survey or not candidate:
                logger.warning(
                    "survey_reminder_handler_not_found",
                    survey_id=survey_id,
                    candidate_id=candidate_id,
                    correlation_id=correlation_id,
                )
                return

            # Decrypt candidate email
            candidate_email = decrypt_field(candidate.email_encrypted) if candidate.email_encrypted else None
            if not candidate_email:
                logger.warning(
                    "survey_reminder_handler_no_email",
                    candidate_id=candidate_id,
                    correlation_id=correlation_id,
                )
                return

            # Build survey link using token
            survey_link = f"https://portal.example.com/surveys/{{{{token}}}}"

            # Calculate days remaining until expiry
            days_remaining = (survey.expires_at - datetime.now(timezone.utc)).days

            # Call NotificationService to deliver survey reminder
            notification_service = NotificationService(db)
            await notification_service.deliver(
                event_type="survey_reminder",
                payload={
                    "survey_link": survey_link,
                    "candidate_email": candidate_email,
                    "candidate_name": candidate.first_name or "Candidate",
                    "days_remaining": max(0, days_remaining),
                },
                org_id=org_id_uuid,
                recipient_email=candidate_email,
                locale=None,
                use_survey_template=True,  # Try SurveyFeedbackTemplate first (Requirement 9.18)
            )

            logger.info(
                "survey_reminder_delivered",
                survey_id=survey_id,
                candidate_email=candidate_email,
                correlation_id=correlation_id,
            )

    except Exception as exc:
        logger.error(
            "survey_reminder_handler_error",
            event_id=str(event.event_id),
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


# Register survey event handlers
register_handler("survey_created", _handle_survey_created)
register_handler("survey_reminder", _handle_survey_reminder)
