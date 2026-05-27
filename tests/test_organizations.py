"""
Integration tests for organization CRUD endpoints.

Tests the following endpoints via httpx.AsyncClient with mocked service layer
and dependency injection:
  - POST   /api/v1/organizations
  - GET    /api/v1/organizations
  - GET    /api/v1/organizations/{id}
  - PATCH  /api/v1/organizations/{id}

Requirements: 2.6, 2.7
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.dependencies import Principal
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()
_NOW = datetime.now(timezone.utc)

_SUPER_ADMIN_PRINCIPAL = Principal(
    user_id=_USER_ID,
    organization_id=_ORG_ID,
    role="SuperAdministrator",
)

_REGULAR_PRINCIPAL = Principal(
    user_id=_USER_ID,
    organization_id=_ORG_ID,
    role="HiringManager",
)


def _make_org(
    org_id: uuid.UUID | None = None,
    name: str = "Acme Corp",
    slug: str = "acme-corp",
) -> SimpleNamespace:
    """
    Build a plain namespace that mimics an Organization ORM instance.

    Using SimpleNamespace avoids SQLAlchemy mapper instrumentation issues
    when constructing mock objects outside of a real session.
    """
    return SimpleNamespace(
        organization_id=org_id or _ORG_ID,
        name=name,
        slug=slug,
        logo_url=None,
        primary_color=None,
        secondary_color=None,
        terms_url=None,
        contact_name=None,
        contact_email=None,
        contact_phone=None,
        feature_flags={},
        allowed_origins=[],
        shard_id=0,
        version=1,
        created_at=_NOW,
        updated_at=_NOW,
        deleted_at=None,
    )


async def _noop_db_session():
    """Stub DB session dependency — yields None so no real DB is touched."""
    yield None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def super_admin_client():
    """
    AsyncClient with the SuperAdministrator principal and a no-op DB session
    injected so that require_super_admin() passes and no real DB is touched.
    """
    from app.database import get_db_session
    from app.dependencies import get_current_principal

    async def _override_principal():
        return _SUPER_ADMIN_PRINCIPAL

    app.dependency_overrides[get_current_principal] = _override_principal
    app.dependency_overrides[get_db_session] = _noop_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_current_principal, None)
    app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def regular_user_client():
    """
    AsyncClient with a non-SuperAdministrator principal injected so that
    require_super_admin() raises 403.  DB session is also stubbed out.
    """
    from app.database import get_db_session
    from app.dependencies import get_current_principal

    async def _override_principal():
        return _REGULAR_PRINCIPAL

    app.dependency_overrides[get_current_principal] = _override_principal
    app.dependency_overrides[get_db_session] = _noop_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_current_principal, None)
    app.dependency_overrides.pop(get_db_session, None)


# ---------------------------------------------------------------------------
# Test: POST /api/v1/organizations — success (201)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_organization_success(super_admin_client):
    """
    POST /api/v1/organizations returns 201 with the created organization data.

    Validates: Requirements 2.6
    """
    org = _make_org()
    payload = {"name": "Acme Corp", "slug": "acme-corp"}

    with patch(
        "app.modules.organizations.router.create_organization",
        new_callable=AsyncMock,
        return_value=org,
    ):
        response = await super_admin_client.post(
            "/api/v1/organizations", json=payload
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Corp"
    assert body["slug"] == "acme-corp"
    assert body["shard_id"] == 0
    assert body["version"] == 1
    assert "organization_id" in body


# ---------------------------------------------------------------------------
# Test: POST /api/v1/organizations — duplicate slug (409)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_organization_duplicate_slug(super_admin_client):
    """
    POST /api/v1/organizations returns 409 with a slug-specific error body
    when the slug is already in use.

    Validates: Requirements 2.7
    """
    payload = {"name": "Acme Corp 2", "slug": "acme-corp"}

    with patch(
        "app.modules.organizations.router.create_organization",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "slug already in use", "field": "slug"},
        ),
    ):
        response = await super_admin_client.post(
            "/api/v1/organizations", json=payload
        )

    assert response.status_code == 409
    body = response.json()
    # FastAPI wraps HTTPException detail under the "detail" key
    assert body["detail"]["detail"] == "slug already in use"
    assert body["detail"]["field"] == "slug"


# ---------------------------------------------------------------------------
# Test: GET /api/v1/organizations — list (200)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_organizations(super_admin_client):
    """
    GET /api/v1/organizations returns 200 with a list of organizations.

    Validates: Requirements 2.6
    """
    orgs = [
        _make_org(org_id=uuid.uuid4(), name="Org A", slug="org-a"),
        _make_org(org_id=uuid.uuid4(), name="Org B", slug="org-b"),
    ]

    with patch(
        "app.modules.organizations.router.list_organizations",
        new_callable=AsyncMock,
        return_value=orgs,
    ):
        response = await super_admin_client.get("/api/v1/organizations")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    slugs = {item["slug"] for item in body}
    assert slugs == {"org-a", "org-b"}


# ---------------------------------------------------------------------------
# Test: GET /api/v1/organizations/{id} — single org (200)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_organization(super_admin_client):
    """
    GET /api/v1/organizations/{id} returns 200 with the matching organization.

    Validates: Requirements 2.6
    """
    org = _make_org()

    with patch(
        "app.modules.organizations.router.get_organization",
        new_callable=AsyncMock,
        return_value=org,
    ):
        response = await super_admin_client.get(
            f"/api/v1/organizations/{_ORG_ID}"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == str(_ORG_ID)
    assert body["slug"] == "acme-corp"


# ---------------------------------------------------------------------------
# Test: PATCH /api/v1/organizations/{id} — update (200)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_organization(super_admin_client):
    """
    PATCH /api/v1/organizations/{id} returns 200 with the updated organization.

    Validates: Requirements 2.6
    """
    updated_org = _make_org()
    updated_org.name = "Acme Corp Updated"
    updated_org.version = 2

    payload = {"version": 1, "name": "Acme Corp Updated"}

    with patch(
        "app.modules.organizations.router.update_organization",
        new_callable=AsyncMock,
        return_value=updated_org,
    ):
        response = await super_admin_client.patch(
            f"/api/v1/organizations/{_ORG_ID}", json=payload
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme Corp Updated"
    assert body["version"] == 2


# ---------------------------------------------------------------------------
# Test: 403 for non-SuperAdministrator callers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_super_admin_forbidden_on_create(regular_user_client):
    """
    POST /api/v1/organizations returns 403 when the caller is not a
    SuperAdministrator.

    Validates: Requirements 2.6
    """
    payload = {"name": "Acme Corp", "slug": "acme-corp"}
    response = await regular_user_client.post(
        "/api/v1/organizations", json=payload
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Access to this resource is forbidden"


@pytest.mark.asyncio
async def test_non_super_admin_forbidden_on_list(regular_user_client):
    """
    GET /api/v1/organizations returns 403 when the caller is not a
    SuperAdministrator.

    Validates: Requirements 2.6
    """
    response = await regular_user_client.get("/api/v1/organizations")
    assert response.status_code == 403
    assert response.json()["detail"] == "Access to this resource is forbidden"


@pytest.mark.asyncio
async def test_non_super_admin_forbidden_on_get(regular_user_client):
    """
    GET /api/v1/organizations/{id} returns 403 when the caller is not a
    SuperAdministrator.

    Validates: Requirements 2.6
    """
    response = await regular_user_client.get(
        f"/api/v1/organizations/{_ORG_ID}"
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Access to this resource is forbidden"


@pytest.mark.asyncio
async def test_non_super_admin_forbidden_on_update(regular_user_client):
    """
    PATCH /api/v1/organizations/{id} returns 403 when the caller is not a
    SuperAdministrator.

    Validates: Requirements 2.6
    """
    payload = {"version": 1, "name": "Hacked Name"}
    response = await regular_user_client.patch(
        f"/api/v1/organizations/{_ORG_ID}", json=payload
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Access to this resource is forbidden"
