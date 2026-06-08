"""
Tests for EmailConfigService.

Feature: interview-workflow
Requirements: 6.1, 6.2, 6.5, 6.6, 6.7, 6.8
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.modules.email_config.service import EmailConfigService
from app.crypto import decrypt_field


class TestEmailConfigService:
    """Tests for EmailConfigService."""

    @pytest.mark.asyncio
    async def test_create_smtp_config(self, db_session: AsyncSession, test_run_id):
        """Test creating SMTP email config with all required fields."""
        service = EmailConfigService(db_session)
        org_id = uuid4()
        
        config = await service.create_or_update_config(
            org_id=org_id,
            provider_type="SMTP",
            smtp_host=f"smtp.example-{test_run_id}.com",
            smtp_port=587,
            smtp_username=f"user-{test_run_id}@example.com",
            smtp_password=f"password-{test_run_id}",
            from_address=f"noreply-{test_run_id}@example.com",
            from_name=f"Test Org",
        )
        
        assert config.organization_email_config_id is not None
        assert config.organization_id == org_id
        assert config.provider_type == "SMTP"
        # Password should be encrypted
        assert config.smtp_password != f"password-{test_run_id}"
        decrypted = decrypt_field(config.smtp_password)
        assert decrypted == f"password-{test_run_id}"

    @pytest.mark.asyncio
    async def test_create_sendgrid_config(self, db_session: AsyncSession, test_run_id):
        """Test creating SendGrid email config."""
        service = EmailConfigService(db_session)
        org_id = uuid4()
        
        config = await service.create_or_update_config(
            org_id=org_id,
            provider_type="SENDGRID",
            third_party_api_key=f"sg_key_{test_run_id}",
            from_address=f"noreply-{test_run_id}@example.com",
            from_name="Test",
        )
        
        assert config.provider_type == "SENDGRID"
        assert config.third_party_api_key != f"sg_key_{test_run_id}"
        decrypted = decrypt_field(config.third_party_api_key)
        assert decrypted == f"sg_key_{test_run_id}"

    @pytest.mark.asyncio
    async def test_smtp_missing_host_error(self, db_session: AsyncSession, test_run_id):
        """Test that missing smtp_host raises 422 error."""
        service = EmailConfigService(db_session)
        org_id = uuid4()
        
        with pytest.raises(HTTPException) as exc:
            await service.create_or_update_config(
                org_id=org_id,
                provider_type="SMTP",
                smtp_port=587,
                smtp_username="user@example.com",
                smtp_password="password",
                from_address="noreply@example.com",
                from_name="Test",
            )
        
        assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "smtp_host" in exc.value.detail

    @pytest.mark.asyncio
    async def test_sendgrid_missing_api_key_error(self, db_session: AsyncSession):
        """Test that missing API key for SendGrid raises 422 error."""
        service = EmailConfigService(db_session)
        org_id = uuid4()
        
        with pytest.raises(HTTPException) as exc:
            await service.create_or_update_config(
                org_id=org_id,
                provider_type="SENDGRID",
                from_address="noreply@example.com",
                from_name="Test",
            )
        
        assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "third_party_api_key" in exc.value.detail

    @pytest.mark.asyncio
    async def test_update_existing_config(self, db_session: AsyncSession, test_run_id):
        """Test updating an existing config."""
        service = EmailConfigService(db_session)
        org_id = uuid4()
        
        # Create
        config1 = await service.create_or_update_config(
            org_id=org_id,
            provider_type="SMTP",
            smtp_host="smtp1.example.com",
            smtp_port=587,
            smtp_username="user1@example.com",
            smtp_password="pass1",
            from_address="noreply@example.com",
            from_name="Test",
        )
        
        # Update same org
        config2 = await service.create_or_update_config(
            org_id=org_id,
            provider_type="SMTP",
            smtp_host="smtp2.example.com",
            smtp_port=465,
            smtp_username="user2@example.com",
            smtp_password="pass2",
            from_address="noreply@example.com",
            from_name="Test",
        )
        
        # Should be same ID (upsert)
        assert config2.organization_email_config_id == config1.organization_email_config_id
        assert config2.smtp_host == "smtp2.example.com"

    @pytest.mark.asyncio
    async def test_get_config(self, db_session: AsyncSession, test_run_id):
        """Test retrieving email config."""
        service = EmailConfigService(db_session)
        org_id = uuid4()
        
        created = await service.create_or_update_config(
            org_id=org_id,
            provider_type="SMTP",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="password",
            from_address="noreply@example.com",
            from_name="Test",
        )
        
        retrieved = await service.get_config(org_id)
        
        assert retrieved is not None
        assert retrieved.organization_email_config_id == created.organization_email_config_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_config(self, db_session: AsyncSession):
        """Test that getting nonexistent config returns None."""
        service = EmailConfigService(db_session)
        
        config = await service.get_config(uuid4())
        assert config is None

    @pytest.mark.asyncio
    async def test_update_global_setting_true(self, db_session: AsyncSession):
        """Test updating global setting to true."""
        service = EmailConfigService(db_session)
        
        setting = await service.update_global_setting(
            setting_key="email_notifications_enabled",
            setting_value="true",
        )
        
        assert setting.setting_value == "true"

    @pytest.mark.asyncio
    async def test_update_global_setting_false(self, db_session: AsyncSession):
        """Test updating global setting to false."""
        service = EmailConfigService(db_session)
        
        setting = await service.update_global_setting(
            setting_key="email_notifications_enabled",
            setting_value="false",
        )
        
        assert setting.setting_value == "false"

    @pytest.mark.asyncio
    async def test_invalid_boolean_value_error(self, db_session: AsyncSession):
        """Test that invalid boolean value raises 422 error."""
        service = EmailConfigService(db_session)
        
        with pytest.raises(HTTPException) as exc:
            await service.update_global_setting(
                setting_key="email_notifications_enabled",
                setting_value="invalid",
            )
        
        assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_global_setting(self, db_session: AsyncSession):
        """Test retrieving global setting."""
        service = EmailConfigService(db_session)
        
        created = await service.update_global_setting(
            setting_key="email_notifications_enabled",
            setting_value="true",
        )
        
        retrieved = await service.get_global_setting("email_notifications_enabled")
        
        assert retrieved is not None
        assert retrieved.setting_value == "true"

    @pytest.mark.asyncio
    async def test_get_nonexistent_setting(self, db_session: AsyncSession):
        """Test that getting nonexistent setting returns None."""
        service = EmailConfigService(db_session)
        
        setting = await service.get_global_setting("nonexistent_key")
        assert setting is None
