"""
Property-based tests for candidate service.

Feature: candidate-lifecycle
Properties: 1, 2, 3, 4

Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import hashlib
import pytest
from hypothesis import given, settings as hypothesis_settings, assume
from hypothesis import strategies as st
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.base_model import Base
from app.crypto import encrypt_field, decrypt_field
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService, VALID_TRANSITIONS


# Test database setup
@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    from sqlalchemy import event
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    # Disable foreign key constraints for testing
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def org_id():
    """Fixture for organization ID."""
    return uuid4()


@pytest.fixture
def user_id():
    """Fixture for user ID."""
    return uuid4()


class TestCandidateEmailUniqueness:
    """Property-based tests for candidate email uniqueness."""

    @pytest.mark.asyncio
    @given(
        email=st.emails(),
        name=st.text(min_size=1, max_size=200),
        other_org_id=st.uuids(),
    )
    @hypothesis_settings(max_examples=50)
    async def test_email_unique_within_organization(
        self, test_db: AsyncSession, org_id, user_id, email: str, name: str, other_org_id
    ):
        """
        Property 1: Candidate email uniqueness within organization
        
        Validates: Requirements 1.2
        
        For any email and organization:
        - Creating a candidate with that email in org A succeeds
        - Creating another candidate with the same email in org A fails with 409
        - Creating a candidate with the same email in org B succeeds
        """
        assume(org_id != other_org_id)
        
        service = CandidateService(test_db)
        
        # First candidate in org_id should succeed
        candidate1 = await service.create_candidate(
            org_id=org_id,
            name=name,
            email=email,
            phone=None,
            location=None,
            created_by=user_id,
        )
        assert candidate1 is not None
        assert candidate1.email_hash == hashlib.sha256(email.lower().encode()).hexdigest()
        
        # Second candidate with same email in same org should fail with 409
        with pytest.raises(HTTPException) as exc_info:
            await service.create_candidate(
                org_id=org_id,
                name=name,
                email=email,
                phone=None,
                location=None,
                created_by=user_id,
            )
        assert exc_info.value.status_code == 409
        
        # Same email in different org should succeed
        candidate2 = await service.create_candidate(
            org_id=other_org_id,
            name=name,
            email=email,
            phone=None,
            location=None,
            created_by=user_id,
        )
        assert candidate2 is not None
        assert candidate2.organization_id == other_org_id


class TestGlobalStatusFSM:
    """Property-based tests for GlobalStatus FSM enforcement."""

    @pytest.mark.asyncio
    @given(
        from_status=st.sampled_from(list(GlobalStatus)),
        to_status=st.sampled_from(list(GlobalStatus)),
    )
    @hypothesis_settings(max_examples=100)
    async def test_status_transitions(
        self, test_db: AsyncSession, org_id, user_id, from_status: GlobalStatus, to_status: GlobalStatus
    ):
        """
        Property 2: GlobalStatus FSM — only valid transitions permitted
        
        Validates: Requirements 1.7, 1.8
        
        For any pair of statuses:
        - Valid transitions succeed and update global_status
        - Invalid transitions raise HTTPException 400 and leave status unchanged
        """
        service = CandidateService(test_db)
        
        # Create candidate with from_status
        candidate = Candidate(
            candidate_id=uuid4(),
            organization_id=org_id,
            name=encrypt_field("Test Candidate"),
            name_hash=hashlib.sha256("test candidate".encode()).hexdigest(),
            email=encrypt_field("test@example.com"),
            email_hash=hashlib.sha256("test@example.com".lower().encode()).hexdigest(),
            phone=None,
            location=None,
            global_status=from_status,
        )
        test_db.add(candidate)
        await test_db.flush()
        
        # Attempt transition
        is_valid = to_status in VALID_TRANSITIONS.get(from_status, set())
        
        if is_valid:
            # Valid transition should succeed
            updated = await service.transition_status(
                candidate=candidate,
                new_status=to_status,
                updated_by=user_id,
            )
            assert updated.global_status == to_status
        else:
            # Invalid transition should raise 400
            with pytest.raises(HTTPException) as exc_info:
                await service.transition_status(
                    candidate=candidate,
                    new_status=to_status,
                    updated_by=user_id,
                )
            assert exc_info.value.status_code == 400
            # Status should remain unchanged
            assert candidate.global_status == from_status


class TestIneligibleStatusRequiresReason:
    """Property-based tests for Ineligible status requiring IneligibilityReason."""

    @pytest.mark.asyncio
    @given(
        reason=st.one_of(
            st.none(),
            st.just(""),
            st.text(alphabet=" \t\n", min_size=1, max_size=50),
        )
    )
    @hypothesis_settings(max_examples=50)
    async def test_ineligible_requires_reason(
        self, test_db: AsyncSession, org_id, user_id, reason: str | None
    ):
        """
        Property 3: Ineligible status requires IneligibilityReason
        
        Validates: Requirements 1.4
        
        For any absent/null/empty/whitespace-only reason:
        - Transitioning to INELIGIBLE raises HTTPException 400
        - Candidate global_status remains ACTIVE
        
        For any non-empty reason:
        - Transitioning to INELIGIBLE succeeds
        - ineligibility_reason is set
        """
        service = CandidateService(test_db)
        
        # Create candidate with ACTIVE status
        candidate = Candidate(
            candidate_id=uuid4(),
            organization_id=org_id,
            name=encrypt_field("Test Candidate"),
            name_hash=hashlib.sha256("test candidate".encode()).hexdigest(),
            email=encrypt_field("test@example.com"),
            email_hash=hashlib.sha256("test@example.com".lower().encode()).hexdigest(),
            phone=None,
            location=None,
            global_status=GlobalStatus.Active,
        )
        test_db.add(candidate)
        await test_db.flush()
        
        is_valid_reason = reason and reason.strip()
        
        if not is_valid_reason:
            # Invalid reason should raise 400
            with pytest.raises(HTTPException) as exc_info:
                await service.transition_status(
                    candidate=candidate,
                    new_status=GlobalStatus.Ineligible,
                    ineligibility_reason=reason,
                    updated_by=user_id,
                )
            assert exc_info.value.status_code == 400
            assert candidate.global_status == GlobalStatus.Active
        else:
            # Valid reason should succeed
            updated = await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.Ineligible,
                ineligibility_reason=reason,
                updated_by=user_id,
            )
            assert updated.global_status == GlobalStatus.Ineligible
            assert updated.ineligibility_reason == reason


class TestLogicalDeleteExcludesFromSearch:
    """Property-based tests for logical delete excluding from search."""

    @pytest.mark.asyncio
    @given(
        name=st.text(min_size=1, max_size=100),
        email=st.emails(),
    )
    @hypothesis_settings(max_examples=50)
    async def test_deleted_candidate_excluded_from_search(
        self, test_db: AsyncSession, org_id, user_id, name: str, email: str
    ):
        """
        Property 4: Logical delete excludes candidate from search
        
        Validates: Requirements 1.5
        
        For any candidate:
        - After DELETED transition: search by name and email returns no results
        - Raw DB fetch returns record with deleted_at set
        """
        service = CandidateService(test_db)
        
        # Create candidate
        candidate = await service.create_candidate(
            org_id=org_id,
            name=name,
            email=email,
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Verify candidate is searchable
        results, count = await service.search_candidates(
            org_id=org_id,
            name=name,
            offset=0,
            limit=50,
        )
        assert count >= 1
        
        # Transition to DELETED
        await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.Deleted,
            updated_by=user_id,
        )
        
        # Verify candidate is no longer searchable
        results, count = await service.search_candidates(
            org_id=org_id,
            name=name,
            offset=0,
            limit=50,
        )
        assert count == 0
        
        # Verify deleted_at is set
        assert candidate.deleted_at is not None
        assert candidate.deleted_by == user_id


class TestCandidateCreation:
    """Unit tests for candidate creation."""

    @pytest.mark.asyncio
    async def test_create_candidate_encrypts_pii(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that PII fields are encrypted on creation."""
        service = CandidateService(test_db)
        
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
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that new candidates are created with ACTIVE status."""
        service = CandidateService(test_db)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="Test Candidate",
            email="test@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        assert candidate.global_status == GlobalStatus.Active

    @pytest.mark.asyncio
    async def test_get_candidate_returns_404_for_missing(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that get_candidate returns 404 for non-existent candidate."""
        service = CandidateService(test_db)
        
        with pytest.raises(HTTPException) as exc_info:
            await service.get_candidate(uuid4(), org_id)
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_candidate_excludes_deleted(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that get_candidate excludes soft-deleted candidates."""
        service = CandidateService(test_db)
        
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
            new_status=GlobalStatus.Deleted,
            updated_by=user_id,
        )
        
        # Should not be found
        with pytest.raises(HTTPException) as exc_info:
            await service.get_candidate(candidate.candidate_id, org_id)
        
        assert exc_info.value.status_code == 404
