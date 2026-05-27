"""
Base declarative class, audit mixin, and version mixin for all ORM models.

Provides:
- Base(DeclarativeBase): shared metadata for all models
- current_user_id_var: ContextVar holding the authenticated user's ID string
- AuditMixin: created_at, updated_at, deleted_at, created_by, updated_by, deleted_by
- VersionMixin: version column with SQLAlchemy optimistic locking (version_id_col)

A SessionEvents.before_flush listener automatically populates audit fields from
current_user_id_var on new, dirty, and soft-deleted instances.
"""

import uuid
from contextvars import ContextVar

from sqlalchemy import Column, DateTime, Integer, event, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Session, declared_attr

# ---------------------------------------------------------------------------
# Context variable — set by auth middleware before each request is handled
# ---------------------------------------------------------------------------

current_user_id_var: ContextVar[str | None] = ContextVar("current_user_id", default=None)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class AuditMixin:
    """Provides CreatedAt, UpdatedAt, DeletedAt, CreatedBy, UpdatedBy, DeletedBy columns."""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), nullable=True)


class VersionMixin:
    """Provides optimistic locking via SQLAlchemy version_id_col."""

    version = Column(Integer, nullable=False, default=1)

    @declared_attr
    def __mapper_args__(cls):  # noqa: N805
        return {"version_id_col": cls.__table__.c.version}


# ---------------------------------------------------------------------------
# before_flush listener — populates audit fields from current_user_id_var
# ---------------------------------------------------------------------------


def _set_audit_fields(session, flush_context, instances):  # noqa: ARG001
    """
    SQLAlchemy before_flush event listener.

    - New instances (session.new): set created_by and updated_by
    - Dirty instances (session.dirty): set updated_by
    - Soft-deleted dirty instances (deleted_at being set): also set deleted_by
    """
    user_id_str = current_user_id_var.get()
    user_uuid: uuid.UUID | None = None
    if user_id_str:
        try:
            user_uuid = uuid.UUID(user_id_str)
        except (ValueError, AttributeError):
            user_uuid = None

    # New instances
    for instance in session.new:
        if isinstance(instance, AuditMixin):
            instance.created_by = user_uuid
            instance.updated_by = user_uuid

    # Dirty instances
    for instance in session.dirty:
        if not isinstance(instance, AuditMixin):
            continue

        instance.updated_by = user_uuid

        # Detect soft-delete: deleted_at is being set to a non-null value on this flush
        from sqlalchemy import inspect as sa_inspect  # local import to avoid circularity

        attr_state = sa_inspect(instance).attrs.deleted_at
        # history.added contains the new value being written
        added = attr_state.history.added
        if added and added[0] is not None:
            instance.deleted_by = user_uuid


# Register the listener on the sync Session class.
# AsyncSession delegates flush operations to the underlying sync Session,
# so this listener fires for both sync and async sessions.
event.listen(Session, "before_flush", _set_audit_fields)
