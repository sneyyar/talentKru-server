"""
Smoke tests for the platform foundation.

These tests are pure Python/import checks — no live database required.
They verify:
- All required event type constants are registered in HandlerRegistry (Req 3.7)
- version_id_col is configured on all 14 mutable mappers (Req 7.1, 7.5)
- All module routers are importable (Req 1.7)
- FastAPI app has the expected platform routes (Req 1.3)
"""

import pytest


# ---------------------------------------------------------------------------
# Test 1: All required event types are registered in HandlerRegistry
# Validates: Requirements 3.7
# ---------------------------------------------------------------------------

def test_required_event_types_defined():
    """All 8 required event types must have at least one handler registered."""
    from app.domain_events.handlers import HandlerRegistry

    required_types = [
        "journey_stage_changed",
        "questionnaire_submitted",
        "interview_slot_created",
        "offer_accepted",
        "candidate_created",
        "candidate_status_changed",
        "role_assignment_changed",
        "requisition_status_changed",
    ]
    for event_type in required_types:
        assert event_type in HandlerRegistry, f"Missing handler for: {event_type}"
        assert len(HandlerRegistry[event_type]) > 0, (
            f"HandlerRegistry has empty handler list for: {event_type}"
        )


# ---------------------------------------------------------------------------
# Test 2: version_id_col is configured on all 14 mutable mappers
# Validates: Requirements 7.1, 7.5
# ---------------------------------------------------------------------------

def test_version_id_col_on_all_mutable_entities():
    """All 14 mutable entities must have version_id_col configured via VersionMixin."""
    from sqlalchemy import inspect as sa_inspect

    from app.modules.organizations.models import Organization, OrganizationEmailConfig
    from app.modules.candidates.models import Candidate
    from app.modules.users.models import User
    from app.modules.journeys.models import InterviewJourney
    from app.modules.interviews.models import InterviewSlot, InterviewFeedback, InterviewerPreference
    from app.modules.requisitions.models import JobRequisition
    from app.modules.job_posting.models import JobPosting
    from app.modules.job_profile.models import JobProfile
    from app.modules.questionnaires.models import Questionnaire, CandidateQuestionnaireResponse
    from app.modules.reporting.models import NotificationTemplate

    mutable_entities = [
        Organization,
        OrganizationEmailConfig,
        Candidate,
        User,
        InterviewJourney,
        InterviewSlot,
        InterviewFeedback,
        InterviewerPreference,
        JobRequisition,
        JobPosting,
        JobProfile,
        Questionnaire,
        CandidateQuestionnaireResponse,
        NotificationTemplate,
    ]

    assert len(mutable_entities) == 14, (
        f"Expected 14 mutable entities, got {len(mutable_entities)}"
    )

    for entity in mutable_entities:
        mapper = sa_inspect(entity)
        assert mapper.version_id_col is not None, (
            f"{entity.__name__} does not have version_id_col configured"
        )


# ---------------------------------------------------------------------------
# Test 3: All module routers are importable
# Validates: Requirements 1.7
# ---------------------------------------------------------------------------

def test_all_module_routers_importable():
    """All 18 module routers must be importable and non-None."""
    from app.modules.auth.router import router as auth_router
    from app.modules.rbac.router import router as rbac_router
    from app.modules.users.router import router as users_router
    from app.modules.organizations.router import router as organizations_router
    from app.modules.candidates.router import router as candidates_router
    from app.modules.resumes.router import router as resumes_router
    from app.modules.requisitions.router import router as requisitions_router
    from app.modules.job_profile.router import router as job_profile_router
    from app.modules.job_posting.router import router as job_posting_router
    from app.modules.skills.router import router as skills_router
    from app.modules.matching.router import router as matching_router
    from app.modules.journeys.router import router as journeys_router
    from app.modules.interviews.router import router as interviews_router
    from app.modules.questionnaires.router import router as questionnaires_router
    from app.modules.portal.router import router as portal_router
    from app.modules.reporting.router import router as reporting_router
    from app.modules.agents.router import router as agents_router
    from app.modules.observability.router import router as observability_router

    routers = [
        auth_router, rbac_router, users_router, organizations_router,
        candidates_router, resumes_router, requisitions_router,
        job_profile_router, job_posting_router, skills_router,
        matching_router, journeys_router, interviews_router,
        questionnaires_router, portal_router, reporting_router,
        agents_router, observability_router,
    ]

    assert len(routers) == 18, f"Expected 18 routers, got {len(routers)}"
    for router in routers:
        assert router is not None


# ---------------------------------------------------------------------------
# Test 4: FastAPI app has the expected platform routes
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------

def test_app_has_health_route():
    """The FastAPI app must expose /health, /metrics, and the domain-events retry endpoint."""
    from app.main import app
    from fastapi.routing import APIRoute

    route_paths = [r.path for r in app.routes if isinstance(r, APIRoute)]

    assert "/health" in route_paths, (
        f"/health not found in routes: {route_paths}"
    )
    assert "/metrics" in route_paths, (
        f"/metrics not found in routes: {route_paths}"
    )
    assert "/internal/domain-events/retry" in route_paths, (
        f"/internal/domain-events/retry not found in routes: {route_paths}"
    )
