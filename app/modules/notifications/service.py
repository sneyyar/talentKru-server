"""
Notification service for interview workflow events.

Implements two-level notification switch (global + org-level), template resolution
with locale fallback, exponential backoff retry with up to 5 attempts, and 24-hour
reminder scheduling for interview slots.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10
"""

import asyncio
import re
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crypto import decrypt_field
from app.modules.notifications.models import NotificationTemplate, NotificationRecord, NotificationStatus
from app.modules.email_config.models import OrganizationEmailConfig, SystemSetting
from app.modules.slots.models import InterviewSlot, SlotStatus, InvitationStatus
from app.modules.notifications.email_delivery import EmailDeliveryService
from app.observability.logging import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Delivers notifications with retry logic and template rendering."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailDeliveryService(db)

    async def deliver(
        self,
        event_type: str,
        payload: dict,
        org_id: UUID,
        recipient_email: str,
        locale: str | None = None,
        use_survey_template: bool = False,
    ) -> NotificationRecord | None:
        """
        Deliver a notification email with retry logic.

        Flow:
        1. Check global email_notifications_enabled system setting
        2. Check organization email_notifications_enabled config
        3. Resolve template (locale-specific then org-default fallback)
           - If use_survey_template=True, try SurveyFeedbackTemplate first, then fall back to NotificationTemplate
        4. Check if template is disabled
        5. Render subject and body from template
        6. Insert NotificationRecord (status=PENDING)
        7. Call _attempt_delivery (retries up to 5 times)

        Args:
            event_type: Type of event (e.g., "journey_stage_changed", "interview_reminder")
            payload: Event payload dict with template variables
            org_id: Organization ID
            recipient_email: Recipient email address
            locale: Optional locale code for locale-specific template variant (e.g., "en_US")
            use_survey_template: If True, try SurveyFeedbackTemplate before NotificationTemplate (Requirement 9.17)

        Returns:
            NotificationRecord if delivery attempted, None if skipped due to disabled settings

        Requirements: 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 9.17
        """
        # Check global system setting first
        if not await self._is_delivery_enabled_global():
            logger.info(
                "email_delivery_skipped_global",
                event_type=event_type,
                org_id=str(org_id),
            )
            return None

        # Check organization setting
        if not await self._is_delivery_enabled_org(org_id):
            logger.info(
                "email_delivery_skipped_org",
                event_type=event_type,
                org_id=str(org_id),
            )
            return None

        # Resolve template with locale fallback
        template = await self._resolve_template(event_type, org_id, locale, use_survey_template=use_survey_template)
        if not template:
            logger.info(
                "notification_template_not_found",
                event_type=event_type,
                org_id=str(org_id),
                locale=locale,
            )
            return None

        # Check if template is disabled
        if not template.is_enabled:
            logger.info(
                "notification_template_disabled",
                template_id=str(getattr(template, 'notification_template_id', None) or getattr(template, 'survey_feedback_template_id', None)),
                event_type=event_type,
            )
            return None

        # Render subject and body
        subject = self._render(template.subject, payload)
        body = self._render(template.body_template, payload)

        # Create notification record
        record = NotificationRecord(
            organization_id=org_id,
            event_type=event_type,
            recipient_email=recipient_email,
            status=NotificationStatus.PENDING.value,
            attempt_count=0,
        )
        self.db.add(record)
        await self.db.flush()

        logger.info(
            "notification_record_created",
            record_id=str(record.notification_record_id),
            event_type=event_type,
            recipient=recipient_email,
        )

        # Attempt delivery with retries
        await self._attempt_delivery(record, org_id, recipient_email, subject, body)

        return record

    async def _is_delivery_enabled_global(self) -> bool:
        """Check global email_notifications_enabled system setting."""
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.setting_key == "email_notifications_enabled"
            )
        )
        setting = result.scalar_one_or_none()
        if setting is None:
            # Default to true if not set
            return True
        return setting.setting_value.lower() == "true"

    async def _is_delivery_enabled_org(self, org_id: UUID) -> bool:
        """Check organization email_notifications_enabled config."""
        result = await self.db.execute(
            select(OrganizationEmailConfig).where(
                OrganizationEmailConfig.organization_id == org_id,
                OrganizationEmailConfig.deleted_at.is_(None),
            )
        )
        config = result.scalar_one_or_none()
        if config is None:
            # Default to true if not configured
            return True
        return config.email_notifications_enabled

    async def _resolve_template(
        self,
        event_type: str,
        org_id: UUID,
        locale: str | None = None,
        use_survey_template: bool = False,
    ) -> NotificationTemplate | None:
        """
        Resolve template with locale fallback.

        If use_survey_template=True:
        1. Try SurveyFeedbackTemplate with matching template_type (Requirement 9.17)
        2. Fall back to NotificationTemplate

        Otherwise:
        - Try locale-specific NotificationTemplate, then falls back to org-default (no locale)

        Args:
            event_type: Event type (survey_invitation, survey_reminder, etc.)
            org_id: Organization ID
            locale: Optional locale code
            use_survey_template: If True, try SurveyFeedbackTemplate first (Requirement 9.17)

        Returns:
            Template object if found, None otherwise
        """
        if use_survey_template:
            # Try SurveyFeedbackTemplate first (Requirement 9.17)
            from app.modules.surveys.models import SurveyFeedbackTemplate, SurveyTemplateType

            # Map event_type to SurveyTemplateType
            template_type_map = {
                "survey_invitation": SurveyTemplateType.INITIAL_SURVEY_INVITATION,
                "survey_reminder": SurveyTemplateType.SURVEY_REMINDER,
            }
            template_type = template_type_map.get(event_type)

            if template_type:
                result = await self.db.execute(
                    select(SurveyFeedbackTemplate).where(
                        SurveyFeedbackTemplate.organization_id == org_id,
                        SurveyFeedbackTemplate.template_type == template_type,
                        SurveyFeedbackTemplate.deleted_at.is_(None),
                    )
                )
                survey_template = result.scalar_one_or_none()
                if survey_template:
                    return survey_template

        # Fall back to NotificationTemplate (or direct lookup if not using survey template)
        # Try locale-specific template first if locale provided
        if locale:
            result = await self.db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.organization_id == org_id,
                    NotificationTemplate.event_type == event_type,
                    NotificationTemplate.locale == locale,
                    NotificationTemplate.deleted_at.is_(None),
                )
            )
            template = result.scalar_one_or_none()
            if template:
                return template

        # Fall back to org-default (no locale)
        result = await self.db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.organization_id == org_id,
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.locale.is_(None),
                NotificationTemplate.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    def _render(self, template: str, payload: dict) -> str:
        """
        Render template by replacing {{variable}} placeholders with payload values.

        Uses regex to find all {{variable}} patterns and replaces with payload values.
        Unknown variables are left as-is.

        Args:
            template: Template string with {{variable}} placeholders
            payload: Dict of variable -> value mappings

        Returns:
            Rendered string with placeholders replaced
        """

        def replace_placeholder(match):
            var_name = match.group(1)
            return str(payload.get(var_name, match.group(0)))

        return re.sub(r'\{\{(\w+)\}\}', replace_placeholder, template)

    async def _attempt_delivery(
        self,
        record: NotificationRecord,
        org_id: UUID,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        """
        Attempt to deliver email with exponential backoff retry.

        Loops attempts 1-5:
        - Call EmailDeliveryService.send
        - On success: set status=DELIVERED, delivered_at=now(), flush, return
        - On exception: log WARNING with attempt count
        - If attempt < 5: set status=RETRYING, flush, sleep(60 * 2^(attempt-1))
        - After 5 failures: set status=PERMANENTLY_FAILED, flush, log ERROR

        Requirements: 8.9, 8.10
        """
        for attempt in range(1, 6):
            try:
                await self.email_service.send(
                    org_id=org_id,
                    recipient_email=recipient_email,
                    subject=subject,
                    body_html=body,
                    body_text=None,
                )
                # Success
                record.status = NotificationStatus.DELIVERED.value
                record.delivered_at = datetime.now(timezone.utc)
                await self.db.flush()
                logger.info(
                    "notification_delivered",
                    record_id=str(record.notification_record_id),
                    recipient=recipient_email,
                    attempt=attempt,
                )
                return
            except Exception as exc:
                logger.warning(
                    "notification_delivery_failed",
                    record_id=str(record.notification_record_id),
                    recipient=recipient_email,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < 5:
                    record.status = NotificationStatus.RETRYING.value
                    record.attempt_count = attempt
                    await self.db.flush()
                    # Exponential backoff: 60 * 2^(attempt-1) seconds
                    backoff_seconds = 60 * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff_seconds)
                else:
                    # Final attempt failed
                    record.status = NotificationStatus.PERMANENTLY_FAILED.value
                    record.attempt_count = attempt
                    await self.db.flush()
                    logger.error(
                        "notification_permanently_failed",
                        record_id=str(record.notification_record_id),
                        recipient=recipient_email,
                        attempts=attempt,
                    )

    async def send_24h_reminder(self, slot_id: UUID, org_id: UUID) -> None:
        """
        Send 24-hour reminder for interview slot if conditions met.

        Conditions:
        - Slot status is SCHEDULED
        - Invitation status is PENDING or ACCEPTED
        - Current time is within 24 hours before scheduled_start

        Flow:
        - Fetch slot
        - Check conditions (skip if not met)
        - Decrypt interviewer email
        - Call deliver("interview_reminder", ...)

        Args:
            slot_id: Interview slot ID
            org_id: Organization ID

        Requirements: 8.5
        """
        # Fetch slot
        result = await self.db.execute(
            select(InterviewSlot).where(
                InterviewSlot.interview_slot_id == slot_id,
                InterviewSlot.organization_id == org_id,
                InterviewSlot.deleted_at.is_(None),
            )
        )
        slot = result.scalar_one_or_none()
        if not slot:
            logger.warning(
                "interview_slot_not_found_for_reminder",
                slot_id=str(slot_id),
                org_id=str(org_id),
            )
            return

        # Check slot status
        if slot.status != SlotStatus.SCHEDULED.value:
            logger.info(
                "interview_reminder_skipped_not_scheduled",
                slot_id=str(slot_id),
                status=slot.status,
            )
            return

        # Check invitation status
        if slot.invitation_status not in {InvitationStatus.PENDING.value, InvitationStatus.ACCEPTED.value}:
            logger.info(
                "interview_reminder_skipped_invitation_status",
                slot_id=str(slot_id),
                invitation_status=slot.invitation_status,
            )
            return

        # Check if now is within 24 hours before scheduled_start
        now = datetime.now(timezone.utc)
        time_until_start = slot.scheduled_start - now
        if time_until_start.total_seconds() > 24 * 3600:
            logger.info(
                "interview_reminder_skipped_too_early",
                slot_id=str(slot_id),
                hours_until_start=time_until_start.total_seconds() / 3600,
            )
            return

        if time_until_start.total_seconds() < 0:
            logger.info(
                "interview_reminder_skipped_already_started",
                slot_id=str(slot_id),
            )
            return

        # Get interviewer user from dependencies or auth context
        # For now, we'll use a placeholder - in real implementation this would come from the request
        interviewer_user_id = slot.interviewer_user_id
        if not interviewer_user_id:
            logger.warning(
                "interview_reminder_skipped_no_interviewer",
                slot_id=str(slot_id),
            )
            return

        # TODO: Get interviewer email from users module/table
        # This is a placeholder - the actual implementation would fetch from the users table
        interviewer_email = "interviewer@example.com"  # Placeholder

        # Create payload
        payload = {
            "slot_id": str(slot.interview_slot_id),
            "scheduled_start": slot.scheduled_start.isoformat(),
            "scheduled_end": slot.scheduled_end.isoformat(),
            "timezone": slot.timezone,
            "slot_type": slot.type,
        }

        await self.deliver(
            event_type="interview_reminder",
            payload=payload,
            org_id=org_id,
            recipient_email=interviewer_email,
            locale=None,
        )
