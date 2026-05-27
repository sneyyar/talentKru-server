"""
ORM model for the domain_events table.

Provides:
- EventStatus(str, enum.Enum): PENDING, PROCESSED, FAILED
- DomainEvent(Base): persisted event record with indexes on status and event_type
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.base_model import Base


class EventStatus(str, enum.Enum):
    PENDING = "Pending"
    PROCESSED = "Processed"
    FAILED = "Failed"


class DomainEvent(Base):
    __tablename__ = "domain_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(128), nullable=False, index=True)
    payload = Column(JSONB, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        SQLEnum(EventStatus),
        nullable=False,
        default=EventStatus.PENDING,
        index=True,
    )
    correlation_id = Column(String(64), nullable=True)
