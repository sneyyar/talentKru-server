"""
Rate limiting middleware for protecting authentication and API endpoints.

Provides:
- SlidingWindowCounter: Thread-safe sliding window rate limiter
- RateLimiter: Multi-key rate limiter for different endpoint groups
- RateLimitMiddleware: FastAPI middleware for applying rate limits

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 9.9, 10.8, 10.9
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class SlidingWindowCounter:
    """
    Thread-safe sliding window counter for rate limiting.
    
    Uses a deque of monotonic timestamps to track requests within a window.
    
    Requirements: 8.7
    """

    window_seconds: int
    max_requests: int
    _timestamps: deque = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_allowed(self) -> tuple[bool, int, int]:
        """
        Check if a request is allowed and return retry-after time if not.
        
        Returns:
            Tuple of (allowed: bool, retry_after_seconds: int, remaining: int)
            - If allowed: (True, 0, remaining_requests)
            - If rate limited: (False, seconds_to_wait, 0)
        """
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.window_seconds
            
            # Remove timestamps outside the window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            
            # Check if we've exceeded the limit
            if len(self._timestamps) >= self.max_requests:
                oldest = self._timestamps[0]
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                return False, retry_after, 0
            
            # Add current timestamp and allow
            self._timestamps.append(now)
            remaining = self.max_requests - len(self._timestamps)
            return True, 0, remaining


class RateLimiter:
    """
    In-memory sliding window rate limiter.
    
    Keyed by (endpoint_group, identifier) where identifier is IP, org_id, or agent key.
    
    Requirements: 8.7
    """

    def __init__(self):
        """Initialize the rate limiter."""
        self._counters: dict[tuple, SlidingWindowCounter] = {}
        self._lock = threading.Lock()

    def get_counter(
        self, key: tuple, window_seconds: int, max_requests: int
    ) -> SlidingWindowCounter:
        """
        Get or create a counter for the given key.
        
        Args:
            key: Tuple of (endpoint_group, identifier)
            window_seconds: Time window in seconds
            max_requests: Maximum requests allowed in the window
            
        Returns:
            SlidingWindowCounter instance
        """
        with self._lock:
            if key not in self._counters:
                self._counters[key] = SlidingWindowCounter(
                    window_seconds, max_requests
                )
            return self._counters[key]

    def check(
        self, key: tuple, window_seconds: int, max_requests: int
    ) -> tuple[int, int]:
        """
        Check if a request is allowed and return retry-after time if not.
        
        Args:
            key: Tuple of (endpoint_group, identifier)
            window_seconds: Time window in seconds
            max_requests: Maximum requests allowed in the window
            
        Returns:
            Tuple of (retry_after_seconds, remaining_requests)
            - If allowed: (0, remaining)
            - If rate limited: (>0, 0)
        """
        counter = self.get_counter(key, window_seconds, max_requests)
        allowed, retry_after, remaining = counter.is_allowed()
        return retry_after, remaining


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for applying rate limits to various endpoint groups.
    
    Applies:
    - IP-based sliding window on POST /token and POST /token/refresh (5 failures / 5 min; 15-min lockout)
    - Per-tenant rate limiting on all authenticated endpoints (configurable per org, default 1000 req/min)
    - Per-agent rate limiting on /internal/agents/ routes (100 req/min)
    - IP-based rate limiting on invitation and password reset endpoints
    
    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.9, 10.8, 10.9
    """

    def __init__(self, app):
        """Initialize the middleware."""
        super().__init__(app)
        self.rate_limiter = RateLimiter()
        # Track lockout periods for auth endpoints (IP -> lockout_until_timestamp)
        self._auth_lockouts: dict[str, float] = {}
        self._lockout_lock = threading.Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process the request and apply rate limiting.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Response with rate limit headers if applicable
        """
        client_ip = self._get_client_ip(request)
        path = request.url.path
        method = request.method

        # Auth endpoint rate limiting (5 failures / 5 min; 15-min lockout)
        # Requirements: 8.1, 8.2
        if path in ("/api/v1/token", "/api/v1/token/refresh") and method == "POST":
            # Check if IP is in lockout
            lockout_until = self._check_lockout(client_ip)
            if lockout_until > 0:
                return Response(
                    status_code=429,
                    headers={"Retry-After": str(lockout_until)},
                )
            
            # Process the request to check if it's a failure
            response = await call_next(request)
            
            # If it's a 401 (failed auth), increment the failure counter
            if response.status_code == 401:
                retry_after, _ = self.rate_limiter.check(
                    ("auth_failures", client_ip), window_seconds=300, max_requests=5
                )
                if retry_after > 0:
                    # Exceeded 5 failures in 5 min, set 15-min lockout
                    self._set_lockout(client_ip, 900)  # 15 minutes
                    return Response(
                        status_code=429,
                        headers={"Retry-After": "900"},
                    )
            
            return response

        # Invitation accept rate limiting (10 attempts / 10 min)
        # Requirement: 9.9
        if path == "/api/v1/auth/invitation/accept" and method == "POST":
            retry_after, _ = self.rate_limiter.check(
                ("invitation", client_ip), window_seconds=600, max_requests=10
            )
            if retry_after > 0:
                return Response(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

        # Password reset request rate limiting (3 req / 10 min)
        # Requirement: 10.8
        if path == "/api/v1/auth/password-reset/request" and method == "POST":
            retry_after, _ = self.rate_limiter.check(
                ("password_reset_request", client_ip),
                window_seconds=600,
                max_requests=3,
            )
            if retry_after > 0:
                return Response(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

        # Password reset confirm rate limiting (5 attempts / 10 min)
        # Requirement: 10.9
        if path == "/api/v1/auth/password-reset/confirm" and method == "POST":
            retry_after, _ = self.rate_limiter.check(
                ("password_reset_confirm", client_ip),
                window_seconds=600,
                max_requests=5,
            )
            if retry_after > 0:
                return Response(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

        # Per-agent rate limiting on /internal/agents/ (100 req / min)
        # Requirement: 8.5
        if path.startswith("/internal/agents/") and method == "POST":
            agent_key = request.headers.get("X-Agent-API-Key", "unknown")
            retry_after, _ = self.rate_limiter.check(
                ("agent", agent_key), window_seconds=60, max_requests=100
            )
            if retry_after > 0:
                return Response(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

        # Call the next middleware/handler
        response = await call_next(request)

        # Per-tenant rate limiting on authenticated endpoints (configurable per org, default 1000 req/min)
        # Requirements: 8.3, 8.4
        # Only apply to authenticated endpoints (those that have org_id in request state)
        if hasattr(request.state, "org_id") and response.status_code < 400:
            org_id = request.state.org_id
            # Get the org's configured rate limit (default 1000)
            org_limit = getattr(request.state, "org_rate_limit", 1000)
            
            retry_after, remaining = self.rate_limiter.check(
                ("tenant", str(org_id)), window_seconds=60, max_requests=org_limit
            )
            
            if retry_after > 0:
                reset_time = int(time.time()) + retry_after
                return Response(
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(org_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_time),
                    },
                )
            else:
                # Add rate limit headers on success
                reset_time = int(time.time()) + 60
                response.headers["X-RateLimit-Limit"] = str(org_limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response

    def _check_lockout(self, client_ip: str) -> int:
        """
        Check if an IP is in lockout and return remaining lockout time.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            Remaining lockout time in seconds (0 if not locked out)
        """
        with self._lockout_lock:
            if client_ip not in self._auth_lockouts:
                return 0
            
            lockout_until = self._auth_lockouts[client_ip]
            now = time.time()
            
            if now >= lockout_until:
                # Lockout expired, remove it
                del self._auth_lockouts[client_ip]
                return 0
            
            return int(lockout_until - now) + 1

    def _set_lockout(self, client_ip: str, duration_seconds: int) -> None:
        """
        Set a lockout for an IP address.
        
        Args:
            client_ip: Client IP address
            duration_seconds: Lockout duration in seconds
        """
        with self._lockout_lock:
            self._auth_lockouts[client_ip] = time.time() + duration_seconds

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """
        Extract client IP from request.
        
        Checks X-Forwarded-For header first (for proxied requests),
        then falls back to client address.
        
        Args:
            request: The incoming request
            
        Returns:
            Client IP address
        """
        if "x-forwarded-for" in request.headers:
            return request.headers["x-forwarded-for"].split(",")[0].strip()
        return request.client.host if request.client else "unknown"
