"""Unit tests for app/middleware/auth.py — agent API key guard.

Validates Requirements 5.4 and 5.5.
"""

import pytest
from unittest.mock import patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.middleware.auth import require_agent_api_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(agent_api_key: str) -> FastAPI:
    """Create a minimal FastAPI app with the guard applied to a test route."""
    app = FastAPI()

    @app.get("/internal/agents/test", dependencies=[Depends(require_agent_api_key)])
    async def protected_route():
        return {"ok": True}

    return app


def _client(agent_api_key: str) -> TestClient:
    app = _make_app(agent_api_key)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests: valid key
# ---------------------------------------------------------------------------

def test_valid_key_returns_200():
    """A request with the correct X-Agent-API-Key header is allowed through."""
    with patch("app.middleware.auth.settings") as mock_settings:
        mock_settings.AGENT_API_KEY = "secret-key-123"
        client = _client("secret-key-123")
        response = client.get(
            "/internal/agents/test",
            headers={"X-Agent-API-Key": "secret-key-123"},
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Tests: missing or wrong key
# ---------------------------------------------------------------------------

def test_missing_header_returns_401():
    """A request without the X-Agent-API-Key header is rejected with 401."""
    with patch("app.middleware.auth.settings") as mock_settings:
        mock_settings.AGENT_API_KEY = "secret-key-123"
        client = _client("secret-key-123")
        response = client.get("/internal/agents/test")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Agent-API-Key"


def test_empty_header_returns_401():
    """A request with an empty X-Agent-API-Key header is rejected with 401."""
    with patch("app.middleware.auth.settings") as mock_settings:
        mock_settings.AGENT_API_KEY = "secret-key-123"
        client = _client("secret-key-123")
        response = client.get(
            "/internal/agents/test",
            headers={"X-Agent-API-Key": ""},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Agent-API-Key"


def test_wrong_key_returns_401():
    """A request with an incorrect X-Agent-API-Key value is rejected with 401."""
    with patch("app.middleware.auth.settings") as mock_settings:
        mock_settings.AGENT_API_KEY = "secret-key-123"
        client = _client("secret-key-123")
        response = client.get(
            "/internal/agents/test",
            headers={"X-Agent-API-Key": "wrong-key"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Agent-API-Key"


# ---------------------------------------------------------------------------
# Tests: AGENT_API_KEY not configured
# ---------------------------------------------------------------------------

def test_unconfigured_agent_api_key_returns_401():
    """When AGENT_API_KEY is empty/unset in settings, all requests are rejected."""
    with patch("app.middleware.auth.settings") as mock_settings:
        mock_settings.AGENT_API_KEY = ""
        client = _client("")
        response = client.get(
            "/internal/agents/test",
            headers={"X-Agent-API-Key": "any-key"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Agent-API-Key"


def test_none_agent_api_key_returns_401():
    """When AGENT_API_KEY is None in settings, all requests are rejected."""
    with patch("app.middleware.auth.settings") as mock_settings:
        mock_settings.AGENT_API_KEY = None
        client = _client("")
        response = client.get(
            "/internal/agents/test",
            headers={"X-Agent-API-Key": "any-key"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing X-Agent-API-Key"
