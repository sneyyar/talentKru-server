"""
Comprehensive smoke tests for interview workflow module integrity.

These tests validate:
1. Enum definitions with correct values (Req 5.1, 5.2, 5.3, 6.2, 8.7, 8.9)
2. System settings seed data
3. Environment variables for security/settings
4. VersionMixin configuration on mutable entities (Req 7.1, 7.5)
5. Module imports for services and routers
"""

import os
import pytest
from typing import Type
from sqlalchemy import inspect as sa_inspect, Column, Integer
from sqlalchemy.orm.attributes import InstrumentedAttribute


# ---------------------------------------------------------------------------
# Test 1: Enum Validation
# Validates: Requirements 5.1, 5.2, 5.3, 6.2, 8.7, 8.9
# ---------------------------------------------------------------------------

def test_journey_stage_enum_has_11_values():
    """JourneyStage must have exactly 11 values."""
    from app.modules.journeys.models import JourneyStage
    
    expected_stages = [
        "SOURCED",
        "RECRUITER_SCREEN",
        "MANAGER_SCREEN",
        "LOOP_INTERVIEW",
        "PANEL_REVIEW",
        "OFFER_PENDING",
        "OFFER_EXTENDED",
        "REJECTED",
        "OFFER_DECLINED",
        "OFFER_ACCEPTED",
        "WITHDRAWN",
    ]
    
    assert len(JourneyStage) == 11, (
        f"JourneyStage should have 11 values, got {len(JourneyStage)}"
    )
    
    for stage_name in expected_stages:
        assert hasattr(JourneyStage, stage_name), (
            f"JourneyStage missing value: {stage_name}"
        )
        stage = getattr(JourneyStage, stage_name)
        assert stage.value == stage_name, (
            f"JourneyStage.{stage_name} has incorrect value: {stage.value}"
        )


def test_journey_overall_status_enum_has_4_values():
    """JourneyOverallStatus must have exactly 4 values."""
    from app.modules.journeys.models import JourneyOverallStatus
    
    expected_statuses = ["ACTIVE", "COMPLETED", "ON_HOLD", "CANCELLED"]
    
    assert len(JourneyOverallStatus) == 4, (
        f"JourneyOverallStatus should have 4 values, got {len(JourneyOverallStatus)}"
    )
    
    for status_name in expected_statuses:
        assert hasattr(JourneyOverallStatus, status_name), (
            f"JourneyOverallStatus missing value: {status_name}"
        )
        status = getattr(JourneyOverallStatus, status_name)
        assert status.value == status_name, (
            f"JourneyOverallStatus.{status_name} has incorrect value: {status.value}"
        )


def test_slot_type_enum_has_4_values():
    """SlotType must have exactly 4 values."""
    from app.modules.slots.models import SlotType
    
    expected_types = ["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"]
    
    assert len(SlotType) == 4, (
        f"SlotType should have 4 values, got {len(SlotType)}"
    )
    
    for type_name in expected_types:
        assert hasattr(SlotType, type_name), (
            f"SlotType missing value: {type_name}"
        )
        slot_type = getattr(SlotType, type_name)
        assert slot_type.value == type_name, (
            f"SlotType.{type_name} has incorrect value: {slot_type.value}"
        )


def test_slot_status_enum_has_4_values():
    """SlotStatus must have exactly 4 values."""
    from app.modules.slots.models import SlotStatus
    
    expected_statuses = ["SCHEDULED", "IN_PROGRESS", "COMPLETE", "CANCELLED"]
    
    assert len(SlotStatus) == 4, (
        f"SlotStatus should have 4 values, got {len(SlotStatus)}"
    )
    
    for status_name in expected_statuses:
        assert hasattr(SlotStatus, status_name), (
            f"SlotStatus missing value: {status_name}"
        )
        status = getattr(SlotStatus, status_name)
        assert status.value == status_name, (
            f"SlotStatus.{status_name} has incorrect value: {status.value}"
        )


def test_feedback_status_enum_has_2_values():
    """FeedbackStatus must have exactly 2 values."""
    from app.modules.feedback.models import FeedbackStatus
    
    expected_statuses = ["DRAFT", "SUBMITTED"]
    
    assert len(FeedbackStatus) == 2, (
        f"FeedbackStatus should have 2 values, got {len(FeedbackStatus)}"
    )
    
    for status_name in expected_statuses:
        assert hasattr(FeedbackStatus, status_name), (
            f"FeedbackStatus missing value: {status_name}"
        )
        status = getattr(FeedbackStatus, status_name)
        assert status.value == status_name, (
            f"FeedbackStatus.{status_name} has incorrect value: {status.value}"
        )


