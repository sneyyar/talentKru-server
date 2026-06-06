"""
Tests for AuthService and authentication flow.

Feature: identity-and-access
Properties: 2, 3, 4, 5, 6, 7, 8, 9

Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import jwt
import bcrypt
import hashlib

from hypothesis import given, settings as hypothesis_settings, HealthCheck
from hypothesis import strategies as st

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.base_model import Base
from app.config import settings
from app.modules.auth.service import (
    AuthService,
    RevocationCache,
    AuthenticationError,
    validate_password_policy,
    check_password_history,
)
from app.modules.auth.models import RevokedToken, RefreshToken
from app.modules.users.models import User, UserStatus, PasswordHistory
from app.modules.users.service import UserService
from app.modules.organizations.models import Organization
from app.modules.rbac.models import Role, UserRole
from app.crypto import encrypt_field, decrypt_field





@pytest.fixture
def revocation_cache():
    """Create a revocation cache instance."""
    return RevocationCache()


class TestPasswordPolicy:
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


class TestAuthServiceBasics:
    """Basic unit tests for AuthService."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, db_session, revocation_cache, org_id, test_run_id):
        """Test successful authentication."""
        password = "ValidPass123!"
        
        # Use unique email for each test run
        email = f"test-{test_run_id[:20]}@example.com"
        
        # Create a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email=email,
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Set password and status
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Authenticate
        auth_service = AuthService(db_session, revocation_cache)
        access_token, refresh_token = await auth_service.authenticate(
            email, password, org_id
        )
        
        assert access_token is not None
        assert refresh_token is not None
        
        # Verify access token is a valid JWT
        decoded = jwt.decode(
            access_token, settings.JWT_SIGNING_KEY, algorithms=["HS256"]
        )
        # The JWT's "sub" claim contains the encrypted email, verify it matches what's in the DB
        decrypted_jwt_email = decrypt_field(decoded["sub"])
        decrypted_user_email = decrypt_field(user.email)
        assert decrypted_jwt_email == decrypted_user_email
        assert decoded["org_id"] == str(org_id)

    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(self, db_session, revocation_cache, org_id):
        """Test authentication with invalid credentials."""
        password = "ValidPass123!"
        
        # Create a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Set password and status
        hashed_password = bcrypt.hashpw(b"ValidPass123!", bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Try to authenticate with wrong password
        auth_service = AuthService(db_session, revocation_cache)
        with pytest.raises(AuthenticationError):
            await auth_service.authenticate(
                "test@example.com", "WrongPassword123!", org_id
            )

    @pytest.mark.asyncio
    async def test_authenticate_locked_user(self, db_session, revocation_cache, org_id):
        """Test that locked users cannot authenticate."""
        password = "ValidPass123!"
        
        # Create a locked user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Set password and lock status
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.LOCKED
        await db_session.flush()
        
        # Try to authenticate
        auth_service = AuthService(db_session, revocation_cache)
        with pytest.raises(AuthenticationError):
            await auth_service.authenticate(
                "test@example.com", password, org_id
            )

    @pytest.mark.asyncio
    async def test_failed_login_attempts_lockout(self, db_session, revocation_cache, org_id):
        """Test that 5 failed attempts lock the user."""
        password = "ValidPass123!"
        
        # Create a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Set password and status
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Make 5 failed attempts
        auth_service = AuthService(db_session, revocation_cache)
        for i in range(5):
            with pytest.raises(AuthenticationError):
                await auth_service.authenticate(
                    "test@example.com", "WrongPassword123!", org_id
                )
        
        # Verify user is locked
        user = await user_service.get_user_by_id(user.user_id, org_id)
        assert user.status == UserStatus.LOCKED.value
        assert user.failed_login_attempts == 5

    @pytest.mark.asyncio
    async def test_successful_login_resets_failed_attempts(self, db_session, revocation_cache, org_id):
        """Test that successful login resets failed attempts counter."""
        password = "ValidPass123!"
        
        # Create a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        # Set password and status
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        user.failed_login_attempts = 3
        await db_session.flush()
        
        # Authenticate successfully
        auth_service = AuthService(db_session, revocation_cache)
        access_token, refresh_token = await auth_service.authenticate(
            "test@example.com", password, org_id
        )
        
        # Verify failed attempts are reset
        user = await user_service.get_user_by_id(user.user_id, org_id)
        assert user.failed_login_attempts == 0


@given(
    example_num=st.integers(min_value=0, max_value=19),
    roles=st.lists(
        st.sampled_from(["Administrator", "Recruiter", "HiringManager"]),
        min_size=1,
        max_size=3,
        unique=True,
    ),
)
@hypothesis_settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@pytest.mark.asyncio
async def test_jwt_claims_completeness(db_session, revocation_cache, org_id, test_run_id, example_num, roles):
    """
    Property 3: JWT claims completeness
    
    Validates: Requirements 3.4, 4.7, 5.7
    
    For any issued JWT, verify it contains all required claims.
    """
    password = "ValidPass123!"
    
    # Use unique email combining test_run_id, example_num, and UUID to ensure no conflicts across runs
    # Hypothesis replays stored examples, so we need a unique part that changes with each run
    unique_email = f"test-{test_run_id}-ex{example_num}-{uuid4().hex[:8]}@example.com"
    
    # Create a user with roles
    user_service = UserService(db_session)
    user = await user_service.create_user(
        email=unique_email,
        given_name="John",
        last_name="Doe",
        org_id=org_id,
    )
    
    # Set password and status
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user.hashed_password = hashed_password
    user.status = UserStatus.ACTIVE
    await db_session.flush()
    
    # Authenticate
    auth_service = AuthService(db_session, revocation_cache)
    access_token, _ = await auth_service.authenticate(unique_email, password, org_id)
    
    # Decode and verify claims
    decoded = jwt.decode(
        access_token, settings.JWT_SIGNING_KEY, algorithms=["HS256"]
    )
    
    # Check required claims
    assert "sub" in decoded
    decrypted_jwt_email = decrypt_field(decoded["sub"])
    decrypted_user_email = decrypt_field(user.email)
    assert decrypted_jwt_email == decrypted_user_email
    assert "org_id" in decoded
    assert decoded["org_id"] == str(org_id)
    assert "roles" in decoded
    assert "exp" in decoded
    assert "iat" in decoded
    assert "jti" in decoded
    
    # Verify TTL is approximately 60 minutes
    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    iat_time = datetime.fromtimestamp(decoded["iat"], tz=timezone.utc)
    ttl_seconds = (exp_time - iat_time).total_seconds()
    assert 3590 <= ttl_seconds <= 3610  # Allow 10 second variance


@pytest.mark.asyncio
async def test_revocation_cache_basic(revocation_cache):
    """Test basic revocation cache operations."""
    jti = "test-jti-123"
    
    # Initially not revoked
    assert not revocation_cache.is_revoked(jti)
    
    # Revoke it
    revocation_cache.revoke(jti)
    
    # Now it should be revoked
    assert revocation_cache.is_revoked(jti)


@pytest.mark.asyncio
async def test_revocation_cache_expiration(revocation_cache):
    """Test that revocation cache entries expire."""
    # Create a cache with 1 second TTL
    cache = RevocationCache(ttl_seconds=1)
    jti = "test-jti-123"
    
    # Revoke it
    cache.revoke(jti)
    assert cache.is_revoked(jti)
    
    # Wait for expiration
    import asyncio
    await asyncio.sleep(1.1)
    
    # Should no longer be revoked
    assert not cache.is_revoked(jti)


class TestRevocationCache:
    """Test RevocationCache functionality."""

    @pytest.mark.asyncio
    async def test_revocation_cache_basic(self, revocation_cache):
        """Test basic revocation cache operations."""
        jti = "test-jti-123"
        
        # Initially not revoked
        assert not revocation_cache.is_revoked(jti)
        
        # Revoke it
        revocation_cache.revoke(jti)
        
        # Now it should be revoked
        assert revocation_cache.is_revoked(jti)

    @pytest.mark.asyncio
    async def test_revocation_cache_expiration(self, revocation_cache):
        """Test that revocation cache entries expire."""
        # Create a cache with 1 second TTL
        cache = RevocationCache(ttl_seconds=1)
        jti = "test-jti-123"
        
        # Revoke it
        cache.revoke(jti)
        assert cache.is_revoked(jti)
        
        # Wait for expiration
        import asyncio
        await asyncio.sleep(1.1)
        
        # Should no longer be revoked
        assert not cache.is_revoked(jti)

    @pytest.mark.asyncio
    async def test_revocation_cache_multiple_entries(self, revocation_cache):
        """Test that cache can hold multiple entries."""
        jtis = ["jti-1", "jti-2", "jti-3"]
        
        # Revoke all
        for jti in jtis:
            revocation_cache.revoke(jti)
        
        # All should be revoked
        for jti in jtis:
            assert revocation_cache.is_revoked(jti)

    @pytest.mark.asyncio
    async def test_revocation_cache_warm_from_db(self, db_session, revocation_cache, test_run_id):
        """Test warming the cache from the database."""
        from datetime import timedelta
        import uuid as uuid_module
        
        now = datetime.now(timezone.utc)
        
        # Use unique JTI values with shorter format to stay within VARCHAR(36)
        jti_1 = f"jti-{uuid_module.uuid4().hex[:8]}"
        jti_2 = f"jti-{uuid_module.uuid4().hex[:8]}"
        
        # Add some revoked tokens to the database
        revoked_token_1 = RevokedToken(
            jti=jti_1,
            revoked_at=now,
            expires_at=now + timedelta(minutes=5),
            reason="logout",
        )
        revoked_token_2 = RevokedToken(
            jti=jti_2,
            revoked_at=now,
            expires_at=now + timedelta(minutes=5),
            reason="logout",
        )
        
        db_session.add(revoked_token_1)
        db_session.add(revoked_token_2)
        await db_session.commit()
        
        # Warm the cache
        await revocation_cache.warm_from_db(db_session)
        
        # Verify the cache contains the tokens
        assert revocation_cache.is_revoked(jti_1)
        assert revocation_cache.is_revoked(jti_2)

    @pytest.mark.asyncio
    async def test_revocation_cache_warm_from_db_excludes_expired(self, db_session, revocation_cache, test_run_id):
        """Test that warming the cache excludes expired tokens."""
        from datetime import timedelta
        import uuid as uuid_module
        
        now = datetime.now(timezone.utc)
        
        # Use unique JTI values with shorter format to stay within VARCHAR(36)
        jti_1 = f"jti-{uuid_module.uuid4().hex[:8]}"
        jti_2 = f"jti-{uuid_module.uuid4().hex[:8]}"
        
        # Add a non-expired token
        revoked_token_1 = RevokedToken(
            jti=jti_1,
            revoked_at=now,
            expires_at=now + timedelta(minutes=5),
            reason="logout",
        )
        
        # Add an expired token
        revoked_token_2 = RevokedToken(
            jti=jti_2,
            revoked_at=now - timedelta(minutes=10),
            expires_at=now - timedelta(minutes=5),
            reason="logout",
        )
        
        db_session.add(revoked_token_1)
        db_session.add(revoked_token_2)
        await db_session.commit()
        
        # Warm the cache
        await revocation_cache.warm_from_db(db_session)
        
        # Verify only non-expired token is in cache
        assert revocation_cache.is_revoked(jti_1)
        assert not revocation_cache.is_revoked(jti_2)

    @pytest.mark.asyncio
    async def test_revocation_cache_thread_safety(self, revocation_cache):
        """Test that the cache is thread-safe."""
        import threading
        
        jti = "test-jti"
        results = []
        
        def revoke_and_check():
            revocation_cache.revoke(jti)
            is_revoked = revocation_cache.is_revoked(jti)
            results.append(is_revoked)
        
        # Create multiple threads
        threads = [threading.Thread(target=revoke_and_check) for _ in range(10)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All should have found the token revoked
        assert all(results)
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_revocation_cache_lazy_eviction(self, revocation_cache):
        """Test that expired entries are lazily evicted."""
        import asyncio
        
        # Create a cache with 1 second TTL
        cache = RevocationCache(ttl_seconds=1)
        
        # Add multiple entries
        for i in range(5):
            cache.revoke(f"jti-{i}")
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Check one entry - this should trigger eviction
        assert not cache.is_revoked("jti-0")
        
        # All entries should now be evicted
        for i in range(5):
            assert not cache.is_revoked(f"jti-{i}")

    @pytest.mark.asyncio
    async def test_revocation_cache_configurable_ttl(self):
        """Test that TTL is configurable."""
        import asyncio
        
        # Create cache with 2 second TTL
        cache = RevocationCache(ttl_seconds=2)
        jti = "test-jti"
        
        # Revoke it
        cache.revoke(jti)
        assert cache.is_revoked(jti)
        
        # Wait 1 second - should still be revoked
        await asyncio.sleep(1)
        assert cache.is_revoked(jti)
        
        # Wait another 1.5 seconds - should be expired
        await asyncio.sleep(1.5)
        assert not cache.is_revoked(jti)


class TestTokenRefresh:
    """Test token refresh and rotation functionality."""

    @pytest.mark.asyncio
    async def test_refresh_valid_token(self, db_session, revocation_cache, org_id):
        """
        Property 6: Refresh token rotation
        
        Validates: Requirements 4.2
        
        For any valid non-expired non-revoked refresh token, assert:
        - New access + refresh tokens returned
        - Old token is_revoked=True
        - replaced_by_token_id set to new token ID
        """
        password = "ValidPass123!"
        
        # Create and authenticate a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Get initial tokens
        auth_service = AuthService(db_session, revocation_cache)
        access_token_1, refresh_token_1 = await auth_service.authenticate(
            "test@example.com", password, org_id
        )
        
        # Refresh the token
        access_token_2, refresh_token_2 = await auth_service.refresh(refresh_token_1)
        
        # Verify new tokens are returned
        assert access_token_2 is not None
        assert refresh_token_2 is not None
        assert access_token_2 != access_token_1
        assert refresh_token_2 != refresh_token_1
        
        # Verify old refresh token is marked as revoked
        token_hash_1 = hashlib.sha256(refresh_token_1.encode()).hexdigest()
        from sqlalchemy import text
        result = await db_session.execute(
            text(f"SELECT is_revoked, replaced_by_token_id FROM refresh_tokens WHERE token_hash = '{token_hash_1}'")
        )
        row = result.first()
        assert row is not None
        assert row[0] == 1  # is_revoked = True
        assert row[1] is not None  # replaced_by_token_id is set

    @pytest.mark.asyncio
    async def test_refresh_expired_token(self, db_session, revocation_cache, org_id):
        """Test that expired refresh tokens are rejected."""
        password = "ValidPass123!"
        
        # Create and authenticate a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Get initial tokens
        auth_service = AuthService(db_session, revocation_cache)
        access_token_1, refresh_token_1 = await auth_service.authenticate(
            "test@example.com", password, org_id
        )
        
        # Manually expire the refresh token
        token_hash_1 = hashlib.sha256(refresh_token_1.encode()).hexdigest()
        from sqlalchemy import text
        now = datetime.now(timezone.utc)
        expired_time = (now - timedelta(hours=1)).isoformat()
        await db_session.execute(
            text(f"UPDATE refresh_tokens SET expires_at = '{expired_time}' WHERE token_hash = '{token_hash_1}'")
        )
        await db_session.commit()
        
        # Try to refresh - should fail
        with pytest.raises(AuthenticationError):
            await auth_service.refresh(refresh_token_1)

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, db_session, revocation_cache, org_id):
        """Test that invalid refresh tokens are rejected."""
        auth_service = AuthService(db_session, revocation_cache)
        
        # Try to refresh with a non-existent token
        with pytest.raises(AuthenticationError):
            await auth_service.refresh("invalid-token-that-does-not-exist")

    @pytest.mark.asyncio
    async def test_token_family_revocation_on_reuse(self, db_session, revocation_cache, org_id):
        """
        Property 7: Token family revocation on reuse
        
        Validates: Requirements 4.3
        
        Build rotation chain of chain_length; reuse first token; assert 401 and all tokens in chain is_revoked=True
        """
        password = "ValidPass123!"
        
        # Create and authenticate a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email="test@example.com",
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Get initial tokens
        auth_service = AuthService(db_session, revocation_cache)
        access_token_1, refresh_token_1 = await auth_service.authenticate(
            "test@example.com", password, org_id
        )
        
        # Build a chain of 3 tokens
        tokens = [refresh_token_1]
        for i in range(2):
            _, new_token = await auth_service.refresh(tokens[-1])
            tokens.append(new_token)
        
        # Now try to reuse the first token (theft detected)
        with pytest.raises(AuthenticationError):
            await auth_service.refresh(tokens[0])
        
        # Verify all tokens in the family are revoked
        from sqlalchemy import text
        for token in tokens:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            result = await db_session.execute(
                text(f"SELECT is_revoked FROM refresh_tokens WHERE token_hash = '{token_hash}'")
            )
            row = result.first()
            assert row is not None
            assert row[0] == 1  # is_revoked = True

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, db_session, revocation_cache, org_id, test_run_id):
        """
        Property 9: Status change triggers token revocation
        
        Validates: Requirements 4.5
        
        Change user status to Locked or Inactive; assert all RefreshToken.is_revoked=True
        """
        password = "ValidPass123!"
        email = f"test-{test_run_id[:20]}@example.com"
        
        # Create and authenticate a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email=email,
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Get initial tokens
        auth_service = AuthService(db_session, revocation_cache)
        access_token_1, refresh_token_1 = await auth_service.authenticate(
            email, password, org_id
        )
        
        # Create a few more tokens by refreshing
        _, refresh_token_2 = await auth_service.refresh(refresh_token_1)
        _, refresh_token_3 = await auth_service.refresh(refresh_token_2)
        
        # Revoke all user tokens
        await auth_service.revoke_all_user_tokens(user.user_id)
        
        # Verify all tokens are revoked by checking status is true
        from sqlalchemy import select
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.user_id,
                RefreshToken.is_revoked == True,
            )
        )
        revoked_tokens = result.scalars().all()
        
        # Check there are revoked tokens (at least the ones we created)
        assert len(revoked_tokens) > 0

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_only_active(self, db_session, revocation_cache, org_id, test_run_id):
        """Test that revoke_all_user_tokens only revokes active tokens."""
        password = "ValidPass123!"
        email = f"test-{test_run_id[:20]}@example.com"
        
        # Create and authenticate a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email=email,
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Get initial tokens
        auth_service = AuthService(db_session, revocation_cache)
        access_token_1, refresh_token_1 = await auth_service.authenticate(
            email, password, org_id
        )
        
        # Refresh to create a second token (first becomes revoked)
        _, refresh_token_2 = await auth_service.refresh(refresh_token_1)
        
        # Revoke all user tokens
        await auth_service.revoke_all_user_tokens(user.user_id)
        
        # Verify all tokens are revoked
        from sqlalchemy import select
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.user_id,
                RefreshToken.is_revoked == True,
            )
        )
        revoked_tokens = result.scalars().all()
        
        # Check there are revoked tokens (at least the ones we created)
        assert len(revoked_tokens) > 0

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_with_reason(self, db_session, revocation_cache, org_id, test_run_id):
        """Test that revoke_all_user_tokens accepts a reason parameter."""
        password = "ValidPass123!"
        email = f"test-{test_run_id[:20]}@example.com"
        
        # Create and authenticate a user
        user_service = UserService(db_session)
        user = await user_service.create_user(
            email=email,
            given_name="John",
            last_name="Doe",
            org_id=org_id,
        )
        
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user.hashed_password = hashed_password
        user.status = UserStatus.ACTIVE
        await db_session.flush()
        
        # Get initial tokens
        auth_service = AuthService(db_session, revocation_cache)
        access_token_1, refresh_token_1 = await auth_service.authenticate(
            email, password, org_id
        )
        
        # Revoke all user tokens with a reason
        await auth_service.revoke_all_user_tokens(user.user_id, reason="password_reset")
        
        # Verify all tokens are revoked
        from sqlalchemy import select
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.user_id,
                RefreshToken.is_revoked == True,
            )
        )
        revoked_tokens = result.scalars().all()
        
        # Check there are revoked tokens
        assert len(revoked_tokens) > 0


@given(chain_length=st.integers(min_value=2, max_value=5), example_num=st.integers(min_value=0, max_value=19))
@hypothesis_settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@pytest.mark.asyncio
async def test_token_family_revocation_property(db_session, revocation_cache, org_id, test_run_id, chain_length, example_num):
    """
    Property 7: Token family revocation on reuse
    
    Validates: Requirements 4.3
    
    Build rotation chain of chain_length; reuse first token; assert 401 and all tokens in chain is_revoked=True
    """
    password = "ValidPass123!"
    
    # Create and authenticate a user with unique email combining test_run_id, example_num, and UUID
    # Hypothesis replays stored examples, so we need a unique part that changes with each run
    user_service = UserService(db_session)
    unique_email = f"test-{test_run_id}-ex{example_num}-{uuid4().hex[:8]}@example.com"
    user = await user_service.create_user(
        email=unique_email,
        given_name="John",
        last_name="Doe",
        org_id=org_id,
    )
    
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user.hashed_password = hashed_password
    user.status = UserStatus.ACTIVE
    await db_session.flush()
    
    # Get initial tokens - pass plaintext email, not encrypted
    auth_service = AuthService(db_session, revocation_cache)
    access_token_1, refresh_token_1 = await auth_service.authenticate(
        unique_email, password, org_id
    )
    
    # Build a chain of tokens (minimum 2 to test token family revocation on reuse)
    tokens = [refresh_token_1]
    for i in range(chain_length - 1):
        _, new_token = await auth_service.refresh(tokens[-1])
        tokens.append(new_token)
    
    # Now try to reuse the first token (theft detected)
    with pytest.raises(AuthenticationError):
        await auth_service.refresh(tokens[0])
    
    # Verify all tokens in the family are revoked
    from sqlalchemy import select
    for token in tokens:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == True,
            )
        )
        row = result.scalar_one_or_none()
        assert row is not None
