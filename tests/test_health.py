"""Integration tests for the GET /health endpoint.

Validates Requirement 1.3: The Server SHALL expose a health check endpoint at
GET /health that returns a JSON response containing a status field ("healthy"
when the application and database connection are operational, "unhealthy"
otherwise) and a version field (the application semantic version string).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_healthy_db_override():
    """Return a dependency override that simulates a reachable database."""
    mock_result = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override():
        yield mock_session

    return override


def _make_unhealthy_db_override():
    """Return a dependency override that simulates an unreachable database."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("DB connection failed"))

    async def override():
        yield mock_session

    return override


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_healthy():
    """GET /health returns 200 with status 'healthy' when DB is reachable.

    Validates: Requirements 1.3
    """
    app.dependency_overrides[get_db_session] = _make_healthy_db_override()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_check_unhealthy():
    """GET /health returns 200 with status 'unhealthy' when DB raises an exception.

    Validates: Requirements 1.3
    """
    app.dependency_overrides[get_db_session] = _make_unhealthy_db_override()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_check_response_shape():
    """GET /health always returns both 'status' and 'version' fields.

    Validates: Requirements 1.3
    """
    app.dependency_overrides[get_db_session] = _make_healthy_db_override()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {"status", "version"}
    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)
