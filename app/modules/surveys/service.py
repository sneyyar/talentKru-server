"""Candidate feedback survey service."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.decorators import transactional
from app.domain_events.publisher import publish_event
from app.modules.surveys.models import (
    CandidateFeedbackSurvey,
    CandidateFeedbackSurveyAnswer,
    CandidateFeedbackSurveyQuestion,
    CandidateFeedbackSurveyResponse,
    CandidateFeedbackSurveyToken,
    SurveyStatus,
    SurveyFeedbackTemplate,
    SurveyTemplateType,
)
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Survey token TTL: 30 days
SURVEY_EXPIRY_DAYS = 30
# Reminder trigger: 7 days
REMINDER_TRIGGER_DAYS = 7


class CandidateFeedbackSurveyService:
    """Service for managing candidate feedback surveys."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @transactional(name="create_survey_for_journey")
    async def create_survey_for_journey(
        self,
        journey_id: UUID,
        candidate_id: UUID,
        org_id: UUID,
        background_tasks=None,
    ) -> tuple[CandidateFeedbackSurvey, str]:
        """
        Create a survey for a journey (skip if already exists).

        Generates token with ≥43 URL-safe chars, computes SHA-256 hash,
        sets expires_at to now + 30 days, inserts survey and token,
        updates survey status to SENT, publishes survey_created event.

        Requirements: 9.1, 9.2, 9.7, 9.8
        """
        # Check if survey already exists for this journey
        existing = await self.db.execute(
            select(CandidateFeedbackSurvey).where(
                CandidateFeedbackSurvey.interview_journey_id == journey_id,
                CandidateFeedbackSurvey.deleted_at.is_(None),
            )
        )
        existing_survey = existing.scalar_one_or_none()
        if existing_survey:
            logger.info("survey_already_exists", journey_id=str(journey_id))
            # Return dummy token for existing survey (not used, but provides a tuple)
            return existing_survey, ""

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=SURVEY_EXPIRY_DAYS)

        # Create survey with DRAFT status
        survey = CandidateFeedbackSurvey(
            candidate_feedback_survey_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=journey_id,
            candidate_id=candidate_id,
            status=SurveyStatus.DRAFT.value,
            created_at=now,
            expires_at=expires_at,
        )
        self.db.add(survey)
        await self.db.flush()

        # Generate token: secrets.token_urlsafe(32) gives ≥43 URL-safe chars
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Create token record (store both plaintext token and hash)
        token_record = CandidateFeedbackSurveyToken(
            candidate_feedback_survey_token_id=uuid4(),
            candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
            token=raw_token,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(token_record)
        await self.db.flush()

        # Update survey status to SENT and link token
        survey.status = SurveyStatus.SENT.value
        survey.survey_token_id = token_record.candidate_feedback_survey_token_id
        await self.db.flush()

        logger.info(
            "survey_created",
            survey_id=str(survey.candidate_feedback_survey_id),
            journey_id=str(journey_id),
        )

        # Publish event for notification delivery
        await publish_event(
            "survey_created",
            {
                "survey_id": str(survey.candidate_feedback_survey_id),
                "journey_id": str(journey_id),
                "candidate_id": str(candidate_id),
                "org_id": str(org_id),
            },
            self.db,
            background_tasks=background_tasks,
        )

        return survey, raw_token

    async def get_survey_by_token(self, token: str) -> tuple[CandidateFeedbackSurvey, list]:
        """
        Get survey and questions by token.

        Computes SHA-256 hash, queries for valid, active, non-expired token.
        Returns 401 if not found. Fetches survey; returns 410 if EXPIRED or
        COMPLETED. Else fetches and returns survey questions ordered by display_order.

        Requirements: 9.12, 9.13
        """
        now = datetime.now(timezone.utc)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Query token
        token_result = await self.db.execute(
            select(CandidateFeedbackSurveyToken).where(
                CandidateFeedbackSurveyToken.token_hash == token_hash,
                CandidateFeedbackSurveyToken.is_active.is_(True),
                CandidateFeedbackSurveyToken.expires_at > now,
                CandidateFeedbackSurveyToken.deleted_at.is_(None),
            )
        )
        token_record = token_result.scalar_one_or_none()

        if not token_record:
            logger.warning("survey_token_not_found", token_hash=token_hash[:8])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired survey link",
            )

        # Fetch survey
        survey_result = await self.db.execute(
            select(CandidateFeedbackSurvey).where(
                CandidateFeedbackSurvey.candidate_feedback_survey_id
                == token_record.candidate_feedback_survey_id,
                CandidateFeedbackSurvey.deleted_at.is_(None),
            )
        )
        survey = survey_result.scalar_one_or_none()

        if not survey:
            logger.error("survey_not_found", survey_id=str(token_record.candidate_feedback_survey_id))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired survey link",
            )

        # Check if survey is expired or completed
        if survey.status in (SurveyStatus.EXPIRED.value, SurveyStatus.COMPLETED.value):
            logger.info(
                "survey_no_longer_available",
                survey_id=str(survey.candidate_feedback_survey_id),
                status=survey.status,
            )
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Survey is no longer available",
            )

        # Fetch questions ordered by display_order
        questions_result = await self.db.execute(
            select(CandidateFeedbackSurveyQuestion)
            .where(
                CandidateFeedbackSurveyQuestion.organization_id == survey.organization_id,
                CandidateFeedbackSurveyQuestion.deleted_at.is_(None),
            )
            .order_by(CandidateFeedbackSurveyQuestion.display_order)
        )
        questions = questions_result.scalars().all()

        logger.info(
            "survey_retrieved",
            survey_id=str(survey.candidate_feedback_survey_id),
            n_questions=len(questions),
        )

        return survey, questions

    @transactional(name="submit_survey")
    async def submit_survey(
        self, token: str, answers: dict[str, int], additional_comments: str | None = None
    ) -> CandidateFeedbackSurveyResponse:
        """
        Submit survey responses.

        Validates token, rating values 0-10, additional_comments max 2000 chars.
        Creates CandidateFeedbackSurveyResponse and CandidateFeedbackSurveyAnswer records.
        Updates survey status to COMPLETED, sets token is_active to False.

        Requirements: 9.14, 9.15
        """
        # Validate token and get survey
        survey, questions = await self.get_survey_by_token(token)

        # Validate ratings
        for question_id_str, rating in answers.items():
            if not isinstance(rating, int) or rating < 0 or rating > 10:
                logger.warning(
                    "invalid_rating",
                    question_id=question_id_str,
                    rating=rating,
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Rating must be between 0 and 10. Got: {rating}",
                )

        # Validate additional_comments length
        if additional_comments and len(additional_comments) > 2000:
            logger.warning(
                "comments_too_long",
                length=len(additional_comments),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Additional comments must not exceed 2000 characters",
            )

        now = datetime.now(timezone.utc)

        # Check if already completed
        if survey.status == SurveyStatus.COMPLETED.value:
            logger.warning(
                "survey_already_completed",
                survey_id=str(survey.candidate_feedback_survey_id),
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This survey has already been completed and cannot be resubmitted.",
            )

        # Create response record
        response = CandidateFeedbackSurveyResponse(
            candidate_feedback_survey_response_id=uuid4(),
            candidate_feedback_survey_id=survey.candidate_feedback_survey_id,
            organization_id=survey.organization_id,
            additional_comments=additional_comments,
            created_at=now,
            updated_at=now,
        )
        self.db.add(response)
        await self.db.flush()

        # Create answer records for each question
        for question in questions:
            question_id_str = str(question.candidate_feedback_survey_question_id)
            rating = answers.get(question_id_str, 0)  # Default to 0 (N/A) if not provided

            answer = CandidateFeedbackSurveyAnswer(
                candidate_feedback_survey_answer_id=uuid4(),
                candidate_feedback_survey_response_id=response.candidate_feedback_survey_response_id,
                candidate_feedback_survey_question_id=question.candidate_feedback_survey_question_id,
                rating=rating,
            )
            self.db.add(answer)

        await self.db.flush()

        # Update survey status to COMPLETED
        survey.status = SurveyStatus.COMPLETED.value
        survey.completed_at = now
        await self.db.flush()

        # Deactivate token
        token_result = await self.db.execute(
            select(CandidateFeedbackSurveyToken).where(
                CandidateFeedbackSurveyToken.candidate_feedback_survey_id
                == survey.candidate_feedback_survey_id,
                CandidateFeedbackSurveyToken.deleted_at.is_(None),
            )
        )
        token_record = token_result.scalar_one_or_none()
        if token_record:
            token_record.is_active = False
            await self.db.flush()

        logger.info(
            "survey_submitted",
            survey_id=str(survey.candidate_feedback_survey_id),
            n_answers=len(answers),
        )

        return response

    @transactional(name="send_survey_reminder")
    async def send_reminder(self, survey_id: UUID, background_tasks=None) -> None:
        """
        Send reminder for survey that's been open 7+ days.

        Queries surveys with status=SENT, created 7+ days ago, no reminder sent.
        Updates first_reminder_sent_at, publishes survey_reminder event.

        Requirements: 9.10
        """
        survey = await self.db.get(CandidateFeedbackSurvey, survey_id)
        if not survey or survey.deleted_at:
            logger.warning("survey_not_found_for_reminder", survey_id=str(survey_id))
            return

        if survey.first_reminder_sent_at:
            logger.info("reminder_already_sent", survey_id=str(survey_id))
            return

        now = datetime.now(timezone.utc)
        survey.first_reminder_sent_at = now
        await self.db.flush()

        logger.info("survey_reminder_sent", survey_id=str(survey_id))

        # Publish reminder event
        await publish_event(
            "survey_reminder",
            {
                "survey_id": str(survey.candidate_feedback_survey_id),
                "journey_id": str(survey.interview_journey_id),
                "candidate_id": str(survey.candidate_id),
                "org_id": str(survey.organization_id),
            },
            self.db,
            background_tasks=background_tasks,
        )

    @transactional(name="expire_surveys")
    async def expire_surveys(self) -> None:
        """
        Expire surveys that have passed the 30-day mark.

        Queries surveys with status=SENT and expires_at <= now.
        Updates status to EXPIRED and deactivates related tokens.

        Requirements: 9.11
        """
        now = datetime.now(timezone.utc)

        # Find surveys to expire
        result = await self.db.execute(
            select(CandidateFeedbackSurvey).where(
                CandidateFeedbackSurvey.status == SurveyStatus.SENT.value,
                CandidateFeedbackSurvey.expires_at <= now,
                CandidateFeedbackSurvey.deleted_at.is_(None),
            )
        )
        surveys = result.scalars().all()

        for survey in surveys:
            survey.status = SurveyStatus.EXPIRED.value
            await self.db.flush()

            # Deactivate tokens
            token_result = await self.db.execute(
                select(CandidateFeedbackSurveyToken).where(
                    CandidateFeedbackSurveyToken.candidate_feedback_survey_id
                    == survey.candidate_feedback_survey_id,
                    CandidateFeedbackSurveyToken.is_active.is_(True),
                    CandidateFeedbackSurveyToken.deleted_at.is_(None),
                )
            )
            tokens = token_result.scalars().all()
            for token in tokens:
                token.is_active = False
            await self.db.flush()

        if surveys:
            logger.info("surveys_expired", count=len(surveys))

    async def get_survey_questions(self, org_id: UUID) -> list[CandidateFeedbackSurveyQuestion]:
        """
        Get survey questions for organization, ordered by display_order.

        Requirements: 9.3
        """
        result = await self.db.execute(
            select(CandidateFeedbackSurveyQuestion)
            .where(
                CandidateFeedbackSurveyQuestion.organization_id == org_id,
                CandidateFeedbackSurveyQuestion.deleted_at.is_(None),
            )
            .order_by(CandidateFeedbackSurveyQuestion.display_order)
        )
        return result.scalars().all()




