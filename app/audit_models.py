"""
ORM model for the audit_log table.

Provides:
- AuditLog(Base): persisted audit log record with indexes on actor_id, org_id, and timestamp
"""

import uuid
from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.base_model import Base


class AuditLog(Base):
    """
    Audit log entry for tracking user actions and system events.
    
    Fields:
    - audit_log_id: UUID primary key
    - actor_id: User ID of the actor performing the action
    - action: Action type (e.g., "AccountActivated", "PasswordReset", "ImpersonationStarted")
    - target_entity: Entity type being affected (e.g., "User", "Role")
    - target_id: ID of the entity being affected
    - org_id: Organization ID for scoping
    - changed_values: Dictionary of changed field values (JSONB)
    - obo_by: SuperAdmin user ID if this is an on-behalf-of action
    - timestamp: Timestamp of the action (UTC)
    
    Requirements: 7.3, 2.4, 2.5, 5.8, 6.9, 9.8, 10.10
    """
    __tablename__ = "audit_logs"

    audit_log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(String(255), nullable=False, index=True)
    action = Column(String(128), nullable=False, index=True)
    target_entity = Column(String(128), nullable=True)
    target_id = Column(String(255), nullable=True)
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    changed_values = Column(JSONB, nullable=True)
    obo_by = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
