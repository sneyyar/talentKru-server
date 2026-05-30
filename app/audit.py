"""
Audit logging service for tracking user actions and system events.

Provides:
- write_audit_log: Helper function for writing audit log entries to both structured logs and database

Requirements: 7.3, 2.4, 2.5, 5.8, 6.9, 9.8, 10.10
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit_models import AuditLog
from app.observability.logging import get_logger

logger = get_logger(__name__)


async def write_audit_log(
    actor_id: str | UUID,
    action: str,
    target_entity: Optional[str] = None,
    target_id: Optional[str | UUID] = None,
    org_id: Optional[str | UUID] = None,
    changed_values: Optional[dict[str, Any]] = None,
    obo_by: Optional[str | UUID] = None,
    timestamp: Optional[datetime] = None,
    db: Optional[AsyncSession] = None,
) -> None:
    """
    Write an audit log entry to both structured logs and the database.

    Args:
        actor_id: User ID of the actor performing the action
        action: Action type (e.g., "AccountActivated", "PasswordReset", "ImpersonationStarted")
        target_entity: Entity type being affected (e.g., "User", "Role")
        target_id: ID of the entity being affected
        org_id: Organization ID for scoping
        changed_values: Dictionary of changed field values
        obo_by: SuperAdmin user ID if this is an on-behalf-of action
        timestamp: Timestamp of the action (defaults to now)
        db: AsyncSession for database persistence (optional; if not provided, only logs to structured logs)

    Requirements: 7.3, 2.4, 2.5, 5.8, 6.9, 9.8, 10.10
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    # Convert UUIDs to strings for logging
    actor_id_str = str(actor_id) if actor_id else None
    target_id_str = str(target_id) if target_id else None
    org_id_uuid = None
    if org_id:
        try:
            org_id_uuid = UUID(str(org_id)) if not isinstance(org_id, UUID) else org_id
        except (ValueError, AttributeError):
            pass
    obo_by_str = str(obo_by) if obo_by else None

    # Log the audit entry to structured logs
    logger.info(
        "audit_log",
        actor_id=actor_id_str,
        action=action,
        target_entity=target_entity,
        target_id=target_id_str,
        org_id=str(org_id_uuid) if org_id_uuid else None,
        changed_values=changed_values,
        obo_by=obo_by_str,
        timestamp=timestamp.isoformat(),
    )

    # Persist to audit_log table if db session is provided
    if db is not None:
        audit_entry = AuditLog(
            actor_id=actor_id_str,
            action=action,
            target_entity=target_entity,
            target_id=target_id_str,
            org_id=org_id_uuid,
            changed_values=changed_values,
            obo_by=obo_by_str,
            timestamp=timestamp,
        )
        db.add(audit_entry)
        await db.flush()
