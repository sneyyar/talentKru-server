"""
Simple unit tests for candidate service.

Feature: candidate-lifecycle
Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import hashlib
import pytest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_field, decrypt_field
from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService


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
    async def test_create_candidate_email_uniqueness(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that email must be unique within organization."""
        service = CandidateService(db_session)
        
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
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that get_candidate returns 404 for non-existent candidate."""
        service = CandidateService(db_session)
        
        with pytest.raises(HTTPException) as exc_info:
            await service.get_candidate(uuid4(), org_id)
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_transition_to_ineligible_requires_reason(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that transitioning to INELIGIBLE requires a reason."""
        service = CandidateService(db_session)
        
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
                new_status=GlobalStatus.INELIGIBLE.value,
                ineligibility_reason=None,
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400
        
        # Transition with whitespace-only reason should fail
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.INELIGIBLE.value,
                ineligibility_reason="   ",
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400
        
        # Transition with valid reason should succeed
        updated = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INELIGIBLE.value,
            ineligibility_reason="Does not meet requirements",
            updated_by=user_id,
        )
        assert updated.global_status == GlobalStatus.INELIGIBLE.value
        assert updated.ineligibility_reason == "Does not meet requirements"

    @pytest.mark.asyncio
    async def test_transition_invalid_status_raises_400(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that invalid status transitions raise 400."""
        service = CandidateService(db_session)
        
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
            new_status=GlobalStatus.INELIGIBLE.value,
            ineligibility_reason="Test reason",
            updated_by=user_id,
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.ACTIVE.value,
                updated_by=user_id,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_transition_to_deleted_sets_deleted_fields(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that transitioning to DELETED sets deleted_at and deleted_by."""
        from app.base_model import current_user_id_var
        
        service = CandidateService(db_session)
        
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
        
        # Set the context variable so the before_flush listener can set deleted_by
        token = current_user_id_var.set(str(user_id))
        try:
            await service.transition_status(
                candidate=candidate,
                new_status=GlobalStatus.DELETED.value,
                updated_by=user_id,
            )
        finally:
            current_user_id_var.reset(token)
        
        assert candidate.deleted_at is not None
        assert candidate.deleted_by == user_id

    @pytest.mark.asyncio
    async def test_deleted_candidate_excluded_from_search(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """Test that deleted candidates are excluded from search."""
        service = CandidateService(db_session)
        
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
            new_status=GlobalStatus.DELETED.value,
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
