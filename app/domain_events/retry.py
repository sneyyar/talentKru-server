"""
Domain event retry module.

Provides:
- retry_failed_events(): queries all DomainEvents with Status=FAILED and
  re-dispatches each one via _dispatch_with_status_update, logging results.

Requirements: 3.5, 3.6
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain_events.models import DomainEvent, EventStatus
from app.domain_events.publisher import _dispatch_with_status_update
from app.observability.logging import get_logger

logger = get_logger(__name__)


async def retry_failed_events(db: AsyncSession) -> dict:
    """
    Query all DomainEvents with status=FAILED and re-dispatch each one.

    Each event is re-dispatched via _dispatch_with_status_update, which opens
    its own session, calls registered handlers, and updates the event status to
    Processed or Failed.  Results are logged at INFO (success) or ERROR (failure).

    Returns a summary dict with counts:
      - retried: number of events successfully re-dispatched
      - errors:  number of events that raised an exception during re-dispatch
      - total:   total number of FAILED events found

    Requirements: 3.5, 3.6
    """
    stmt = select(DomainEvent).where(DomainEvent.status == EventStatus.Failed)
    result = await db.execute(stmt)
    failed_events = list(result.scalars().all())

    retried = 0
    errors = 0

    for event in failed_events:
        try:
            await _dispatch_with_status_update(event.event_id, event.correlation_id)
            retried += 1
            logger.info(
                "domain_event_retry_dispatched",
                event_id=str(event.event_id),
                event_type=event.event_type,
            )
        except Exception as exc:
            errors += 1
            logger.error(
                "domain_event_retry_failed",
                event_id=str(event.event_id),
                event_type=event.event_type,
                error=str(exc),
            )

    return {"retried": retried, "errors": errors, "total": len(failed_events)}
