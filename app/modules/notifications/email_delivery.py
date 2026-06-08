"""
Email delivery service for notifications.

Sends emails using SMTP or third-party providers (SendGrid, SES).
Supports credential decryption and fallback to system-level SMTP defaults.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crypto import decrypt_field
from app.modules.email_config.models import OrganizationEmailConfig, ProviderType
from app.config import settings
from app.observability.logging import get_logger

logger = get_logger(__name__)


class EmailDeliveryService:
    """Delivers emails via SMTP or third-party providers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send(
        self,
        org_id: UUID,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        """
        Send email via SMTP or third-party provider.

        Args:
            org_id: Organization ID for credential lookup
            recipient_email: Recipient email address
            subject: Email subject line
            body_html: Email body in HTML format
            body_text: Email body in plain text format (optional)

        Raises:
            Exception: If email delivery fails

        Requirements: 6.5, 8.9
        """
        # Fetch org config or use system defaults
        result = await self.db.execute(
            select(OrganizationEmailConfig).where(
                OrganizationEmailConfig.organization_id == org_id,
                OrganizationEmailConfig.deleted_at.is_(None),
            )
        )
        org_config = result.scalar_one_or_none()

        if org_config:
            await self._send_via_provider(org_config, recipient_email, subject, body_html, body_text)
        else:
            # Fall back to system SMTP defaults
            await self._send_via_system_smtp(recipient_email, subject, body_html, body_text)

    async def _send_via_provider(
        self,
        org_config: OrganizationEmailConfig,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        """Send via org-configured provider."""
        if org_config.provider_type == ProviderType.SMTP.value:
            await self._send_via_smtp(org_config, recipient_email, subject, body_html, body_text)
        elif org_config.provider_type == ProviderType.SENDGRID.value:
            await self._send_via_sendgrid(org_config, recipient_email, subject, body_html, body_text)
        elif org_config.provider_type == ProviderType.SES.value:
            await self._send_via_ses(org_config, recipient_email, subject, body_html, body_text)
        else:
            raise ValueError(f"Unknown provider type: {org_config.provider_type}")

    async def _send_via_smtp(
        self,
        org_config: OrganizationEmailConfig,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        """Send via SMTP."""
        smtp_host = org_config.smtp_host
        smtp_port = org_config.smtp_port
        smtp_username = org_config.smtp_username
        smtp_password = decrypt_field(org_config.smtp_password) if org_config.smtp_password else None
        smtp_use_tls = org_config.smtp_use_tls or False
        from_address = org_config.from_address
        from_name = org_config.from_name

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_address}>"
        msg["To"] = recipient_email

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            if smtp_use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)

            server.sendmail(from_address, [recipient_email], msg.as_string())
            server.quit()
            logger.info("email_sent_via_smtp", recipient=recipient_email, subject=subject)
        except Exception as e:
            logger.error("smtp_send_failed", recipient=recipient_email, error=str(e))
            raise

    async def _send_via_system_smtp(
        self,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        """Send via system-level SMTP defaults."""
        smtp_host = settings.SMTP_HOST
        smtp_port = settings.SMTP_PORT
        smtp_username = settings.SMTP_USERNAME
        smtp_password = settings.SMTP_PASSWORD
        smtp_use_tls = settings.SMTP_USE_TLS
        from_address = settings.EMAIL_FROM_ADDRESS
        from_name = settings.EMAIL_FROM_NAME

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_address}>"
        msg["To"] = recipient_email

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            if smtp_use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)

            server.sendmail(from_address, [recipient_email], msg.as_string())
            server.quit()
            logger.info("email_sent_via_system_smtp", recipient=recipient_email, subject=subject)
        except Exception as e:
            logger.error("system_smtp_send_failed", recipient=recipient_email, error=str(e))
            raise

    async def _send_via_sendgrid(
        self,
        org_config: OrganizationEmailConfig,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        """Send via SendGrid API."""
        # This is a stub for SendGrid integration
        logger.info("sendgrid_not_implemented", recipient=recipient_email)
        raise NotImplementedError("SendGrid integration not yet implemented")

    async def _send_via_ses(
        self,
        org_config: OrganizationEmailConfig,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> None:
        """Send via AWS SES."""
        # This is a stub for SES integration
        logger.info("ses_not_implemented", recipient=recipient_email)
        raise NotImplementedError("SES integration not yet implemented")
