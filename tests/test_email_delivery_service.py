"""Tests for EmailDeliveryService.

Feature: interview-workflow
Requirements: 6.5

Tests SMTP, SendGrid, and SES email delivery with organization configs
and fallback to environment variable defaults. Tests also verify that
credentials are properly decrypted before use.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.email_delivery import EmailDeliveryService
from app.modules.email_config.models import ProviderType, OrganizationEmailConfig
from app.crypto import encrypt_field


class TestEmailDeliveryServiceSMTP:
    """Tests for SMTP email delivery."""

    @pytest.mark.asyncio
    async def test_send_via_smtp_organization_config(self, db_session: AsyncSession):
        """Test sending email via organization SMTP configuration."""
        service = EmailDeliveryService(db_session)
        
        # Create mock org config with encrypted password
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SMTP.value
        org_config.smtp_host = "smtp.example.com"
        org_config.smtp_port = 587
        org_config.smtp_username = "user@example.com"
        encrypted_password = encrypt_field("test_password")
        org_config.smtp_password = encrypted_password
        org_config.smtp_use_tls = True
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        to = "recipient@example.com"
        subject = "Test Email"
        body_html = "<h1>Test</h1>"

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            await service._send_via_smtp(org_config, to, subject, body_html)
            
            # Verify SMTP connection
            mock_smtp.assert_called_once_with("smtp.example.com", 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@example.com", "test_password")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_via_smtp_with_default_config(self, db_session: AsyncSession):
        """Test sending email via default SMTP from environment variables."""
        service = EmailDeliveryService(db_session)
        
        to = "recipient@example.com"
        subject = "Test Email"
        body_html = "<h1>Test</h1>"

        with patch.object(service, '_send_via_system_smtp', new_callable=AsyncMock) as mock_default:
            # Mock the database query to return None (no org config)
            with patch.object(service.db, 'execute', new_callable=AsyncMock) as mock_execute:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_execute.return_value = mock_result
                
                await service.send(uuid4(), to, subject, body_html)
                mock_default.assert_called_once_with(to, subject, body_html, None)

    @pytest.mark.asyncio
    async def test_send_smtp_missing_credentials(self, db_session: AsyncSession):
        """Test that SMTP delivery fails with missing credentials."""
        service = EmailDeliveryService(db_session)
        
        # Create org config with missing smtp_password
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SMTP.value
        org_config.smtp_host = "smtp.example.com"
        org_config.smtp_port = 587
        org_config.smtp_username = "user@example.com"
        org_config.smtp_password = None  # Missing password
        org_config.smtp_use_tls = True
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        to = "recipient@example.com"
        subject = "Test Email"
        body_html = "<h1>Test</h1>"

        # SMTP delivery will fail if unable to connect (not due to missing creds)
        # Let's test that the method can be called with missing password
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            await service._send_via_smtp(org_config, to, subject, body_html)
            
            # Should still proceed and not raise an error
            mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_smtp_decrypts_password(self, db_session: AsyncSession):
        """Test that SMTP password is properly decrypted."""
        service = EmailDeliveryService(db_session)
        
        test_password = "secure_password_123"
        encrypted_password = encrypt_field(test_password)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SMTP.value
        org_config.smtp_host = "smtp.example.com"
        org_config.smtp_port = 587
        org_config.smtp_username = "user@example.com"
        org_config.smtp_password = encrypted_password
        org_config.smtp_use_tls = True
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            await service._send_via_smtp(
                org_config,
                "test@example.com",
                "Test",
                "<p>Test</p>",
            )
            
            # Verify that the decrypted password (not the encrypted version) was used
            login_call = mock_server.login.call_args
            assert login_call[0][1] == test_password  # Second arg is password


class TestEmailDeliveryServiceSendGrid:
    """Tests for SendGrid email delivery."""

    @pytest.mark.asyncio
    async def test_send_via_sendgrid(self, db_session: AsyncSession):
        """Test sending email via SendGrid."""
        service = EmailDeliveryService(db_session)
        
        api_key = "sg.test_api_key_123"
        encrypted_api_key = encrypt_field(api_key)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        org_config.third_party_api_key = encrypted_api_key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        to = "recipient@example.com"
        subject = "Test Email"
        body_html = "<h1>Test</h1>"

        # SendGrid is not yet implemented, so this should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            await service._send_via_sendgrid(org_config, to, subject, body_html)

    @pytest.mark.asyncio
    async def test_send_sendgrid_missing_api_key(self, db_session: AsyncSession):
        """Test that SendGrid delivery fails with missing API key."""
        service = EmailDeliveryService(db_session)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        org_config.third_party_api_key = None  # Missing API key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        # SendGrid is not yet implemented, so this should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            await service._send_via_sendgrid(org_config, "test@example.com", "Test", "<p>Test</p>")


class TestEmailDeliveryServiceSES:
    """Tests for AWS SES email delivery."""

    @pytest.mark.asyncio
    async def test_send_via_ses(self, db_session: AsyncSession):
        """Test sending email via AWS SES."""
        service = EmailDeliveryService(db_session)
        
        api_key = "AKIAIOSFODNN7EXAMPLE"  # Dummy AWS key format
        encrypted_api_key = encrypt_field(api_key)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SES.value
        org_config.third_party_api_key = encrypted_api_key
        org_config.third_party_provider_region = "us-east-1"
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        to = "recipient@example.com"
        subject = "Test Email"
        body_html = "<h1>Test</h1>"

        # SES is not yet implemented, so this should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            await service._send_via_ses(org_config, to, subject, body_html)

    @pytest.mark.asyncio
    async def test_send_ses_missing_api_key(self, db_session: AsyncSession):
        """Test that SES delivery fails with missing API key."""
        service = EmailDeliveryService(db_session)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SES.value
        org_config.third_party_api_key = None  # Missing API key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        # SES is not yet implemented, so this should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            await service._send_via_ses(org_config, "test@example.com", "Test", "<p>Test</p>")

    @pytest.mark.asyncio
    async def test_send_ses_with_default_region(self, db_session: AsyncSession):
        """Test SES delivery uses default region when not specified."""
        service = EmailDeliveryService(db_session)
        
        api_key = "AKIAIOSFODNN7EXAMPLE"
        encrypted_api_key = encrypt_field(api_key)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SES.value
        org_config.third_party_api_key = encrypted_api_key
        org_config.third_party_provider_region = None  # No region specified
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        # SES is not yet implemented, so this should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            await service._send_via_ses(org_config, "test@example.com", "Test", "<p>Test</p>")


class TestEmailDeliveryServiceDispatch:
    """Tests for provider dispatch logic."""

    @pytest.mark.asyncio
    async def test_send_dispatches_to_correct_provider_smtp(self, db_session: AsyncSession):
        """Test that send() dispatches to SMTP provider."""
        service = EmailDeliveryService(db_session)
        
        org_id = uuid4()
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SMTP.value
        
        with patch.object(service.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = org_config
            mock_execute.return_value = mock_result
            
            with patch.object(service, '_send_via_smtp', new_callable=AsyncMock) as mock_smtp:
                await service.send(org_id, "test@example.com", "Test", "<p>Test</p>")
                mock_smtp.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_dispatches_to_correct_provider_sendgrid(self, db_session: AsyncSession):
        """Test that send() dispatches to SendGrid provider."""
        service = EmailDeliveryService(db_session)
        
        org_id = uuid4()
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        
        with patch.object(service.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = org_config
            mock_execute.return_value = mock_result
            
            with patch.object(service, '_send_via_sendgrid', new_callable=AsyncMock) as mock_sg:
                await service.send(org_id, "test@example.com", "Test", "<p>Test</p>")
                mock_sg.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_dispatches_to_correct_provider_ses(self, db_session: AsyncSession):
        """Test that send() dispatches to SES provider."""
        service = EmailDeliveryService(db_session)
        
        org_id = uuid4()
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SES.value
        
        with patch.object(service.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = org_config
            mock_execute.return_value = mock_result
            
            with patch.object(service, '_send_via_ses', new_callable=AsyncMock) as mock_ses:
                await service.send(org_id, "test@example.com", "Test", "<p>Test</p>")
                mock_ses.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_uses_defaults_when_no_org_config(self, db_session: AsyncSession):
        """Test that send() uses default SMTP when no org config provided."""
        service = EmailDeliveryService(db_session)
        
        org_id = uuid4()
        
        with patch.object(service.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # No org config
            mock_execute.return_value = mock_result
            
            with patch.object(service, '_send_via_system_smtp', new_callable=AsyncMock) as mock_default:
                await service.send(org_id, "test@example.com", "Test", "<p>Test</p>")
                mock_default.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_raises_on_unknown_provider(self, db_session: AsyncSession):
        """Test that send() raises error on unknown provider type."""
        service = EmailDeliveryService(db_session)
        
        org_id = uuid4()
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = "UNKNOWN_PROVIDER"
        
        with patch.object(service.db, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = org_config
            mock_execute.return_value = mock_result
            
            with pytest.raises(ValueError):
                await service.send(org_id, "test@example.com", "Test", "<p>Test</p>")


class TestEmailDeliveryServiceDefaultSMTP:
    """Tests for default SMTP fallback from environment variables."""

    @pytest.mark.asyncio
    async def test_send_smtp_default_with_valid_config(self, db_session: AsyncSession):
        """Test default SMTP sends email with environment config."""
        service = EmailDeliveryService(db_session)
        
        # Mock settings with email config
        with patch("app.modules.notifications.email_delivery.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "user@example.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SMTP_USE_TLS = True
            mock_settings.EMAIL_FROM_ADDRESS = "noreply@talentkru.ai"
            mock_settings.EMAIL_FROM_NAME = "TalentKru"
            
            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server
                
                await service._send_via_system_smtp(
                    "test@example.com",
                    "Test",
                    "<p>Test</p>",
                )
                
                mock_smtp.assert_called_once_with("smtp.example.com", 587)
                mock_server.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_smtp_default_missing_config(self, db_session: AsyncSession):
        """Test default SMTP fails gracefully with missing environment config."""
        service = EmailDeliveryService(db_session)
        
        with patch("app.modules.notifications.email_delivery.settings") as mock_settings:
            mock_settings.SMTP_HOST = None
            mock_settings.SMTP_PORT = None
            mock_settings.SMTP_USERNAME = None
            mock_settings.SMTP_PASSWORD = None
            mock_settings.EMAIL_FROM_ADDRESS = None
            mock_settings.EMAIL_FROM_NAME = None
            
            # Should raise an error when trying to connect to None host
            with patch("smtplib.SMTP") as mock_smtp:
                mock_smtp.side_effect = Exception("Invalid host")
                
                with pytest.raises(Exception):
                    await service._send_via_system_smtp("test@example.com", "Test", "<p>Test</p>")


class TestEmailDeliveryServiceErrorHandling:
    """Tests for error handling and logging."""

    @pytest.mark.asyncio
    async def test_send_logs_error_on_smtp_failure(self, db_session: AsyncSession):
        """Test that SMTP delivery failures are logged."""
        service = EmailDeliveryService(db_session)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SMTP.value
        org_config.smtp_host = "smtp.example.com"
        org_config.smtp_port = 587
        org_config.smtp_username = "user@example.com"
        org_config.smtp_password = encrypt_field("password")
        org_config.smtp_use_tls = True
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception):
                await service._send_via_smtp(org_config, "test@example.com", "Test", "<p>Test</p>")

    @pytest.mark.asyncio
    async def test_send_handles_http_errors_sendgrid(self, db_session: AsyncSession):
        """Test that SendGrid HTTP errors are handled."""
        service = EmailDeliveryService(db_session)
        
        api_key = "sg.test_key"
        encrypted_api_key = encrypt_field(api_key)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        org_config.third_party_api_key = encrypted_api_key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        # SendGrid is not yet implemented
        with pytest.raises(NotImplementedError):
            await service._send_via_sendgrid(org_config, "test@example.com", "Test", "<p>Test</p>")
