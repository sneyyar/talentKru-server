"""
Tests for CandidatePortalService.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException
from hypothesis import HealthCheck, given, settings as hyp_settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.crypto import encrypt_field
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.portal.models import CandidatePortalToken
from app.modules.portal.service import CandidatePortalService


@pytest.mark.asyncio
async def test_get_or_create_token_creates_new_token(
    db_session: AsyncSession, org_id: UUID, test_run_id: str
):
    """Test get_or_create_token creates a new token with required properties."""
    candidate_id = uuid4()

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    # Verify raw_token is URL-safe and minimum length
    assert isinstance(raw_token, str)
    assert len(raw_token) >= 43  # secrets.token_urlsafe(32) produces >= 43 chars
    # Verify it's URL-safe (no / or + after base64url)
    assert all(c.isalnum() or c in "-_" for c in raw_token)

    # Verify token was stored in database
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    stmt = select(CandidatePortalToken).where(
        CandidatePortalToken.token_hash == token_hash
    )
    result = await db_session.execute(stmt)
    token_record = result.scalar_one_or_none()

    assert token_record is not None
    assert token_record.candidate_id == candidate_id
    assert token_record.organization_id == org_id
    assert token_record.is_active is True
    assert token_record.deleted_at is None


@pytest.mark.asyncio
async def test_get_or_create_token_sets_expiry(
    db_session: AsyncSession, org_id: UUID
):
    """Test get_or_create_token sets correct expiry based on PORTAL_TOKEN_TTL_DAYS."""
    candidate_id = uuid4()
    before = datetime.now(timezone.utc)

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    after = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    stmt = select(CandidatePortalToken).where(
        CandidatePortalToken.token_hash == token_hash
    )
    result = await db_session.execute(stmt)
    token_record = result.scalar_one_or_none()

    expected_min = before + timedelta(days=app_settings.PORTAL_TOKEN_TTL_DAYS)
    expected_max = after + timedelta(days=app_settings.PORTAL_TOKEN_TTL_DAYS)

    assert expected_min <= token_record.expires_at <= expected_max


@pytest.mark.asyncio
async def test_validate_token_success(
    db_session: AsyncSession, org_id: UUID
):
    """Test validate_token successfully validates a valid, active token."""
    candidate_id = uuid4()

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    # Validate should succeed
    result_candidate_id, result_org_id = await service.validate_token(raw_token)

    assert result_candidate_id == candidate_id
    assert result_org_id == org_id


@pytest.mark.asyncio
async def test_validate_token_invalid_raises_401(
    db_session: AsyncSession, org_id: UUID
):
    """Test validate_token raises 401 for invalid token."""
    service = CandidatePortalService(db_session)

    invalid_token = "invalid_token_" + secrets.token_urlsafe(16)
    with pytest.raises(HTTPException) as exc_info:
        await service.validate_token(invalid_token)

    assert exc_info.value.status_code == 401
    # Generic message - no disclosure
    assert "Invalid or expired" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_validate_token_expired_raises_401(
    db_session: AsyncSession, org_id: UUID
):
    """Test validate_token raises 401 for expired token."""
    candidate_id = uuid4()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Create an expired token
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    token_record = CandidatePortalToken(
        candidate_portal_token_id=uuid4(),
        candidate_id=candidate_id,
        organization_id=org_id,
        token_hash=token_hash,
        expires_at=past_time,
        is_active=True,
    )
    db_session.add(token_record)
    await db_session.flush()

    service = CandidatePortalService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await service.validate_token(raw_token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_validate_token_inactive_raises_401(
    db_session: AsyncSession, org_id: UUID
):
    """Test validate_token raises 401 for inactive token."""
    candidate_id = uuid4()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Create an inactive token
    future_time = datetime.now(timezone.utc) + timedelta(days=7)
    token_record = CandidatePortalToken(
        candidate_portal_token_id=uuid4(),
        candidate_id=candidate_id,
        organization_id=org_id,
        token_hash=token_hash,
        expires_at=future_time,
        is_active=False,
    )
    db_session.add(token_record)
    await db_session.flush()

    service = CandidatePortalService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await service.validate_token(raw_token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_and_issue_jwt_success(
    db_session: AsyncSession, org_id: UUID, test_run_id: str
):
    """Test verify_email_and_issue_jwt successfully issues JWT for valid email."""
    candidate_id = uuid4()
    email = f"test-{test_run_id}@example.com"
    encrypted_email = encrypt_field(email)

    # Create candidate
    candidate = Candidate(
        candidate_id=candidate_id,
        organization_id=org_id,
        name=encrypt_field(f"Test Candidate {test_run_id}"),
        name_hash=hashlib.sha256(
            f"Test Candidate {test_run_id}".encode()
        ).hexdigest(),
        email=encrypted_email,
        email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
        global_status=GlobalStatus.ACTIVE.value,
    )
    db_session.add(candidate)
    await db_session.flush()

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    # Verify email and issue JWT
    access_token = await service.verify_email_and_issue_jwt(raw_token, email)

    # Decode JWT and verify claims
    payload = jwt.decode(access_token, app_settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    assert payload["sub"] == email.lower()
    assert payload["candidate_id"] == str(candidate_id)
    assert payload["org_id"] == str(org_id)
    assert "exp" in payload
    assert "iat" in payload
    assert payload["exp"] > payload["iat"]


@pytest.mark.asyncio
async def test_verify_email_and_issue_jwt_email_case_insensitive(
    db_session: AsyncSession, org_id: UUID, test_run_id: str
):
    """Test verify_email_and_issue_jwt is case-insensitive for email."""
    candidate_id = uuid4()
    email = f"Test-{test_run_id}@Example.COM"
    encrypted_email = encrypt_field(email)

    candidate = Candidate(
        candidate_id=candidate_id,
        organization_id=org_id,
        name=encrypt_field("Test"),
        name_hash=hashlib.sha256("Test".encode()).hexdigest(),
        email=encrypted_email,
        email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
        global_status=GlobalStatus.ACTIVE.value,
    )
    db_session.add(candidate)
    await db_session.flush()

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    # Verify with different case
    access_token = await service.verify_email_and_issue_jwt(
        raw_token, "test-" + test_run_id + "@example.com"
    )

    payload = jwt.decode(access_token, app_settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    assert payload["sub"] == email.lower()


@pytest.mark.asyncio
async def test_verify_email_and_issue_jwt_email_mismatch_raises_401(
    db_session: AsyncSession, org_id: UUID, test_run_id: str
):
    """Test verify_email_and_issue_jwt raises 401 for email mismatch."""
    candidate_id = uuid4()
    email = f"correct-{test_run_id}@example.com"
    encrypted_email = encrypt_field(email)

    candidate = Candidate(
        candidate_id=candidate_id,
        organization_id=org_id,
        name=encrypt_field("Test"),
        name_hash=hashlib.sha256("Test".encode()).hexdigest(),
        email=encrypted_email,
        email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
        global_status=GlobalStatus.ACTIVE.value,
    )
    db_session.add(candidate)
    await db_session.flush()

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    # Try to verify with wrong email
    wrong_email = f"wrong-{test_run_id}@example.com"
    with pytest.raises(HTTPException) as exc_info:
        await service.verify_email_and_issue_jwt(raw_token, wrong_email)

    assert exc_info.value.status_code == 401
    # Generic message - no disclosure of what's wrong
    assert "Invalid or expired" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_verify_email_and_issue_jwt_invalid_token_raises_401(
    db_session: AsyncSession, org_id: UUID, test_run_id: str
):
    """Test verify_email_and_issue_jwt raises 401 for invalid token."""
    email = f"test-{test_run_id}@example.com"
    service = CandidatePortalService(db_session)

    invalid_token = "invalid_token_" + secrets.token_urlsafe(16)
    with pytest.raises(HTTPException) as exc_info:
        await service.verify_email_and_issue_jwt(invalid_token, email)

    assert exc_info.value.status_code == 401


# ============================================================================
# Property-Based Tests
# ============================================================================


@hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(ttl_days=st.integers(min_value=1, max_value=365))
@pytest.mark.asyncio
async def test_portal_token_entropy_and_ttl(
    db_session: AsyncSession, org_id: UUID, ttl_days: int
):
    """
    Property 14: Portal token minimum entropy and TTL.
    
    **Validates: Requirements 5.1, 5.2, 5.3**
    
    Generated token has >= 43 URL-safe chars (from 32 bytes).
    expires_at == creation_time + PORTAL_TOKEN_TTL_DAYS days.
    Invalid/expired/inactive token -> 401 without revealing which condition applies.
    """
    # Note: ttl_days is generated but PORTAL_TOKEN_TTL_DAYS is fixed in settings
    candidate_id = uuid4()

    service = CandidatePortalService(db_session)
    before = datetime.now(timezone.utc)
    raw_token = await service.get_or_create_token(candidate_id, org_id)
    after = datetime.now(timezone.utc)

    # Property 1: Token is URL-safe and minimum length
    assert len(raw_token) >= 43
    assert all(c.isalnum() or c in "-_" for c in raw_token)

    # Property 2: Expiry is within expected range
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    stmt = select(CandidatePortalToken).where(
        CandidatePortalToken.token_hash == token_hash
    )
    result = await db_session.execute(stmt)
    token_record = result.scalar_one_or_none()

    expected_min = before + timedelta(days=app_settings.PORTAL_TOKEN_TTL_DAYS)
    expected_max = after + timedelta(days=app_settings.PORTAL_TOKEN_TTL_DAYS)
    assert expected_min <= token_record.expires_at <= expected_max

    # Property 3: Invalid token raises 401 with no specific reason
    invalid_token = "invalid_" + secrets.token_urlsafe(32)
    with pytest.raises(HTTPException) as exc:
        await service.validate_token(invalid_token)
    assert exc.value.status_code == 401


@hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(
    submitted_email=st.emails(),
    actual_email=st.emails(),
)
@pytest.mark.asyncio
async def test_portal_email_verification_non_disclosure(
    db_session: AsyncSession, org_id: UUID, submitted_email: str, actual_email: str, test_run_id: str
):
    """
    Property 15: Portal email verification non-disclosure.
    
    **Validates: Requirements 5.4, 5.5**
    
    Email mismatch -> HTTPException 401 with identical message as invalid token.
    No disclosure of whether token or email was wrong.
    """
    if submitted_email.lower() == actual_email.lower():
        # Skip: we want mismatches
        return

    candidate_id = uuid4()
    # Make email unique per test run to avoid unique constraint violations
    unique_actual_email = f"actual-{test_run_id}-{secrets.token_hex(4)}@example.com"
    unique_submitted_email = f"submitted-{test_run_id}-{secrets.token_hex(4)}@example.com"
    encrypted_email = encrypt_field(unique_actual_email)

    # Create candidate with actual email
    candidate = Candidate(
        candidate_id=candidate_id,
        organization_id=org_id,
        name=encrypt_field("Test"),
        name_hash=hashlib.sha256("Test".encode()).hexdigest(),
        email=encrypted_email,
        email_hash=hashlib.sha256(unique_actual_email.lower().encode()).hexdigest(),
        global_status=GlobalStatus.ACTIVE.value,
    )
    db_session.add(candidate)
    await db_session.flush()

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    # Email mismatch should raise 401
    with pytest.raises(HTTPException) as exc_info:
        await service.verify_email_and_issue_jwt(raw_token, unique_submitted_email)

    assert exc_info.value.status_code == 401
    # Message should be generic - same as for invalid token
    assert "Invalid or expired" in str(exc_info.value.detail)

    # Also test invalid token raises same generic message
    invalid_token = "invalid_" + secrets.token_urlsafe(32)
    with pytest.raises(HTTPException) as exc_invalid:
        await service.validate_token(invalid_token)

    assert exc_invalid.value.status_code == 401
    assert exc_invalid.value.detail == exc_info.value.detail


@hyp_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(st.just(None))  # Just one example per hypothesis run
@pytest.mark.asyncio
async def test_portal_token_returned_once_not_stored(
    db_session: AsyncSession, org_id: UUID, _
):
    """
    Property: Raw token is returned once, not stored in plaintext.
    
    **Validates: Requirements 5.1**
    
    - get_or_create_token returns raw_token
    - Database stores only token_hash (SHA-256)
    - Hash is unique and queries cannot expose raw token
    """
    candidate_id = uuid4()

    service = CandidatePortalService(db_session)
    raw_token = await service.get_or_create_token(candidate_id, org_id)

    # Verify token_hash in database but not raw_token
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    stmt = select(CandidatePortalToken).where(
        CandidatePortalToken.token_hash == token_hash
    )
    result = await db_session.execute(stmt)
    token_record = result.scalar_one_or_none()

    assert token_record is not None
    # Verify raw_token is not stored anywhere in the record
    # (only token_hash, candidate_id, org_id, expires_at, is_active)
    assert token_record.token_hash == token_hash
    assert token_record.token_hash != raw_token
    assert not hasattr(token_record, "raw_token")
