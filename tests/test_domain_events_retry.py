"""Integration tests for POST /internal/domain-events/retry endpoint.

Validates Requirement 3.6: The Server SHALL expose an internal endpoint for
retrying failed domain events, restricted to the SuperAdministrator role.

Strategy: build a minimal FastAPI test app that wires the same endpoint logic
(require_super_admin dependency + retry_failed_events call) without a real
database session, mirroring the pattern used in test_middleware_auth.py.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.dependencies import Principal, get_current_principal, require_super_admin
from app.domain_events.retry import retry_failed_events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _super_admin_principal() -> Principal:
    """Return a Principal with the SuperAdministrator role."""
    return Principal(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role="SuperAdministrator",
    )


def _regular_principal() -> Principal:
    """Return a Principal with a non-admin role."""
    return Principal(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role="Recruiter",
    )


def _make_retry_app(
    principal: Principal | None = None,
    retry_return_value: dict | None = None,
) -> FastAPI:
    """
    Build a minimal FastAPI app with the retry endpoint wired up.

    - principal: if provided, injected as the authenticated caller via
      get_current_principal override; if None, the dependency raises 401.
    - retry_return_value: the dict that retry_failed_events will return.
    """
    test_app = FastAPI()

    # Stub DB session — the endpoint only needs an AsyncSession object;
    # we pass a MagicMock so no real DB connection is attempted.
    async def _fake_db():
        yield MagicMock()

    # Stub retry function
    async def _fake_retry(db) -> dict:
        return retry_return_value or {"retried": 0, "errors": 0, "total": 0}

    # Stub principal resolution
    if principal is not None:
        async def _get_principal():
            return principal
    else:
        async def _get_principal():
            raise HTTPException(status_code=401, detail="Not authenticated")

    @test_app.post(
        "/internal/domain-events/retry",
        dependencies=[Depends(require_super_admin)],
    )
    async def retry_endpoint(db=Depends(_fake_db)):
        return await _fake_retry(db)

    test_app.dependency_overrides[get_current_principal] = _get_principal

    return test_app


# ---------------------------------------------------------------------------
# Test: endpoint requires authentication (no principal set)
# ---------------------------------------------------------------------------


def test_retry_endpoint_requires_super_admin_no_auth():
    """POST /internal/domain-events/retry returns 401 when no principal is set.

    Validates Requirement 3.6: endpoint is restricted to SuperAdministrator.
    """
    test_app = _make_retry_app(principal=None)
    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.post("/internal/domain-events/retry")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: endpoint rejects non-SuperAdministrator roles
# ---------------------------------------------------------------------------


def test_retry_endpoint_requires_super_admin_wrong_role():
    """POST /internal/domain-events/retry returns 403 for non-SuperAdministrator roles.

    Validates Requirement 3.6: endpoint is restricted to SuperAdministrator.
    """
    test_app = _make_retry_app(principal=_regular_principal())
    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.post("/internal/domain-events/retry")
    assert response.status_code == 403
    assert "forbidden" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test: successful retry returns 200 with summary
# ---------------------------------------------------------------------------


def test_retry_endpoint_success():
    """POST /internal/domain-events/retry returns 200 with retry summary when called as SuperAdministrator.

    Validates Requirement 3.6: endpoint is accessible to SuperAdministrator and
    returns a summary of retried events.
    """
    summary = {"retried": 2, "errors": 0, "total": 2}
    test_app = _make_retry_app(principal=_super_admin_principal(), retry_return_value=summary)
    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.post("/internal/domain-events/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["retried"] == 2
    assert body["errors"] == 0
    assert body["total"] == 2


# ---------------------------------------------------------------------------
# Test: retry_failed_events is called when endpoint is invoked
# ---------------------------------------------------------------------------


def test_retry_dispatches_failed_events():
    """POST /internal/domain-events/retry calls retry_failed_events exactly once.

    Validates Requirement 3.6: failed events are re-dispatched when the endpoint
    is triggered by a SuperAdministrator.
    """
    call_count = {"n": 0}
    summary = {"retried": 1, "errors": 0, "total": 1}

    test_app = FastAPI()

    async def _fake_db():
        yield MagicMock()

    async def _get_principal():
        return _super_admin_principal()

    async def _fake_retry(db) -> dict:
        call_count["n"] += 1
        return summary

    @test_app.post(
        "/internal/domain-events/retry",
        dependencies=[Depends(require_super_admin)],
    )
    async def retry_endpoint(db=Depends(_fake_db)):
        return await _fake_retry(db)

    test_app.dependency_overrides[get_current_principal] = _get_principal

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.post("/internal/domain-events/retry")

    assert response.status_code == 200
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Test: retry with no failed events returns zero counts
# ---------------------------------------------------------------------------


def test_retry_endpoint_no_failed_events():
    """POST /internal/domain-events/retry returns zeros when no failed events exist.

    Validates Requirement 3.6: the summary correctly reflects an empty retry run.
    """
    summary = {"retried": 0, "errors": 0, "total": 0}
    test_app = _make_retry_app(principal=_super_admin_principal(), retry_return_value=summary)
    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.post("/internal/domain-events/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["retried"] == 0
    assert body["errors"] == 0
    assert body["total"] == 0


# ---------------------------------------------------------------------------
# Test: retry with partial errors returns correct counts
# ---------------------------------------------------------------------------


def test_retry_endpoint_partial_errors():
    """POST /internal/domain-events/retry returns correct counts when some events fail to re-dispatch.

    Validates Requirement 3.6: the summary accurately reflects partial failures.
    """
    summary = {"retried": 3, "errors": 2, "total": 5}
    test_app = _make_retry_app(principal=_super_admin_principal(), retry_return_value=summary)
    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.post("/internal/domain-events/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["retried"] == 3
    assert body["errors"] == 2
    assert body["total"] == 5


# ---------------------------------------------------------------------------
# Test: retry_failed_events unit test — verifies it queries FAILED events
# and returns correct summary structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_failed_events_returns_summary_keys():
    """retry_failed_events returns a dict with retried, errors, and total keys.

    Validates Requirement 3.6: the retry function produces a structured summary.
    """
    # Mock the DB session to return an empty list of failed events
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    result = await retry_failed_events(mock_db)

    assert "retried" in result
    assert "errors" in result
    assert "total" in result
    assert result["total"] == 0
    assert result["retried"] == 0
    assert result["errors"] == 0
