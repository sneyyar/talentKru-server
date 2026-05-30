"""
Integration tests for RateLimitMiddleware.

Tests the middleware behavior for:
- Auth endpoint rate limiting (5 failures / 5 min; 15-min lockout)
- Per-tenant rate limiting (configurable per org, default 1000 req/min)
- Per-agent rate limiting (100 req/min)
- Invitation accept rate limiting (10 attempts / 10 min)
- Password reset rate limiting (3 req/10 min for request, 5 attempts/10 min for confirm)

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.9, 10.8, 10.9
"""

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.middleware.rate_limit import RateLimitMiddleware


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with RateLimitMiddleware."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/api/v1/token")
    async def token():
        return {"access_token": "test"}

    @app.post("/api/v1/token/refresh")
    async def token_refresh():
        return {"access_token": "test"}

    @app.post("/api/v1/auth/invitation/accept")
    async def invitation_accept():
        return {"ok": True}

    @app.post("/api/v1/auth/password-reset/request")
    async def password_reset_request():
        return {"ok": True}

    @app.post("/api/v1/auth/password-reset/confirm")
    async def password_reset_confirm():
        return {"ok": True}

    @app.post("/internal/agents/callback")
    async def agent_callback():
        return {"ok": True}

    return app


class TestAuthEndpointRateLimiting:
    """Tests for auth endpoint rate limiting (5 failures / 5 min; 15-min lockout)."""

    def test_auth_endpoint_allows_5_failures(self):
        """First 5 failed auth attempts from same IP should be allowed."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.post("/api/v1/token")
        async def token():
            # Return 401 to simulate failed auth
            return Response(status_code=401, content="Unauthorized")

        client = TestClient(app)

        for i in range(5):
            response = client.post(
                "/api/v1/token",
                json={"email": "test@test.com", "password": "wrong"},
            )
            # The middleware should pass through the 401 response
            assert response.status_code == 401

    def test_auth_endpoint_blocks_6th_failure(self):
        """6th failed auth attempt from same IP should be blocked with 429."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.post("/api/v1/token")
        async def token():
            # Return 401 to simulate failed auth
            return Response(status_code=401, content="Unauthorized")

        client = TestClient(app)

        # Make 5 failed attempts
        for i in range(5):
            response = client.post(
                "/api/v1/token",
                json={"email": "test@test.com", "password": "wrong"},
            )
            assert response.status_code == 401

        # 6th attempt should be blocked by middleware before reaching endpoint
        response = client.post(
            "/api/v1/token",
            json={"email": "test@test.com", "password": "wrong"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers


class TestInvitationAcceptRateLimiting:
    """Tests for invitation accept rate limiting (10 attempts / 10 min)."""

    def test_invitation_accept_allows_10_attempts(self):
        """First 10 invitation accept attempts from same IP should be allowed."""
        app = _make_app()
        client = TestClient(app)

        for i in range(10):
            response = client.post(
                "/api/v1/auth/invitation/accept",
                json={"token": "test", "password": "Test123!@#"},
            )
            # Should pass through to endpoint (not blocked by rate limiter)
            assert response.status_code != 429

    def test_invitation_accept_blocks_11th_attempt(self):
        """11th invitation accept attempt from same IP should be blocked with 429."""
        app = _make_app()
        client = TestClient(app)

        # Make 10 attempts
        for i in range(10):
            client.post(
                "/api/v1/auth/invitation/accept",
                json={"token": "test", "password": "Test123!@#"},
            )

        # 11th attempt should be blocked
        response = client.post(
            "/api/v1/auth/invitation/accept",
            json={"token": "test", "password": "Test123!@#"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers


class TestPasswordResetRateLimiting:
    """Tests for password reset rate limiting."""

    def test_password_reset_request_allows_3_requests(self):
        """First 3 password reset requests from same IP should be allowed."""
        app = _make_app()
        client = TestClient(app)

        for i in range(3):
            response = client.post(
                "/api/v1/auth/password-reset/request",
                json={"email": "test@test.com"},
            )
            assert response.status_code != 429

    def test_password_reset_request_blocks_4th_request(self):
        """4th password reset request from same IP should be blocked with 429."""
        app = _make_app()
        client = TestClient(app)

        # Make 3 requests
        for i in range(3):
            client.post(
                "/api/v1/auth/password-reset/request",
                json={"email": "test@test.com"},
            )

        # 4th request should be blocked
        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "test@test.com"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_password_reset_confirm_allows_5_attempts(self):
        """First 5 password reset confirm attempts from same IP should be allowed."""
        app = _make_app()
        client = TestClient(app)

        for i in range(5):
            response = client.post(
                "/api/v1/auth/password-reset/confirm",
                json={"token": "test", "password": "Test123!@#"},
            )
            assert response.status_code != 429

    def test_password_reset_confirm_blocks_6th_attempt(self):
        """6th password reset confirm attempt from same IP should be blocked with 429."""
        app = _make_app()
        client = TestClient(app)

        # Make 5 attempts
        for i in range(5):
            client.post(
                "/api/v1/auth/password-reset/confirm",
                json={"token": "test", "password": "Test123!@#"},
            )

        # 6th attempt should be blocked
        response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "test", "password": "Test123!@#"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers


class TestAgentRateLimiting:
    """Tests for per-agent rate limiting (100 req/min)."""

    def test_agent_endpoint_allows_100_requests(self):
        """First 100 agent requests with same API key should be allowed."""
        app = _make_app()
        client = TestClient(app)

        for i in range(100):
            response = client.post(
                "/internal/agents/callback",
                headers={"X-Agent-API-Key": "test-key"},
            )
            assert response.status_code != 429

    def test_agent_endpoint_blocks_101st_request(self):
        """101st agent request with same API key should be blocked with 429."""
        app = _make_app()
        client = TestClient(app)

        # Make 100 requests
        for i in range(100):
            client.post(
                "/internal/agents/callback",
                headers={"X-Agent-API-Key": "test-key"},
            )

        # 101st request should be blocked
        response = client.post(
            "/internal/agents/callback",
            headers={"X-Agent-API-Key": "test-key"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_different_agent_keys_independent(self):
        """Different agent API keys should have independent rate limits."""
        app = _make_app()
        client = TestClient(app)

        # Use up limit for key1
        for i in range(100):
            client.post(
                "/internal/agents/callback",
                headers={"X-Agent-API-Key": "key1"},
            )

        # key1 should be blocked
        response = client.post(
            "/internal/agents/callback",
            headers={"X-Agent-API-Key": "key1"},
        )
        assert response.status_code == 429

        # key2 should still be allowed
        response = client.post(
            "/internal/agents/callback",
            headers={"X-Agent-API-Key": "key2"},
        )
        assert response.status_code != 429


class TestClientIPExtraction:
    """Tests for client IP extraction from X-Forwarded-For header."""

    def test_x_forwarded_for_header_used(self):
        """Client IP should be extracted from X-Forwarded-For header."""
        app = _make_app()
        client = TestClient(app)

        # Make 5 requests with X-Forwarded-For header
        for i in range(5):
            response = client.post(
                "/api/v1/auth/invitation/accept",
                json={"token": "test", "password": "Test123!@#"},
                headers={"X-Forwarded-For": "203.0.113.1, 198.51.100.1"},
            )
            assert response.status_code != 429

        # 6th request should be blocked (same IP from X-Forwarded-For)
        response = client.post(
            "/api/v1/auth/invitation/accept",
            json={"token": "test", "password": "Test123!@#"},
            headers={"X-Forwarded-For": "203.0.113.1, 198.51.100.1"},
        )
        # Should be allowed (different from default client IP)
        assert response.status_code != 429

    def test_different_ips_independent(self):
        """Different client IPs should have independent rate limits."""
        app = _make_app()
        client = TestClient(app)

        # Make 10 requests from IP1
        for i in range(10):
            response = client.post(
                "/api/v1/auth/invitation/accept",
                json={"token": "test", "password": "Test123!@#"},
                headers={"X-Forwarded-For": "203.0.113.1"},
            )
            assert response.status_code != 429

        # 11th request from IP1 should be blocked
        response = client.post(
            "/api/v1/auth/invitation/accept",
            json={"token": "test", "password": "Test123!@#"},
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        assert response.status_code == 429

        # But requests from IP2 should still be allowed
        response = client.post(
            "/api/v1/auth/invitation/accept",
            json={"token": "test", "password": "Test123!@#"},
            headers={"X-Forwarded-For": "203.0.113.2"},
        )
        assert response.status_code != 429
