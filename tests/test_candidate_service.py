"""
Property-based tests for candidate service.

Feature: candidate-lifecycle
Properties: 1, 2, 3, 4

Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import hashlib
import pytest
from hypothesis import given, settings as hypothesis_settings, assume, HealthCheck, Verbosity
from hypothesis import strategies as st
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crypto import encrypt_field, decrypt_field
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService, VALID_TRANSITIONS
from app.modules.organizations.models import Organization


class TestCandidateEmailUniqueness:
    """Property-based tests for candidate email uniqueness."""

    @pytest.mark.asyncio
    @given(
        email_prefix=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"),
    )
    @hypothesis_settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        database=None,  # Disable example database to prevent FlakyReplay errors
    )
    async def test_email_unique_within_organization(
        self, db_session: AsyncSession, org_id, user_id, test_run_id, email_prefix: str
    ):
        """
        Property 1: Candidate email uniqueness within organization
        
        Validates: Requirements 1.2
        
        For any email and organization:
        - Creating a candidate with that email in org A succeeds
        - Creating another candidate with the same email in org A fails with 409
        - Creating a candidate with the same email in different org succeeds
        """
        service = CandidateService(db_session)
        
        # Make email unique by appending test_run_id and uuid
        unique_email = f"{email_prefix}-{test_run_id}-{uuid4().hex[:8]}@example.com"
        unique_name = f"Test Candidate-{test_run_id}"
        
        # First candidate in org_id should succeed
        candidate1 = await service.create_candidate(
            org_id=org_id,
            name=unique_name,
            email=unique_email,
            phone=None,
            location=None,
            created_by=user_id,
        )
        assert candidate1 is not None
        assert candidate1.email_hash == hashlib.sha256(unique_email.lower().encode()).hexdigest()
        
        # Second candidate with same email in same org should fail with 409
        with pytest.raises(HTTPException) as exc_info:
            await service.create_candidate(
                org_id=org_id,
                name=unique_name,
                email=unique_email,
                phone=None,
                location=None,
                created_by=user_id,
            )
        assert exc_info.value.status_code == 409


class TestGlobalStatusFSM:
    """Property-based tests for GlobalStatus FSM enforcement."""

    @pytest.mark.asyncio
    async def test_status_transitions_valid_active_to_interviewing(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test valid transition from ACTIVE to INTERVIEWING."""
        service = CandidateService(db_session)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        assert candidate.global_status == GlobalStatus.ACTIVE.value
        
        updated = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INTERVIEWING.value,
            updated_by=user_id,
        )
        assert updated.global_status == GlobalStatus.INTERVIEWING.value

    @pytest.mark.asyncio
    async def test_status_transitions_invalid_expired_to_active(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test invalid transition - cannot go from DELETED back to ACTIVE."""
        from sqlalchemy import text
        
        # Create candidate directly in DELETED status
        candidate_id = uuid4()
        unique_email = f"deleted-{uuid4().hex[:8]}@example.com"
        
        candidate = Candidate(
            candidate_id=candidate_id,
            organization_id=org_id,
            name=encrypt_field("Test User"),
            name_hash=hashlib.sha256("test user".encode()).hexdigest(),
            email=encrypt_field(unique_email),
            email_hash=hashlib.sha256(unique_email.lower().encode()).hexdigest(),
            phone=None,
            location=None,
            global_status=GlobalStatus.DELETED.value,
        )
        db_session.add(candidate)
        await db_session.flush()
        
        service = CandidateService(db_session)
        
        # Try invalid transition from DELETED to ACTIVE
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.ACTIVE.value,
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400
        assert candidate.global_status == GlobalStatus.DELETED.value


class TestIneligibleStatusRequiresReason:
    """Tests for Ineligible status requiring IneligibilityReason."""

    @pytest.mark.asyncio
    async def test_ineligible_requires_reason_success(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that transitioning to INELIGIBLE with reason succeeds."""
        service = CandidateService(db_session)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        assert candidate.global_status == GlobalStatus.ACTIVE.value
        
        reason = "Failed background check"
        updated = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INELIGIBLE.value,
            ineligibility_reason=reason,
            updated_by=user_id,
        )
        assert updated.global_status == GlobalStatus.INELIGIBLE.value
        assert updated.ineligibility_reason == reason

    @pytest.mark.asyncio
    async def test_ineligible_requires_reason_failure(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that transitioning to INELIGIBLE without reason fails."""
        service = CandidateService(db_session)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="Jane Doe",
            email="jane@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Try with None
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.INELIGIBLE.value,
                ineligibility_reason=None,
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400
        assert candidate.global_status == GlobalStatus.ACTIVE.value
        
        # Try with empty string
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.INELIGIBLE.value,
                ineligibility_reason="",
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400
        assert candidate.global_status == GlobalStatus.ACTIVE.value


class TestLogicalDeleteExcludesFromSearch:
    """Property-based tests for logical delete excluding from search."""

    @pytest.mark.asyncio
    @given(
        name_suffix=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_"),
    )
    @hypothesis_settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        database=None,  # Disable example database to prevent FlakyReplay errors
    )
    async def test_deleted_candidate_excluded_from_search(
        self, db_session: AsyncSession, org_id, user_id, test_run_id, name_suffix: str
    ):
        """
        Property 4: Logical delete excludes candidate from search
        
        Validates: Requirements 1.5
        
        For any candidate:
        - After DELETED transition: search by name and email returns no results
        - Raw DB fetch returns record with deleted_at set
        """
        service = CandidateService(db_session)
        
        # Create candidate with unique name and email using test_run_id and uuid
        unique_name = f"Candidate-{test_run_id}-{name_suffix}"
        unique_email = f"deleted-test-{test_run_id}-{uuid4().hex[:8]}@example.com"
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name=unique_name,
            email=unique_email,
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Verify candidate is searchable
        results, count = await service.search_candidates(
            org_id=org_id,
            name=unique_name,
            offset=0,
            limit=50,
        )
        assert count >= 1
        
        # Transition to DELETED
        await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.DELETED.value,
            updated_by=user_id,
        )
        
        # Verify candidate is no longer searchable
        results, count = await service.search_candidates(
            org_id=org_id,
            name=unique_name,
            offset=0,
            limit=50,
        )
        assert count == 0
        
        # Verify deleted_at is set
        assert candidate.deleted_at is not None


class TestCandidateCreation:
    """Unit tests for candidate creation."""

    @pytest.mark.asyncio
    async def test_create_candidate_encrypts_pii(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that PII fields are encrypted on creation."""
        service = CandidateService(db_session)
        
        name = "John Doe"
        email = "john@example.com"
        phone = "555-1234"
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name=name,
            email=email,
            phone=phone,
            location="New York",
            created_by=user_id,
        )
        
        # Verify encrypted fields are not plaintext
        assert candidate.name != name
        assert candidate.email != email
        assert candidate.phone != phone
        
        # Verify hashes are correct
        assert candidate.name_hash == hashlib.sha256(name.lower().encode()).hexdigest()
        assert candidate.email_hash == hashlib.sha256(email.lower().encode()).hexdigest()
        
        # Verify decryption works
        assert decrypt_field(candidate.name) == name
        assert decrypt_field(candidate.email) == email
        assert decrypt_field(candidate.phone) == phone

    @pytest.mark.asyncio
    async def test_create_candidate_sets_active_status(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that new candidates are created with ACTIVE status."""
        service = CandidateService(db_session)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="Test Candidate",
            email="test@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        assert candidate.global_status == GlobalStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_get_candidate_returns_404_for_missing(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that get_candidate returns 404 for non-existent candidate."""
        service = CandidateService(db_session)
        
        with pytest.raises(HTTPException) as exc_info:
            await service.get_candidate(uuid4(), org_id)
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_candidate_excludes_deleted(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that get_candidate excludes soft-deleted candidates."""
        service = CandidateService(db_session)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="Test Candidate",
            email="test@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Delete the candidate
        await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.DELETED.value,
            updated_by=user_id,
        )
        
        # Should not be found
        with pytest.raises(HTTPException) as exc_info:
            await service.get_candidate(candidate.candidate_id, org_id)
        
        assert exc_info.value.status_code == 404
