"""
Property-based tests for authentication.

Feature: identity-and-access
Properties: 2, 3, 4, 5, 6, 7, 8, 9

Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

import pytest
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st
import jwt
from datetime import datetime, timezone

from app.config import settings
from app.modules.auth.service import validate_password_policy


class TestPasswordPolicyProperties:
    """Property-based tests for password policy."""

    @given(password=st.text(max_size=11))
    @hypothesis_settings(max_examples=20)
    def test_short_passwords_rejected(self, password: str):
        """
        Property: Short passwords are always rejected.
        
        For any password shorter than 12 characters, validation should fail.
        """
        violations = validate_password_policy(password)
        if len(password) < 12:
            assert len(violations) > 0

    @given(
        password=st.text(
            alphabet=st.characters(
                blacklist_categories=("Cc", "Cs"),
                blacklist_characters="\n\r\t",
            ),
            min_size=12,
            max_size=100,
        )
    )
    @hypothesis_settings(max_examples=20)
    def test_valid_passwords_accepted(self, password: str):
        """
        Property: Passwords meeting all requirements are accepted.
        
        For any password with 12+ chars, uppercase, lowercase, digit, and special char,
        validation should pass.
        """
        # Only test if password meets all requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        
        violations = validate_password_policy(password)
        
        if has_upper and has_lower and has_digit and has_special:
            assert len(violations) == 0


class TestJWTProperties:
    """Property-based tests for JWT generation."""

    @given(
        sub=st.emails(),
        org_id=st.uuids().map(str),
        roles=st.lists(
            st.sampled_from(["Administrator", "Recruiter", "HiringManager"]),
            min_size=1,
            max_size=3,
            unique=True,
        ),
    )
    @hypothesis_settings(max_examples=20)
    def test_jwt_signature_verification(self, sub: str, org_id: str, roles: list):
        """
        Property 5: JWT signature verification
        
        Validates: Requirements 3.3
        
        For any JWT signed with JWT_SIGNING_KEY, decoding with the same key
        should succeed, but decoding with a different key should fail.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": sub,
            "org_id": org_id,
            "roles": roles,
            "exp": now.timestamp() + 3600,
            "iat": now.timestamp(),
            "jti": "test-jti",
        }
        
        # Sign with correct key
        token = jwt.encode(
            payload, settings.JWT_SIGNING_KEY, algorithm="HS256"
        )
        
        # Decoding with correct key should succeed
        decoded = jwt.decode(
            token, settings.JWT_SIGNING_KEY, algorithms=["HS256"]
        )
        assert decoded["sub"] == sub
        
        # Decoding with wrong key should fail
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "wrong-key", algorithms=["HS256"])
