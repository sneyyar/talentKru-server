"""
Service-layer transaction management.

Provides:
- atomic_transaction: Context manager for explicit service-layer transactions
- Handles commit on success, rollback on exception
- Structured logging for audit trail
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def atomic_transaction(
    db: AsyncSession,
    operation_name: str,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for service-layer transactions.

    Wraps an operation in an explicit transaction with commit/rollback semantics:
    - On successful completion: commits transaction
    - On exception: rolls back transaction and re-raises

    Args:
        db: SQLAlchemy AsyncSession instance
        operation_name: Descriptive name for logging (e.g., "create_candidate")

    Yields:
        The same AsyncSession

    Raises:
        Any exception raised within the context (after rollback)
    """
    try:
        yield db
        await db.commit()
        logger.info(
            "transaction_committed",
            operation=operation_name,
        )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "transaction_rolled_back",
            operation=operation_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise
