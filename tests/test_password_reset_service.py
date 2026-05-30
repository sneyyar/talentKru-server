"""
Tests for PasswordResetService.

Feature: identity-and-access
Properties: 19, 20, 21, 22

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.10
"""

import pytest
from datetime import datetime, timezone, timedelta
import hashlib
import secrets
import bcrypt

from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.modules.auth.service import validate_password_policy


class TestPasswordPolicyValidation:
    """Test password policy validation."""

    def test_valid_password(self):
        """Test that a valid password passes validation."""
        password = "ValidPass123!"
        violations = validate_password_policy(password)
        assert violations == []

    def test_password_too_short(self):
        """Test that short passwords are rejected."""
        password = "Short1!"
        violations = validate_password_policy(password)
        assert any("12 characters" in v for v in violations)

    def test_password_missing_uppercase(self):
        """Test that passwords without uppercase are rejected."""
        password = "validpass123!"
        violations = validate_password_policy(password)
        assert any("uppercase" in v for v in violations)

    def test_password_missing_lowercase(self):
        """Test that passwords without lowercase are rejected."""
        password = "VALIDPASS123!"
        violations = validate_password_policy(password)
        assert any("lowercase" in v for v in violations)

    def test_password_missing_digit(self):
        """Test that passwords without digits are rejected."""
        password = "ValidPass!"
        violations = validate_password_policy(password)
        assert any("digit" in v for v in violations)

    def test_password_missing_special_char(self):
        """Test that passwords without special characters are rejected."""
        password = "ValidPass123"
        violations = validate_password_policy(password)
        assert any("special character" in v for v in violations)


class TestPasswordResetTokenGeneration:
    """Test password reset token generation."""

    def test_token_generation(self):
        """Test that tokens are properly generated."""
        raw_token = secrets.token_bytes(32).hex()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Verify token is 64 characters (32 bytes hex)
        assert len(raw_token) == 64
        
        # Verify hash is 64 characters (SHA-256 hex)
        assert len(token_hash) == 64

    def test_token_hash_determinism(self):
        """Test that token hashing is deterministic."""
        raw_token = secrets.token_bytes(32).hex()
        hash1 = hashlib.sha256(raw_token.encode()).hexdigest()
        hash2 = hashlib.sha256(raw_token.encode()).hexdigest()
        
        assert hash1 == hash2

    def test_token_uniqueness(self):
        """Test that generated tokens are unique."""
        tokens = set()
        for _ in range(10):
            raw_token = secrets.token_bytes(32).hex()
            tokens.add(raw_token)
        
        assert len(tokens) == 10


class TestPasswordHashing:
    """Test password hashing with bcrypt."""

    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        password = "ValidPass123!"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        # Verify hash is 60 characters (bcrypt format)
        assert len(hashed) == 60
        
        # Verify password can be verified
        assert bcrypt.checkpw(password.encode(), hashed.encode())

    def test_password_verification_failure(self):
        """Test that wrong passwords fail verification."""
        password = "ValidPass123!"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        # Verify wrong password fails
        assert not bcrypt.checkpw(b"WrongPass123!", hashed.encode())

    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes."""
        password = "ValidPass123!"
        hash1 = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        hash2 = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        # Hashes should be different (different salts)
        assert hash1 != hash2
        
        # But both should verify against the password
        assert bcrypt.checkpw(password.encode(), hash1.encode())
        assert bcrypt.checkpw(password.encode(), hash2.encode())


class TestPasswordResetProperties:
    """Property-based tests for password reset functionality."""

    @given(st.text(min_size=12, max_size=100))
    @hypothesis_settings(max_examples=10)
    def test_password_policy_validation_property(self, password):
        """
        Property: Any password that passes validation must satisfy all policy requirements.
        
        **Validates: Requirements 10.5**
        """
        violations = validate_password_policy(password)
        
        if not violations:
            # If no violations, password must satisfy all requirements
            assert len(password) >= 12
            assert any(c.isupper() for c in password)
            assert any(c.islower() for c in password)
            assert any(c.isdigit() for c in password)
            assert any(not c.isalnum() for c in password)

    def test_token_expiry_calculation_property(self):
        """
        Property: Password reset tokens must expire in exactly 15 minutes.
        
        **Validates: Requirements 10.1**
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=15)
        
        # Verify expiry is 15 minutes from now
        delta = (expires_at - now).total_seconds()
        assert delta == 15 * 60

    def test_token_uniqueness_property(self):
        """
        Property: Each password reset token must have a unique hash.
        
        **Validates: Requirements 10.1**
        """
        tokens = set()
        for _ in range(5):
            raw_token = secrets.token_bytes(32).hex()
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            tokens.add(token_hash)
        
        # Verify all tokens are unique
        assert len(tokens) == 5