class CandidateFeedbackSurveyTemplateService:
    """Service for managing survey feedback templates (Req 9.17, 9.18)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @transactional(name="create_survey_template")
    async def create_template(
        self,
        org_id: UUID,
        template_type: str,
        subject: str,
        body_template: str,
        is_enabled: bool = True,
    ) -> SurveyFeedbackTemplate:
        """
        Create a new survey feedback template (org-scoped).

        Validates template_type is one of the allowed enum values.
        Prevents duplicate templates per org via unique constraint.

        Requirements: 9.17
        """
        # Validate template_type
        valid_types = {t.value for t in SurveyTemplateType}
        if template_type not in valid_types:
            logger.warning(
                "invalid_template_type",
                template_type=template_type,
                valid_types=valid_types,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"template_type must be one of: {', '.join(valid_types)}",
            )

        # Validate subject length
        if not subject or len(subject) > 200:
            logger.warning(
                "invalid_subject_length",
                length=len(subject) if subject else 0,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="subject must be 1-200 characters",
            )

        # Validate body_template is not empty
        if not body_template:
            logger.warning("empty_body_template")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="body_template cannot be empty",
            )

        now = datetime.now(timezone.utc)
        template = SurveyFeedbackTemplate(
            survey_feedback_template_id=uuid4(),
            organization_id=org_id,
            template_type=template_type,
            subject=subject,
            body_template=body_template,
            is_enabled=is_enabled,
        )
        self.db.add(template)

        try:
            await self.db.flush()
        except IntegrityError as e:
            logger.warning(
                "duplicate_template",
                org_id=str(org_id),
                template_type=template_type,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template type '{template_type}' already exists for this organization",
            ) from e

        logger.info(
            "survey_template_created",
            template_id=str(template.survey_feedback_template_id),
            org_id=str(org_id),
            template_type=template_type,
        )

        return template

    async def get_template(
        self,
        org_id: UUID,
        template_type: str,
    ) -> SurveyFeedbackTemplate | None:
        """
        Get a survey template by org and template_type (org-scoped).

        Requirements: 9.17
        """
        result = await self.db.execute(
            select(SurveyFeedbackTemplate).where(
                SurveyFeedbackTemplate.organization_id == org_id,
                SurveyFeedbackTemplate.template_type == template_type,
                SurveyFeedbackTemplate.deleted_at.is_(None),
            )
        )
        template = result.scalar_one_or_none()

        if template:
            logger.info(
                "survey_template_retrieved",
                template_id=str(template.survey_feedback_template_id),
            )

        return template

    async def list_templates(self, org_id: UUID) -> list[SurveyFeedbackTemplate]:
        """
        List all survey templates for an organization (org-scoped).

        Requirements: 9.17
        """
        result = await self.db.execute(
            select(SurveyFeedbackTemplate).where(
                SurveyFeedbackTemplate.organization_id == org_id,
                SurveyFeedbackTemplate.deleted_at.is_(None),
            )
        )
        return result.scalars().all()

    @transactional(name="update_survey_template")
    async def update_template(
        self,
        org_id: UUID,
        template_id: UUID,
        subject: str | None = None,
        body_template: str | None = None,
        is_enabled: bool | None = None,
    ) -> SurveyFeedbackTemplate:
        """
        Update a survey feedback template (org-scoped).

        Validates subject length if provided. Org-scoped query ensures
        authorization.

        Requirements: 9.17
        """
        # Fetch template (org-scoped)
        result = await self.db.execute(
            select(SurveyFeedbackTemplate).where(
                SurveyFeedbackTemplate.survey_feedback_template_id == template_id,
                SurveyFeedbackTemplate.organization_id == org_id,
                SurveyFeedbackTemplate.deleted_at.is_(None),
            )
        )
        template = result.scalar_one_or_none()

        if not template:
            logger.warning(
                "template_not_found",
                template_id=str(template_id),
                org_id=str(org_id),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )

        # Validate and update fields
        if subject is not None:
            if not subject or len(subject) > 200:
                logger.warning(
                    "invalid_subject_length_update",
                    length=len(subject) if subject else 0,
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="subject must be 1-200 characters",
                )
            template.subject = subject

        if body_template is not None:
            if not body_template:
                logger.warning("empty_body_template_update")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="body_template cannot be empty",
                )
            template.body_template = body_template

        if is_enabled is not None:
            template.is_enabled = is_enabled

        await self.db.flush()

        logger.info(
            "survey_template_updated",
            template_id=str(template.survey_feedback_template_id),
            org_id=str(org_id),
        )

        return template

    @transactional(name="delete_survey_template")
    async def delete_template(self, org_id: UUID, template_id: UUID) -> None:
        """
        Soft delete a survey feedback template (org-scoped).

        Sets deleted_at timestamp, preserving the record for audit trail.

        Requirements: 9.17
        """
        # Fetch template (org-scoped)
        result = await self.db.execute(
            select(SurveyFeedbackTemplate).where(
                SurveyFeedbackTemplate.survey_feedback_template_id == template_id,
                SurveyFeedbackTemplate.organization_id == org_id,
                SurveyFeedbackTemplate.deleted_at.is_(None),
            )
        )
        template = result.scalar_one_or_none()

        if not template:
            logger.warning(
                "template_not_found_for_delete",
                template_id=str(template_id),
                org_id=str(org_id),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )

        # Soft delete
        template.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "survey_template_deleted",
            template_id=str(template.survey_feedback_template_id),
            org_id=str(org_id),
        )
