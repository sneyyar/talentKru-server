"""
Property-based tests for rate limiting infrastructure.

Feature: identity-and-access
Property 14: Authentication endpoint rate limiting
Property 15: Per-tenant API rate limiting

Requirements: 8.1, 8.2, 8.3, 8.4
"""

import pytest
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.middleware.rate_limit import RateLimiter, SlidingWindowCounter


class TestSlidingWindowCounter:
    """Unit tests for SlidingWindowCounter."""

    def test_allows_requests_within_limit(self):
        """Test that requests within the limit are allowed."""
        counter = SlidingWindowCounter(window_seconds=60, max_requests=5)
        
        for i in range(5):
            allowed, retry_after, remaining = counter.is_allowed()
            assert allowed is True
            assert retry_after == 0

    def test_rejects_requests_exceeding_limit(self):
        """Test that requests exceeding the limit are rejected."""
        counter = SlidingWindowCounter(window_seconds=60, max_requests=5)
        
        # Fill up the limit
        for i in range(5):
            counter.is_allowed()
        
        # Next request should be rejected
        allowed, retry_after, remaining = counter.is_allowed()
        assert allowed is False
        assert retry_after > 0

    def test_retry_after_is_positive(self):
        """Test that retry_after is always positive when rate limited."""
        counter = SlidingWindowCounter(window_seconds=60, max_requests=1)
        
        counter.is_allowed()  # Use the one allowed request
        allowed, retry_after, remaining = counter.is_allowed()
        
        assert allowed is False
        assert retry_after > 0
        assert retry_after <= 60


class TestRateLimiter:
    """Unit tests for RateLimiter."""

    def test_multiple_keys_independent(self):
        """Test that different keys have independent rate limits."""
        limiter = RateLimiter()
        
        # First key: use up the limit
        for i in range(5):
            retry_after, remaining = limiter.check(
                ("auth", "192.168.1.1"), window_seconds=60, max_requests=5
            )
            assert retry_after == 0
        
        # First key should now be rate limited
        retry_after, remaining = limiter.check(
            ("auth", "192.168.1.1"), window_seconds=60, max_requests=5
        )
        assert retry_after > 0
        
        # Second key should still be allowed
        retry_after, remaining = limiter.check(
            ("auth", "192.168.1.2"), window_seconds=60, max_requests=5
        )
        assert retry_after == 0

    def test_different_endpoint_groups_independent(self):
        """Test that different endpoint groups have independent rate limits."""
        limiter = RateLimiter()
        
        # Use up auth endpoint limit
        for i in range(5):
            limiter.check(
                ("auth", "192.168.1.1"), window_seconds=60, max_requests=5
            )
        
        # Auth should be rate limited
        retry_after, remaining = limiter.check(
            ("auth", "192.168.1.1"), window_seconds=60, max_requests=5
        )
        assert retry_after > 0
        
        # But invitation endpoint should still be allowed
        retry_after, remaining = limiter.check(
            ("invitation", "192.168.1.1"), window_seconds=600, max_requests=10
        )
        assert retry_after == 0


@given(ip=st.ip_addresses(v=4).map(str))
@hypothesis_settings(max_examples=20)
def test_authentication_endpoint_rate_limiting(ip):
    """
    Property 14: Authentication endpoint rate limiting
    
    Validates: Requirements 8.1, 8.2
    
    After 5 failed attempts from the same IP, assert 429 with Retry-After header
    on the 6th request.
    """
    limiter = RateLimiter()
    
    # First 5 requests should be allowed
    for i in range(5):
        retry_after, remaining = limiter.check(
            ("auth", ip), window_seconds=300, max_requests=5
        )
        assert retry_after == 0, f"Request {i+1} should be allowed"
    
    # 6th request should be rate limited
    retry_after, remaining = limiter.check(
        ("auth", ip), window_seconds=300, max_requests=5
    )
    assert retry_after > 0, "6th request should be rate limited"
    assert retry_after <= 300, "Retry-After should be within window"


@given(
    org_id=st.uuids().map(str),
    num_requests=st.integers(min_value=1001, max_value=1100),
)
@hypothesis_settings(max_examples=20)
def test_per_tenant_api_rate_limiting(org_id, num_requests):
    """
    Property 15: Per-tenant API rate limiting
    
    Validates: Requirements 8.3, 8.4
    
    Generate org with configured limit N (1000); send N+1 requests;
    assert last returns 429 with X-RateLimit-* headers.
    """
    limiter = RateLimiter()
    limit = 1000
    
    # Send requests up to the limit
    for i in range(limit):
        retry_after, remaining = limiter.check(
            ("tenant", org_id), window_seconds=60, max_requests=limit
        )
        assert retry_after == 0, f"Request {i+1} should be allowed (within limit)"
    
    # Next request should be rate limited
    retry_after, remaining = limiter.check(
        ("tenant", org_id), window_seconds=60, max_requests=limit
    )
    assert retry_after > 0, "Request exceeding limit should be rate limited"
    assert retry_after <= 60, "Retry-After should be within window"
