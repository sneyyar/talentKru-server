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

from app.modules.notifications.email_delivery import EmailDeliveryService
from app.crypto import encrypt_field

# ProviderType and OrganizationEmailConfig are only used as mock specs
# to avoid table redefinition issues when tests are run together
ProviderType = None  # Will be patched in tests


class TestEmailDeliveryServiceSMTP:
    """Tests for SMTP email delivery."""

    @pytest.mark.asyncio
    async def test_send_via_smtp_organization_config(self):
        """Test sending email via organization SMTP configuration."""
        service = EmailDeliveryService()
        
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
        body = "<h1>Test</h1>"

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            await service._send_smtp(to, subject, body, org_config)
            
            # Verify SMTP connection
            mock_smtp.assert_called_once_with("smtp.example.com", 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@example.com", "test_password")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_via_smtp_with_default_config(self):
        """Test sending email via default SMTP from environment variables."""
        service = EmailDeliveryService()
        
        to = "recipient@example.com"
        subject = "Test Email"
        body = "<h1>Test</h1>"

        with patch.object(service, '_send_smtp_default', new_callable=AsyncMock) as mock_default:
            await service.send(to, subject, body, org_config=None)
            mock_default.assert_called_once_with(to, subject, body)

    @pytest.mark.asyncio
    async def test_send_smtp_missing_credentials(self):
        """Test that SMTP delivery fails with missing credentials."""
        service = EmailDeliveryService()
        
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
        body = "<h1>Test</h1>"

        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await service._send_smtp(to, subject, body, org_config)
        
        assert exc_info.value.status_code == 500
        assert "incomplete" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_send_smtp_decrypts_password(self):
        """Test that SMTP password is properly decrypted."""
        service = EmailDeliveryService()
        
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
            
            await service._send_smtp(
                "test@example.com",
                "Test",
                "<p>Test</p>",
                org_config,
            )
            
            # Verify that the decrypted password (not the encrypted version) was used
            login_call = mock_server.login.call_args
            assert login_call[0][1] == test_password  # Second arg is password


class TestEmailDeliveryServiceSendGrid:
    """Tests for SendGrid email delivery."""

    @pytest.mark.asyncio
    async def test_send_via_sendgrid(self):
        """Test sending email via SendGrid."""
        service = EmailDeliveryService()
        
        api_key = "sg.test_api_key_123"
        encrypted_api_key = encrypt_field(api_key)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        org_config.third_party_api_key = encrypted_api_key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        to = "recipient@example.com"
        subject = "Test Email"
        body = "<h1>Test</h1>"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            await service._send_sendgrid(to, subject, body, org_config)
            
            # Verify API call
            call_args = mock_client.post.call_args
            assert call_args[1]["url"] == "https://api.sendgrid.com/v3/mail/send"
            assert f"Bearer {api_key}" in call_args[1]["headers"]["Authorization"]

    @pytest.mark.asyncio
    async def test_send_sendgrid_missing_api_key(self):
        """Test that SendGrid delivery fails with missing API key."""
        service = EmailDeliveryService()
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        org_config.third_party_api_key = None  # Missing API key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await service._send_sendgrid("test@example.com", "Test", "<p>Test</p>", org_config)
        
        assert exc_info.value.status_code == 500
        assert "not configured" in exc_info.value.detail.lower()


class TestEmailDeliveryServiceSES:
    """Tests for AWS SES email delivery."""

    @pytest.mark.asyncio
    async def test_send_via_ses(self):
        """Test sending email via AWS SES."""
        service = EmailDeliveryService()
        
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
        body = "<h1>Test</h1>"

        with patch("boto3.client") as mock_boto3:
            mock_ses = MagicMock()
            mock_boto3.return_value = mock_ses
            
            await service._send_ses(to, subject, body, org_config)
            
            # Verify boto3 client creation
            mock_boto3.assert_called_once_with("ses", region_name="us-east-1")
            
            # Verify send_email call
            mock_ses.send_email.assert_called_once()
            call_kwargs = mock_ses.send_email.call_args[1]
            assert call_kwargs["Source"] == "noreply@talentkru.ai"
            assert call_kwargs["Destination"]["ToAddresses"] == [to]
            assert call_kwargs["Message"]["Subject"]["Data"] == subject

    @pytest.mark.asyncio
    async def test_send_ses_missing_api_key(self):
        """Test that SES delivery fails with missing API key."""
        service = EmailDeliveryService()
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SES.value
        org_config.third_party_api_key = None  # Missing API key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await service._send_ses("test@example.com", "Test", "<p>Test</p>", org_config)
        
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_send_ses_with_default_region(self):
        """Test SES delivery uses default region when not specified."""
        service = EmailDeliveryService()
        
        api_key = "AKIAIOSFODNN7EXAMPLE"
        encrypted_api_key = encrypt_field(api_key)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SES.value
        org_config.third_party_api_key = encrypted_api_key
        org_config.third_party_provider_region = None  # No region specified
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        with patch("boto3.client") as mock_boto3:
            mock_ses = MagicMock()
            mock_boto3.return_value = mock_ses
            
            await service._send_ses("test@example.com", "Test", "<p>Test</p>", org_config)
            
            # Verify default region
            mock_boto3.assert_called_once_with("ses", region_name="us-east-1")


class TestEmailDeliveryServiceDispatch:
    """Tests for provider dispatch logic."""

    @pytest.mark.asyncio
    async def test_send_dispatches_to_correct_provider_smtp(self):
        """Test that send() dispatches to SMTP provider."""
        service = EmailDeliveryService()
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SMTP.value
        
        with patch.object(service, '_send_smtp', new_callable=AsyncMock) as mock_smtp:
            await service.send("test@example.com", "Test", "<p>Test</p>", org_config)
            mock_smtp.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_dispatches_to_correct_provider_sendgrid(self):
        """Test that send() dispatches to SendGrid provider."""
        service = EmailDeliveryService()
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        
        with patch.object(service, '_send_sendgrid', new_callable=AsyncMock) as mock_sg:
            await service.send("test@example.com", "Test", "<p>Test</p>", org_config)
            mock_sg.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_dispatches_to_correct_provider_ses(self):
        """Test that send() dispatches to SES provider."""
        service = EmailDeliveryService()
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SES.value
        
        with patch.object(service, '_send_ses', new_callable=AsyncMock) as mock_ses:
            await service.send("test@example.com", "Test", "<p>Test</p>", org_config)
            mock_ses.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_uses_defaults_when_no_org_config(self):
        """Test that send() uses default SMTP when no org config provided."""
        service = EmailDeliveryService()
        
        with patch.object(service, '_send_smtp_default', new_callable=AsyncMock) as mock_default:
            await service.send("test@example.com", "Test", "<p>Test</p>", org_config=None)
            mock_default.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_raises_on_unknown_provider(self):
        """Test that send() raises error on unknown provider type."""
        service = EmailDeliveryService()
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = "UNKNOWN_PROVIDER"
        
        with pytest.raises(Exception):  # ValueError wrapped or re-raised
            await service.send("test@example.com", "Test", "<p>Test</p>", org_config)


class TestEmailDeliveryServiceDefaultSMTP:
    """Tests for default SMTP fallback from environment variables."""

    @pytest.mark.asyncio
    async def test_send_smtp_default_with_valid_config(self):
        """Test default SMTP sends email with environment config."""
        service = EmailDeliveryService()
        
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
                
                await service._send_smtp_default(
                    "test@example.com",
                    "Test",
                    "<p>Test</p>",
                )
                
                mock_smtp.assert_called_once_with("smtp.example.com", 587)
                mock_server.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_smtp_default_missing_config(self):
        """Test default SMTP fails gracefully with missing environment config."""
        service = EmailDeliveryService()
        
        with patch("app.modules.notifications.email_delivery.settings") as mock_settings:
            mock_settings.SMTP_HOST = None
            mock_settings.SMTP_PORT = None
            mock_settings.SMTP_USERNAME = None
            mock_settings.SMTP_PASSWORD = None
            mock_settings.EMAIL_FROM_ADDRESS = None
            
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as exc_info:
                await service._send_smtp_default("test@example.com", "Test", "<p>Test</p>")
            
            assert exc_info.value.status_code == 500


class TestEmailDeliveryServiceErrorHandling:
    """Tests for error handling and logging."""

    @pytest.mark.asyncio
    async def test_send_logs_error_on_smtp_failure(self):
        """Test that SMTP delivery failures are logged."""
        service = EmailDeliveryService()
        
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
                await service.send("test@example.com", "Test", "<p>Test</p>", org_config)

    @pytest.mark.asyncio
    async def test_send_handles_http_errors_sendgrid(self):
        """Test that SendGrid HTTP errors are handled."""
        service = EmailDeliveryService()
        
        api_key = "sg.test_key"
        encrypted_api_key = encrypt_field(api_key)
        
        org_config = MagicMock(spec=OrganizationEmailConfig)
        org_config.provider_type = ProviderType.SENDGRID.value
        org_config.third_party_api_key = encrypted_api_key
        org_config.from_address = "noreply@talentkru.ai"
        org_config.from_name = "TalentKru"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.raise_for_status.side_effect = Exception("Unauthorized")
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            with pytest.raises(Exception):
                await service._send_sendgrid("test@example.com", "Test", "<p>Test</p>", org_config)
