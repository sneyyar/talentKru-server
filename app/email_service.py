"""
Email service for sending transactional emails.

Provides:
- EmailService: Abstraction for email dispatch
- send_email: Helper function for sending emails

This is a stub implementation that logs emails instead of actually sending them.
In production, this would integrate with SendGrid, AWS SES, or similar.
"""

import structlog
from typing import Optional

logger = structlog.get_logger(__name__)


class EmailService:
    """Email service for sending transactional emails."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            html_body: Optional HTML email body

        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Stub implementation: log the email instead of sending
            logger.info(
                "email_sent",
                to_email=to_email,
                subject=subject,
                body_preview=body[:100],
            )
            return True
        except Exception as e:
            logger.error(
                "email_send_failed",
                to_email=to_email,
                subject=subject,
                error=str(e),
            )
            return False


# Global email service instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
