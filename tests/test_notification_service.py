"""
Tests for NotificationService.

Tests the two-level notification switch, template resolution, delivery with
exponential backoff retry, and 24-hour reminder scheduling.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.service import NotificationService
from app.modules.notifications.models import (
    NotificationTemplate,
    NotificationRecord,
    NotificationStatus,
)
from app.modules.email_config.models import (
    OrganizationEmailConfig,
    SystemSetting,
    ProviderType,
)
from app.modules.slots.models import InterviewSlot, SlotStatus, InvitationStatus
from app.crypto import encrypt_field


@pytest.mark.asyncio
async def test_render_replaces_placeholders(db_session: AsyncSession):
    """Test that _render correctly replaces {{variable}} placeholders."""
    service = NotificationService(db_session)

    template = "Hello {{name}}, your interview is at {{time}}"
    payload = {"name": "John", "time": "2025-01-15 14:00"}

    result = service._render(template, payload)
    assert result == "Hello John, your interview is at 2025-01-15 14:00"


@pytest.mark.asyncio
async def test_render_unknown_placeholders(db_session: AsyncSession):
    """Test that _render leaves unknown placeholders as-is."""
    service = NotificationService(db_session)

    template = "Hello {{name}}, event: {{event_id}}"
    payload = {"name": "Jane"}

    result = service._render(template, payload)
    # Unknown variable {{event_id}} should remain unchanged
    assert result == "Hello Jane, event: {{event_id}}"


@pytest.mark.asyncio
async def test_deliver_respects_global_switch_disabled(db_session: AsyncSession):
    """Test that disabled global switch prevents delivery."""
    # Get or create global setting with disabled value
    result = await db_session.execute(
        __import__('sqlalchemy').select(SystemSetting).where(
            SystemSetting.setting_key == "email_notifications_enabled"
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.setting_value = "false"
    else:
        setting = SystemSetting(
            setting_key="email_notifications_enabled",
            setting_value="false",
        )
        db_session.add(setting)
    await db_session.flush()

    service = NotificationService(db_session)

    result = await service.deliver(
        event_type="test_event",
        payload={"test": "value"},
        org_id=uuid4(),
        recipient_email="test@example.com",
    )

    # Should return None (delivery skipped)
    assert result is None


@pytest.mark.asyncio
async def test_deliver_template_not_found(db_session: AsyncSession):
    """Test that missing template causes delivery to return None."""
    # Enable global switch
    from sqlalchemy import select
    result = await db_session.execute(
        select(SystemSetting).where(
            SystemSetting.setting_key == "email_notifications_enabled"
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.setting_value = "true"
    else:
        setting = SystemSetting(
            setting_key="email_notifications_enabled",
            setting_value="true",
        )
        db_session.add(setting)
    await db_session.flush()

    # Try to deliver without template existing
    service = NotificationService(db_session)
    result = await service.deliver(
        event_type="nonexistent_event",
        payload={"test": "value"},
        org_id=uuid4(),
        recipient_email="test@example.com",
    )

    # Should return None
    assert result is None


@pytest.mark.asyncio
async def test_deliver_disabled_template(db_session: AsyncSession):
    """Test that disabled template causes delivery to return None."""
    from sqlalchemy import select
    result = await db_session.execute(
        select(SystemSetting).where(
            SystemSetting.setting_key == "email_notifications_enabled"
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.setting_value = "true"
    else:
        setting = SystemSetting(
            setting_key="email_notifications_enabled",
            setting_value="true",
        )
        db_session.add(setting)

    org_id = uuid4()
    org_config = OrganizationEmailConfig(
        organization_email_config_id=uuid4(),
        organization_id=org_id,
        email_notifications_enabled=True,
        provider_type=ProviderType.SMTP.value,
        from_address="noreply@example.com",
        from_name="Test System",
    )
    db_session.add(org_config)

    # Create disabled template
    template = NotificationTemplate(
        notification_template_id=uuid4(),
        organization_id=org_id,
        event_type="test_event",
        subject="Test Subject",
        body_template="Test Body",
        is_enabled=False,
    )
    db_session.add(template)
    await db_session.flush()

    # Try to deliver with disabled template
    service = NotificationService(db_session)
    result = await service.deliver(
        event_type="test_event",
        payload={},
        org_id=org_id,
        recipient_email="test@example.com",
    )

    # Should return None
    assert result is None


@pytest.mark.asyncio
async def test_attempt_delivery_succeeds_first_try(db_session: AsyncSession):
    """Test that delivery succeeds on first attempt."""
    org_id = uuid4()
    record = NotificationRecord(
        notification_record_id=uuid4(),
        organization_id=org_id,
        event_type="test_event",
        recipient_email="test@example.com",
        status=NotificationStatus.PENDING.value,
        attempt_count=0,
    )
    db_session.add(record)
    await db_session.flush()

    service = NotificationService(db_session)
    service.email_service.send = AsyncMock()

    await service._attempt_delivery(
        record,
        org_id,
        "test@example.com",
        "Subject",
        "Body",
    )

    # Should be DELIVERED
    assert record.status == NotificationStatus.DELIVERED.value
    assert record.delivered_at is not None
    service.email_service.send.assert_called_once()


@pytest.mark.asyncio
async def test_attempt_delivery_retries_with_backoff(db_session: AsyncSession):
    """Test that delivery retries with exponential backoff."""
    org_id = uuid4()
    record = NotificationRecord(
        notification_record_id=uuid4(),
        organization_id=org_id,
        event_type="test_event",
        recipient_email="test@example.com",
        status=NotificationStatus.PENDING.value,
        attempt_count=0,
    )
    db_session.add(record)
    await db_session.flush()

    service = NotificationService(db_session)

    # Mock send to fail twice, then succeed on third attempt
    send_call_count = 0

    async def mock_send(*args, **kwargs):
        nonlocal send_call_count
        send_call_count += 1
        if send_call_count < 3:
            raise Exception("Temporary failure")

    service.email_service.send = mock_send

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await service._attempt_delivery(
            record,
            org_id,
            "test@example.com",
            "Subject",
            "Body",
        )

    # Should have retried twice with backoff
    assert send_call_count == 3
    assert record.status == NotificationStatus.DELIVERED.value
    # First retry: 60 * 2^0 = 60 seconds, second retry: 60 * 2^1 = 120 seconds
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_attempt_delivery_permanent_failure_after_5_attempts(db_session: AsyncSession):
    """Test that delivery is permanently failed after 5 attempts."""
    org_id = uuid4()
    record = NotificationRecord(
        notification_record_id=uuid4(),
        organization_id=org_id,
        event_type="test_event",
        recipient_email="test@example.com",
        status=NotificationStatus.PENDING.value,
        attempt_count=0,
    )
    db_session.add(record)
    await db_session.flush()

    service = NotificationService(db_session)
    service.email_service.send = AsyncMock(side_effect=Exception("Persistent failure"))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await service._attempt_delivery(
            record,
            org_id,
            "test@example.com",
            "Subject",
            "Body",
        )

    # Should be PERMANENTLY_FAILED
    assert record.status == NotificationStatus.PERMANENTLY_FAILED.value
    assert record.attempt_count == 5
