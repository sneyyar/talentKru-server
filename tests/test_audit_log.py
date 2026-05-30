"""
Tests for the audit logging service.

Tests:
- write_audit_log persists to database
- write_audit_log logs to structured logs
- write_audit_log handles optional parameters
- write_audit_log converts UUIDs to strings
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from app.audit import write_audit_log
from app.audit_models import AuditLog


@pytest.mark.asyncio
async def test_write_audit_log_with_db_session():
    """Test that write_audit_log persists to database when db session is provided."""
    # Create a mock AsyncSession
    mock_db = AsyncMock()
    
    actor_id = str(uuid4())
    org_id = uuid4()
    target_id = str(uuid4())
    timestamp = datetime.now(timezone.utc)
    changed_values = {"field1": "old_value", "field2": "new_value"}
    
    # Call write_audit_log
    await write_audit_log(
        actor_id=actor_id,
        action="TestAction",
        target_entity="TestEntity",
        target_id=target_id,
        org_id=org_id,
        changed_values=changed_values,
        obo_by=None,
        timestamp=timestamp,
        db=mock_db,
    )
    
    # Verify that db.add was called
    assert mock_db.add.called
    
    # Verify that db.flush was called
    assert mock_db.flush.called
    
    # Get the audit entry that was added
    added_entry = mock_db.add.call_args[0][0]
    
    # Verify the audit entry has correct values
    assert isinstance(added_entry, AuditLog)
    assert added_entry.actor_id == actor_id
    assert added_entry.action == "TestAction"
    assert added_entry.target_entity == "TestEntity"
    assert added_entry.target_id == target_id
    assert added_entry.org_id == org_id
    assert added_entry.changed_values == changed_values
    assert added_entry.obo_by is None
    assert added_entry.timestamp == timestamp


@pytest.mark.asyncio
async def test_write_audit_log_without_db_session():
    """Test that write_audit_log works without db session (logs only)."""
    actor_id = str(uuid4())
    
    # Call write_audit_log without db session
    with patch('app.audit.logger') as mock_logger:
        await write_audit_log(
            actor_id=actor_id,
            action="TestAction",
            target_entity="TestEntity",
        )
        
        # Verify that logger.info was called
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_write_audit_log_with_uuid_conversion():
    """Test that write_audit_log converts UUIDs to strings."""
    mock_db = AsyncMock()
    
    actor_id = uuid4()
    org_id = uuid4()
    target_id = uuid4()
    obo_by = uuid4()
    
    await write_audit_log(
        actor_id=actor_id,
        action="TestAction",
        target_entity="TestEntity",
        target_id=target_id,
        org_id=org_id,
        obo_by=obo_by,
        db=mock_db,
    )
    
    # Get the audit entry that was added
    added_entry = mock_db.add.call_args[0][0]
    
    # Verify that UUIDs were converted to strings
    assert isinstance(added_entry.actor_id, str)
    assert isinstance(added_entry.target_id, str)
    assert isinstance(added_entry.obo_by, str)
    assert added_entry.org_id == org_id  # org_id should remain as UUID


@pytest.mark.asyncio
async def test_write_audit_log_with_default_timestamp():
    """Test that write_audit_log uses current time if timestamp not provided."""
    mock_db = AsyncMock()
    
    before = datetime.now(timezone.utc)
    
    await write_audit_log(
        actor_id="test_actor",
        action="TestAction",
        db=mock_db,
    )
    
    after = datetime.now(timezone.utc)
    
    # Get the audit entry that was added
    added_entry = mock_db.add.call_args[0][0]
    
    # Verify that timestamp is set and is between before and after
    assert added_entry.timestamp is not None
    assert before <= added_entry.timestamp <= after


@pytest.mark.asyncio
async def test_write_audit_log_with_obo_by():
    """Test that write_audit_log correctly handles obo_by parameter."""
    mock_db = AsyncMock()
    
    actor_id = str(uuid4())
    obo_by = str(uuid4())
    
    await write_audit_log(
        actor_id=actor_id,
        action="ImpersonationStarted",
        target_entity="User",
        obo_by=obo_by,
        db=mock_db,
    )
    
    # Get the audit entry that was added
    added_entry = mock_db.add.call_args[0][0]
    
    # Verify that obo_by is set correctly
    assert added_entry.obo_by == obo_by


@pytest.mark.asyncio
async def test_write_audit_log_with_changed_values():
    """Test that write_audit_log correctly handles changed_values parameter."""
    mock_db = AsyncMock()
    
    changed_values = {
        "status": {"old": "Active", "new": "Locked"},
        "failed_attempts": {"old": 4, "new": 5},
    }
    
    await write_audit_log(
        actor_id="test_actor",
        action="UserLocked",
        target_entity="User",
        changed_values=changed_values,
        db=mock_db,
    )
    
    # Get the audit entry that was added
    added_entry = mock_db.add.call_args[0][0]
    
    # Verify that changed_values is set correctly
    assert added_entry.changed_values == changed_values