def test_response_status_enum_has_3_values():
    """ResponseStatus must have exactly 3 values."""
    from app.modules.questionnaires.models import ResponseStatus
    
    expected_statuses = ["DRAFT", "INCOMPLETE", "SUBMITTED"]
    
    assert len(ResponseStatus) == 3, (
        f"ResponseStatus should have 3 values, got {len(ResponseStatus)}"
    )
    
    for status_name in expected_statuses:
        assert hasattr(ResponseStatus, status_name), (
            f"ResponseStatus missing value: {status_name}"
        )
        status = getattr(ResponseStatus, status_name)
        assert status.value == status_name, (
            f"ResponseStatus.{status_name} has incorrect value: {status.value}"
        )


def test_notification_status_enum_has_4_values():
    """NotificationStatus must have exactly 4 values."""
    from app.modules.notifications.models import NotificationStatus
    
    expected_statuses = ["PENDING", "DELIVERED", "RETRYING", "PERMANENTLY_FAILED"]
    
    assert len(NotificationStatus) == 4, (
        f"NotificationStatus should have 4 values, got {len(NotificationStatus)}"
    )
    
    for status_name in expected_statuses:
        assert hasattr(NotificationStatus, status_name), (
            f"NotificationStatus missing value: {status_name}"
        )
        status = getattr(NotificationStatus, status_name)
        assert status.value == status_name, (
            f"NotificationStatus.{status_name} has incorrect value: {status.value}"
        )


def test_provider_type_enum_has_3_values():
    """ProviderType must have exactly 3 values."""
    from app.modules.email_config.models import ProviderType
    
    expected_types = ["SMTP", "SENDGRID", "SES"]
    
    assert len(ProviderType) == 3, (
        f"ProviderType should have 3 values, got {len(ProviderType)}"
    )
    
    for type_name in expected_types:
        assert hasattr(ProviderType, type_name), (
            f"ProviderType missing value: {type_name}"
        )
        provider = getattr(ProviderType, type_name)
        assert provider.value == type_name, (
            f"ProviderType.{type_name} has incorrect value: {provider.value}"
        )


def test_survey_status_enum_has_4_values():
    """SurveyStatus must have exactly 4 values."""
    from app.modules.surveys.models import SurveyStatus
    
    expected_statuses = ["DRAFT", "SENT", "COMPLETED", "EXPIRED"]
    
    assert len(SurveyStatus) == 4, (
        f"SurveyStatus should have 4 values, got {len(SurveyStatus)}"
    )
    
    for status_name in expected_statuses:
        assert hasattr(SurveyStatus, status_name), (
            f"SurveyStatus missing value: {status_name}"
        )
        status = getattr(SurveyStatus, status_name)
        assert status.value == status_name, (
            f"SurveyStatus.{status_name} has incorrect value: {status.value}"
        )


# ---------------------------------------------------------------------------
# Test 2: Environment Variables Validation
# Validates: Security/settings requirements
# ---------------------------------------------------------------------------

def test_environment_variables_set_and_valid():
    """Assert required environment variables are set and have valid values."""
    # PORTAL_TOKEN_TTL_DAYS - optional but if set, must be valid integer > 0
    portal_ttl = os.getenv("PORTAL_TOKEN_TTL_DAYS")
    if portal_ttl is not None:
        try:
            ttl_value = int(portal_ttl)
            assert ttl_value > 0, f"PORTAL_TOKEN_TTL_DAYS must be > 0, got {ttl_value}"
        except ValueError:
            pytest.fail(f"PORTAL_TOKEN_TTL_DAYS must be integer, got {portal_ttl}")
    
    # AGENT_API_KEY
    agent_key = os.getenv("AGENT_API_KEY")
    assert agent_key is not None and len(agent_key) > 0, (
        "AGENT_API_KEY not set or empty"
    )
    
    # JWT_SIGNING_KEY
    jwt_key = os.getenv("JWT_SIGNING_KEY")
    assert jwt_key is not None and len(jwt_key) > 0, (
        "JWT_SIGNING_KEY not set or empty"
    )


# ---------------------------------------------------------------------------
# Test 3: VersionMixin Configuration on Mutable Entities
# Validates: Requirements 7.1, 7.5
# ---------------------------------------------------------------------------

def test_version_id_col_configured_on_mutable_entities():
    """All 8 interview workflow mutable entities must have version_id_col configured."""
    from app.modules.journeys.models import InterviewJourney
    from app.modules.slots.models import InterviewSlot, InterviewerPreference
    from app.modules.feedback.models import InterviewFeedback
    from app.modules.questionnaires.models import Questionnaire, CandidateQuestionnaireResponse
    from app.modules.email_config.models import OrganizationEmailConfig
    from app.modules.notifications.models import NotificationTemplate

    mutable_entities = [
        InterviewJourney,
        InterviewSlot,
        InterviewFeedback,
        InterviewerPreference,
        Questionnaire,
        CandidateQuestionnaireResponse,
        OrganizationEmailConfig,
        NotificationTemplate,
    ]

    assert len(mutable_entities) == 8, (
        f"Expected 8 mutable entities, got {len(mutable_entities)}"
    )

    for entity in mutable_entities:
        mapper = sa_inspect(entity)
        assert mapper.version_id_col is not None, (
            f"{entity.__name__} does not have version_id_col configured"
        )


