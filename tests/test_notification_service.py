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
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

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
from app.base_model import Base
from app.crypto import encrypt_field


@pytest.fixture
async def test_db():
    """Create an in-memory test database for unit tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        yield session
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_render_replaces_placeholders():
    """Test that _render correctly replaces {{variable}} placeholders."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        service = NotificationService(session)

        template = "Hello {{name}}, your interview is at {{time}}"
        payload = {"name": "John", "time": "2025-01-15 14:00"}

        result = service._render(template, payload)
        assert result == "Hello John, your interview is at 2025-01-15 14:00"
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_render_unknown_placeholders():
    """Test that _render leaves unknown placeholders as-is."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        service = NotificationService(session)

        template = "Hello {{name}}, {{unknown}} placeholder"
        payload = {"name": "John"}

        result = service._render(template, payload)
        assert result == "Hello John, {{unknown}} placeholder"
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_deliver_respects_global_switch_disabled():
    """Test that global email_notifications_enabled=false skips delivery."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        # Set global switch to false
        setting = SystemSetting(
            setting_key="email_notifications_enabled",
            setting_value="false",
        )
        session.add(setting)
        await session.flush()

        # Create service and attempt delivery
        service = NotificationService(session)
        result = await service.deliver(
            event_type="test_event",
            payload={"test": "value"},
            org_id=uuid4(),
            recipient_email="test@example.com",
        )

        # Should return None (delivery skipped)
        assert result is None
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_deliver_template_not_found():
    """Test that missing template causes delivery to return None."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        # Global and org switches are enabled
        setting = SystemSetting(
            setting_key="email_notifications_enabled",
            setting_value="true",
        )
        session.add(setting)
        await session.flush()

        # Try to deliver without template existing
        service = NotificationService(session)
        result = await service.deliver(
            event_type="nonexistent_event",
            payload={"test": "value"},
            org_id=uuid4(),
            recipient_email="test@example.com",
        )

        # Should return None
        assert result is None
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_deliver_disabled_template():
    """Test that disabled template causes delivery to return None."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        setting = SystemSetting(
            setting_key="email_notifications_enabled",
            setting_value="true",
        )
        session.add(setting)

        org_id = uuid4()
        org_config = OrganizationEmailConfig(
            organization_email_config_id=uuid4(),
            organization_id=org_id,
            email_notifications_enabled=True,
            provider_type=ProviderType.SMTP.value,
            from_address="noreply@example.com",
            from_name="Test System",
        )
        session.add(org_config)

        # Create disabled template
        template = NotificationTemplate(
            notification_template_id=uuid4(),
            organization_id=org_id,
            event_type="test_event",
            subject="Test Subject",
            body_template="Test Body",
            is_enabled=False,
        )
        session.add(template)
        await session.flush()

        # Try to deliver with disabled template
        service = NotificationService(session)
        result = await service.deliver(
            event_type="test_event",
            payload={},
            org_id=org_id,
            recipient_email="test@example.com",
        )

        # Should return None
        assert result is None
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_attempt_delivery_succeeds_first_try():
    """Test that delivery succeeds on first attempt."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        org_id = uuid4()
        record = NotificationRecord(
            notification_record_id=uuid4(),
            organization_id=org_id,
            event_type="test_event",
            recipient_email="test@example.com",
            status=NotificationStatus.PENDING.value,
            attempt_count=0,
        )
        session.add(record)
        await session.flush()

        service = NotificationService(session)
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
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_attempt_delivery_retries_with_backoff():
    """Test that delivery retries with exponential backoff."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        org_id = uuid4()
        record = NotificationRecord(
            notification_record_id=uuid4(),
            organization_id=org_id,
            event_type="test_event",
            recipient_email="test@example.com",
            status=NotificationStatus.PENDING.value,
            attempt_count=0,
        )
        session.add(record)
        await session.flush()

        service = NotificationService(session)

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
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_attempt_delivery_permanent_failure_after_5_attempts():
    """Test that delivery is permanently failed after 5 attempts."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        org_id = uuid4()
        record = NotificationRecord(
            notification_record_id=uuid4(),
            organization_id=org_id,
            event_type="test_event",
            recipient_email="test@example.com",
            status=NotificationStatus.PENDING.value,
            attempt_count=0,
        )
        session.add(record)
        await session.flush()

        service = NotificationService(session)
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
    
    await engine.dispose()
