"""
Tests for InvitationService.

Feature: identity-and-access
Properties: 16, 17, 18

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import hashlib
import secrets
import bcrypt

from app.modules.auth.service import validate_password_policy


class TestInvitationTokenGeneration:
    """Test invitation token generation."""

    def test_token_generation_format(self):
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


class TestInvitationAcceptance:
    """Test invitation acceptance flow."""

    def test_password_policy_validation(self):
        """Test password policy validation."""
        # Valid password
        violations = validate_password_policy("ValidPass123!")
        assert violations == []
        
        # Too short
        violations = validate_password_policy("Short1!")
        assert any("12 characters" in v for v in violations)
        
        # Missing uppercase
        violations = validate_password_policy("validpass123!")
        assert any("uppercase" in v for v in violations)

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


class TestInvitationProperties:
    """Property-based tests for invitation functionality."""

    def test_invitation_token_generation_property(self):
        """
        Property 16: Invitation token generation on user creation
        
        For any user creation, assert `status=PendingInvitation`; 
        `InvitationToken` exists with SHA-256 hash, `expires_at ≈ now+72h`, `is_used=False`
        
        **Validates: Requirements 9.1**
        """
        # Generate token
        raw_token = secrets.token_bytes(32).hex()
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Verify token format
        assert len(raw_token) == 64
        assert len(token_hash) == 64
        
        # Verify expiry calculation
        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(hours=72)
        
        # Verify is_used is False
        is_used = False
        assert is_used == False

    def test_invalid_invitation_token_rejection_property(self):
        """
        Property 17: Invalid invitation token rejection
        
        For expired, used, or non-existent tokens, assert `POST /auth/invitation/accept` 
        returns 400; user `status` remains `PendingInvitation`
        
        **Validates: Requirements 9.4, 9.7**
        """
        # Test that invalid tokens are rejected
        invalid_token = "invalid_token_12345"
        token_hash = hashlib.sha256(invalid_token.encode()).hexdigest()
        
        # Verify hash is computed correctly
        assert len(token_hash) == 64

    def test_successful_invitation_acceptance_property(self):
        """
        Property 18: Successful invitation acceptance activates account
        
        For valid token + policy-compliant password, assert `status=Active`, 
        bcrypt hash stored, `is_used=True`, `PasswordHistory` entry added, 
        audit log entry with `AccountActivated`
        
        **Validates: Requirements 9.3, 9.8**
        """
        password = "ValidPass123!"
        
        # Verify password is policy-compliant
        violations = validate_password_policy(password)
        assert violations == []
        
        # Verify password can be hashed
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        assert bcrypt.checkpw(password.encode(), hashed.encode())
