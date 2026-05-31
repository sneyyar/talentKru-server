"""
Domain event publisher.

Provides:
- publish_event(): persist-first pattern — writes DomainEvent with Status=Pending
  inside the current transaction, then schedules async dispatch via BackgroundTasks.
  If BackgroundTasks is unavailable, the event remains Pending for later retry.
- _dispatch_with_status_update(): background task that calls registered handlers
  and updates the event status to Processed or Failed in its own session.
"""

import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionFactory
from app.domain_events.handlers import dispatch_event
from app.domain_events.models import DomainEvent, EventStatus
from app.observability.logging import get_logger

logger = get_logger(__name__)


async def publish_event(
    event_type: str,
    payload: dict,
    db: AsyncSession,
    background_tasks: BackgroundTasks | None = None,
    correlation_id: str | None = None,
) -> DomainEvent:
    """
    Persist a domain event and schedule async dispatch.

    The event is written to the domain_events table (Status=Pending) inside the
    caller's active transaction via db.flush().  If background_tasks is provided,
    the handler is scheduled as a background task.  If background_tasks is None,
    a WARNING is logged and the event remains Pending for the scheduled retry job.

    Requirements: 3.1, 3.3
    """
    event = DomainEvent(
        event_id=uuid.uuid4(),
        event_type=event_type,
        payload=payload,
        published_at=datetime.now(timezone.utc),
        status=EventStatus.Pending,
        correlation_id=correlation_id,
    )
    db.add(event)
    await db.flush()  # persist within current transaction

    if background_tasks is not None:
        background_tasks.add_task(
            _dispatch_with_status_update, event.event_id, correlation_id
        )
    else:
        logger.warning(
            "background_tasks_unavailable",
            event_id=str(event.event_id),
            event_type=event_type,
        )
    return event


async def _dispatch_with_status_update(
    event_id: uuid.UUID, correlation_id: str | None
) -> None:
    """
    Background task: load the event, call all registered handlers, then commit
    the status update (Processed or Failed) in a dedicated session.

    The finally block guarantees the status commit runs even if error logging
    itself raises — satisfying Requirement 3.5.

    Requirements: 3.4, 3.5
    """
    async with AsyncSessionFactory() as db:
        event = await db.get(DomainEvent, event_id)
        try:
            await dispatch_event(event, correlation_id)
            event.status = EventStatus.Processed
            event.processed_at = datetime.now(timezone.utc)
        except Exception as exc:
            event.status = EventStatus.Failed
            logger.error(
                "domain_event_handler_failed",
                event_id=str(event_id),
                correlation_id=correlation_id,
                error=str(exc),
            )
        finally:
            await db.commit()
