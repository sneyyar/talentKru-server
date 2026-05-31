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


# Pre-register all stub handlers
register_handler("journey_stage_changed", _stub_journey_stage_changed)
register_handler("questionnaire_submitted", _stub_questionnaire_submitted)
register_handler("interview_slot_created", _stub_interview_slot_created)
register_handler("offer_accepted", _stub_offer_accepted)
register_handler("candidate_created", _stub_candidate_created)
register_handler("candidate_status_changed", _stub_candidate_status_changed)
register_handler("role_assignment_changed", _stub_role_assignment_changed)
register_handler("requisition_status_changed", _stub_requisition_status_changed)