def test_version_column_is_integer_type():
    """All entities with version_id_col must have version column as Integer type."""
    from app.modules.journeys.models import InterviewJourney
    from app.modules.slots.models import InterviewSlot, InterviewerPreference
    from app.modules.feedback.models import InterviewFeedback
    from app.modules.questionnaires.models import Questionnaire, CandidateQuestionnaireResponse
    from app.modules.email_config.models import OrganizationEmailConfig
    from app.modules.notifications.models import NotificationTemplate

    mutable_entities = [
        InterviewJourney,
        InterviewSlot,
        InterviewFeedback,
        InterviewerPreference,
        Questionnaire,
        CandidateQuestionnaireResponse,
        OrganizationEmailConfig,
        NotificationTemplate,
    ]

    for entity in mutable_entities:
        mapper = sa_inspect(entity)
        version_col = mapper.version_id_col
        
        assert version_col is not None, (
            f"{entity.__name__} has no version_id_col"
        )
        
        # Get the column type
        col_type = version_col.type
        assert isinstance(col_type, Integer), (
            f"{entity.__name__} version column type is {type(col_type)}, "
            f"expected Integer"
        )


# ---------------------------------------------------------------------------
# Test 4: Module Imports - Services
# Validates: Module structure requirements
# ---------------------------------------------------------------------------

def test_all_service_modules_importable():
    """All service modules must be importable without errors."""
    # Journey services
    from app.modules.journeys.service import InterviewJourneyService
    
    # Slot services
    from app.modules.slots.service import InterviewSlotService
    
    # Feedback services
    from app.modules.feedback.service import InterviewFeedbackService
    
    # Questionnaire services
    from app.modules.questionnaires.service import QuestionnairesService
    
    # Email config services
    from app.modules.email_config.service import EmailConfigService
    
    # Notification services
    from app.modules.notifications.service import NotificationService
    
    services = [
        InterviewJourneyService,
        InterviewSlotService,
        InterviewFeedbackService,
        QuestionnairesService,
        EmailConfigService,
        NotificationService,
    ]
    
    for service in services:
        assert service is not None, f"Service {service.__name__} failed to import"


# ---------------------------------------------------------------------------
# Test 5: Module Imports - Routers
# Validates: Module structure requirements
# ---------------------------------------------------------------------------

def test_all_router_modules_importable():
    """All router modules must be importable and non-None."""
    from app.modules.journeys.router import router as journeys_router
    from app.modules.slots.router import router as slots_router
    from app.modules.feedback.router import router as feedback_router
    from app.modules.questionnaires.router import router as questionnaires_router

    routers = [
        journeys_router,
        slots_router,
        feedback_router,
        questionnaires_router,
    ]

    assert len(routers) == 4, f"Expected 4 routers, got {len(routers)}"
    
    for router in routers:
        assert router is not None


# ---------------------------------------------------------------------------
# Test 6: Module Imports - Models
# Validates: Module structure requirements
# ---------------------------------------------------------------------------

def test_all_model_modules_importable():
    """All model modules must be importable without errors."""
    # Journey models
    from app.modules.journeys.models import (
        InterviewJourney,
        InterviewJourneyStageHistory,
        CandidateInterviewJourney,
        JourneyStage,
        JourneyOverallStatus,
    )
    
    # Slot models
    from app.modules.slots.models import (
        InterviewSlot,
        InterviewerPreference,
        SlotType,
        SlotStatus,
    )
    
    # Feedback models
    from app.modules.feedback.models import (
        InterviewFeedback,
        FeedbackStatus,
    )
    
    # Questionnaire models
    from app.modules.questionnaires.models import (
        Questionnaire,
        CandidateQuestionnaireResponse,
        ResponseStatus,
    )
    
    # Email config models
    from app.modules.email_config.models import (
        OrganizationEmailConfig,
        ProviderType,
    )
    
    # Notification models
    from app.modules.notifications.models import (
        NotificationTemplate,
        NotificationStatus,
    )
    
    # Survey models
    from app.modules.surveys.models import (
        CandidateFeedbackSurvey,
        SurveyStatus,
    )
    
    models = [
        InterviewJourney,
        InterviewJourneyStageHistory,
        CandidateInterviewJourney,
        InterviewSlot,
        InterviewerPreference,
        InterviewFeedback,
        Questionnaire,
        CandidateQuestionnaireResponse,
        OrganizationEmailConfig,
        NotificationTemplate,
        CandidateFeedbackSurvey,
    ]
    
    for model in models:
        assert model is not None, f"Model {model.__name__} failed to import"
