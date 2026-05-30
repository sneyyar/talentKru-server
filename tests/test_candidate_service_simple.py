"""
Simple unit tests for candidate service.

Feature: candidate-lifecycle
Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import hashlib
import pytest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event

from app.base_model import Base
from app.crypto import encrypt_field, decrypt_field
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.domain_events.models import DomainEvent  # Import to register model


# Test database setup
@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
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
        
        assert candidate.global_status == GlobalStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_candidate_email_uniqueness(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that email must be unique within organization."""
        service = CandidateService(test_db)
        
        email = "test@example.com"
        
        # First candidate should succeed
        candidate1 = await service.create_candidate(
            org_id=org_id,
            name="Test Candidate 1",
            email=email,
            phone=None,
            location=None,
            created_by=user_id,
        )
        assert candidate1 is not None
        
        # Second candidate with same email should fail
        with pytest.raises(HTTPException) as exc_info:
            await service.create_candidate(
                org_id=org_id,
                name="Test Candidate 2",
                email=email,
                phone=None,
                location=None,
                created_by=user_id,
            )
        assert exc_info.value.status_code == 409

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
    async def test_transition_to_ineligible_requires_reason(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that transitioning to INELIGIBLE requires a reason."""
        service = CandidateService(test_db)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="Test Candidate",
            email="test@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Transition without reason should fail
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.INELIGIBLE,
                ineligibility_reason=None,
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400
        
        # Transition with whitespace-only reason should fail
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.INELIGIBLE,
                ineligibility_reason="   ",
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400
        
        # Transition with valid reason should succeed
        updated = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INELIGIBLE,
            ineligibility_reason="Does not meet requirements",
            updated_by=user_id,
        )
        assert updated.global_status == GlobalStatus.INELIGIBLE
        assert updated.ineligibility_reason == "Does not meet requirements"

    @pytest.mark.asyncio
    async def test_transition_invalid_status_raises_400(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that invalid status transitions raise 400."""
        service = CandidateService(test_db)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="Test Candidate",
            email="test@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # INELIGIBLE cannot transition to ACTIVE
        await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INELIGIBLE,
            ineligibility_reason="Test reason",
            updated_by=user_id,
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.ACTIVE,
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_transition_to_deleted_sets_deleted_fields(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that transitioning to DELETED sets deleted_at and deleted_by."""
        service = CandidateService(test_db)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="Test Candidate",
            email="test@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        assert candidate.deleted_at is None
        assert candidate.deleted_by is None
        
        await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.DELETED,
            updated_by=user_id,
        )
        
        assert candidate.deleted_at is not None
        assert candidate.deleted_by == user_id

    @pytest.mark.asyncio
    async def test_deleted_candidate_excluded_from_search(
        self, test_db: AsyncSession, org_id, user_id
    ):
        """Test that deleted candidates are excluded from search."""
        service = CandidateService(test_db)
        
        name = "Test Candidate"
        email = "test@example.com"
        
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
        
        # Delete the candidate
        await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.DELETED,
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
            new_status=GlobalStatus.DELETED,
            updated_by=user_id,
        )
        
        # Should not be found
        with pytest.raises(HTTPException) as exc_info:
            await service.get_candidate(candidate.candidate_id, org_id)
        
        assert exc_info.value.status_code == 404
