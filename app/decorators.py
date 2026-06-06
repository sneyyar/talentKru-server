"""
Decorators for service-layer transaction management.

Provides:
- @transactional(): Decorator for write operations (commits on success)
- @read_only: Decorator for read operations (no transaction)
"""

from functools import wraps
from typing import Any, Callable, Optional

from app.service_base import atomic_transaction


def transactional(name: Optional[str] = None) -> Callable:
    """
    Decorator for service methods that modify state.

    Wraps the method in atomic_transaction automatically.
    Use for all write operations.

    Usage:
        @transactional()
        async def create_candidate(self, ...):
            # Just do the work, decorator handles transaction
            candidate = Candidate(...)
            self.db.add(candidate)
            return candidate

        @transactional(name="custom_operation_name")
        async def multi_step_operation(self, ...):
            # Complex operation with custom name for logging
            ...

    Args:
        name: Optional custom name for logging (defaults to method name)

    Returns:
        Decorated async method
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            operation_name = name or func.__name__
            async with atomic_transaction(self.db, operation_name):
                return await func(self, *args, **kwargs)

        return wrapper

    return decorator


def read_only(func: Callable) -> Callable:
    """
    Decorator for service methods that only read data.

    Does NOT wrap in transaction. Use for queries only.

    Usage:
        @read_only
        async def get_candidate(self, candidate_id):
            result = await self.db.execute(select(Candidate).where(...))
            return result.scalar_one_or_none()

    Returns:
        Original method (no modification)
    """
    # Intentionally a no-op; provides explicit intent marker
    @wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        return await func(self, *args, **kwargs)

    return wrapper
