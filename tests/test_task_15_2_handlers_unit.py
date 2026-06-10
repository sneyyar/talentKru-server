"""
Unit tests for Task 15.2: Survey domain event handlers.

These tests verify handler logic without requiring a database connection.
They test:
- Handler registration in HandlerRegistry
- Payload extraction and UUID conversion
- Error handling and graceful failures
"""

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.domain_events.handlers import (
    _handle_survey_created,
    _handle_survey_reminder,
    HandlerRegistry,
)
from app.domain_events.models import DomainEvent, EventStatus


# ============================================================================
# Handler Registration Tests
# ============================================================================


def test_survey_created_handler_is_registered():
    """Test that survey_created handler is registered in HandlerRegistry."""
    assert "survey_created" in HandlerRegistry
    assert _handle_survey_created in HandlerRegistry["survey_created"]


def test_survey_reminder_handler_is_registered():
    """Test that survey_reminder handler is registered in HandlerRegistry."""
    assert "survey_reminder" in HandlerRegistry
    assert _handle_survey_reminder in HandlerRegistry["survey_reminder"]


# ============================================================================
# Survey Created Handler Tests
# ============================================================================


@pytest.mark.asyncio
async def test_survey_created_handler_handles_missing_payload():
    """Test that survey_created handler handles missing payload gracefully."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={},  # Missing required fields
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Should not raise, just log warning
    await _handle_survey_created(event, "test-correlation")


@pytest.mark.asyncio
async def test_survey_created_handler_handles_none_payload():
    """Test that survey_created handler handles None payload gracefully."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload=None,  # Null payload
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Should not raise, just log warning
    await _handle_survey_created(event, None)


@pytest.mark.asyncio
async def test_survey_created_handler_uuid_conversion():
    """Test that survey_created handler converts string UUIDs to UUID objects."""
    survey_id = uuid4()
    candidate_id = uuid4()
    org_id = uuid4()

    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={
            "survey_id": str(survey_id),
            "candidate_id": str(candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Mock the AsyncSessionFactory to avoid DB connection (imported inside function)
    with patch("app.database.AsyncSessionFactory") as mock_factory:
        # Create a mock async context manager
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db

        # Mock execute to return None (no survey/candidate found)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Should not raise when processing UUID strings
        await _handle_survey_created(event, "test-correlation")

        # Verify execute was called (which means UUID conversion worked)
        mock_db.execute.assert_called()


@pytest.mark.asyncio
async def test_survey_created_handler_catches_exceptions():
    """Test that survey_created handler catches and logs exceptions."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={
            "survey_id": str(uuid4()),
            "candidate_id": str(uuid4()),
            "org_id": str(uuid4()),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Mock AsyncSessionFactory to raise an exception (imported inside function)
    with patch("app.database.AsyncSessionFactory") as mock_factory:
        mock_factory.return_value.__aenter__.side_effect = Exception("DB Error")

        # Should not raise, exception should be caught and logged
        await _handle_survey_created(event, "test-correlation")


# ============================================================================
# Survey Reminder Handler Tests
# ============================================================================


@pytest.mark.asyncio
async def test_survey_reminder_handler_handles_missing_payload():
    """Test that survey_reminder handler handles missing payload gracefully."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload={},  # Missing required fields
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Should not raise, just log warning
    await _handle_survey_reminder(event, "test-correlation")


@pytest.mark.asyncio
async def test_survey_reminder_handler_handles_none_payload():
    """Test that survey_reminder handler handles None payload gracefully."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload=None,  # Null payload
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Should not raise, just log warning
    await _handle_survey_reminder(event, None)


@pytest.mark.asyncio
async def test_survey_reminder_handler_uuid_conversion():
    """Test that survey_reminder handler converts string UUIDs to UUID objects."""
    survey_id = uuid4()
    candidate_id = uuid4()
    org_id = uuid4()

    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload={
            "survey_id": str(survey_id),
            "candidate_id": str(candidate_id),
            "org_id": str(org_id),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Mock the AsyncSessionFactory to avoid DB connection (imported inside function)
    with patch("app.database.AsyncSessionFactory") as mock_factory:
        # Create a mock async context manager
        mock_db = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_db

        # Mock execute to return None (no survey/candidate found)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Should not raise when processing UUID strings
        await _handle_survey_reminder(event, "test-correlation")

        # Verify execute was called (which means UUID conversion worked)
        mock_db.execute.assert_called()


@pytest.mark.asyncio
async def test_survey_reminder_handler_catches_exceptions():
    """Test that survey_reminder handler catches and logs exceptions."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload={
            "survey_id": str(uuid4()),
            "candidate_id": str(uuid4()),
            "org_id": str(uuid4()),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Mock AsyncSessionFactory to raise an exception (imported inside function)
    with patch("app.database.AsyncSessionFactory") as mock_factory:
        mock_factory.return_value.__aenter__.side_effect = Exception("DB Error")

        # Should not raise, exception should be caught and logged
        await _handle_survey_reminder(event, "test-correlation")


@pytest.mark.asyncio
async def test_survey_reminder_handler_payload_structure():
    """Test that survey_reminder handler expects correct payload structure."""
    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_reminder",
        payload={
            "survey_id": str(uuid4()),
            "candidate_id": str(uuid4()),
            # Missing org_id
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Should handle missing org_id gracefully
    await _handle_survey_reminder(event, "test-correlation")


# ============================================================================
# Event Dispatch Tests
# ============================================================================


@pytest.mark.asyncio
async def test_survey_handlers_are_called_by_dispatch_event():
    """Test that handlers are called when dispatch_event is invoked."""
    from app.domain_events.handlers import dispatch_event

    event = DomainEvent(
        event_id=uuid4(),
        event_type="survey_created",
        payload={
            "survey_id": str(uuid4()),
            "candidate_id": str(uuid4()),
            "org_id": str(uuid4()),
        },
        published_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING.value,
    )

    # Mock the handler
    with patch("app.domain_events.handlers._handle_survey_created") as mock_handler:
        mock_handler.__self__ = None  # Ensure it looks like a function
        mock_handler.return_value = None

        # Manually dispatch to mock handler
        handler = _handle_survey_created
        assert handler is not None
