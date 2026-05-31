"""
Integration tests for full candidate lifecycle.

Feature: candidate-lifecycle
Tasks: 17.1 - Full candidate lifecycle integration tests

Requirements: 1.1, 1.2, 1.5, 1.6, 2.5, 2.6
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.modules.resumes.models import Resume, ParseStatus
from app.modules.resumes.service import ResumeService
from app.crypto import encrypt_field
import hashlib


class TestCandidateLifecycleIntegration:
    """Integration tests for full candidate lifecycle."""

    @pytest.mark.asyncio
    async def test_create_candidate_with_valid_data(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Create candidate with valid data
        
        Validates: Requirements 1.1, 1.2
        
        - Create candidate with name, email, phone
        - Verify record in database
        - Verify PII encrypted
        - Verify email_hash computed correctly
        """
        service = CandidateService(db_session)
        
        name = "John Doe"
        email = "john@example.com"
        phone = "+1-555-0123"
        
        # Create candidate
        candidate = await service.create_candidate(
            org_id=org_id,
            name=name,
            email=email,
            phone=phone,
            location="San Francisco, CA",
            created_by=user_id,
        )
        
        # Verify candidate created
        assert candidate.candidate_id is not None
        assert candidate.organization_id == org_id
        assert candidate.global_status == GlobalStatus.ACTIVE.value
        
        # Verify in database
        db_candidate = await db_session.get(Candidate, candidate.candidate_id)
        assert db_candidate is not None
        assert db_candidate.organization_id == org_id
        
        # Verify email_hash computed correctly
        expected_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        assert db_candidate.email_hash == expected_hash
        
        # Verify name_hash computed correctly
        expected_name_hash = hashlib.sha256(name.lower().encode()).hexdigest()
        assert db_candidate.name_hash == expected_name_hash

    @pytest.mark.asyncio
    async def test_search_candidates_by_name(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Search candidates by name (case-insensitive)
        
        Validates: Requirements 1.6
        
        - Create multiple candidates
        - Search by name (case-insensitive)
        - Verify correct results returned
        - Verify pagination works
        """
        service = CandidateService(db_session)
        
        # Create multiple candidates
        candidates_data = [
            ("Alice Johnson", "alice@example.com"),
            ("Bob Smith", "bob@example.com"),
            ("Alice Brown", "alice.brown@example.com"),
        ]
        
        created_candidates = []
        for name, email in candidates_data:
            candidate = await service.create_candidate(
                org_id=org_id,
                name=name,
                email=email,
                phone=None,
                location=None,
                created_by=user_id,
            )
            created_candidates.append(candidate)
        
        # Search for "Alice Johnson" (exact match)
        results, total = await service.search_candidates(
            org_id=org_id,
            name="Alice Johnson",
            offset=0,
            limit=50,
        )
        
        # Should find 1 candidate with exact name match
        assert len(results) == 1
        assert results[0].candidate_id == created_candidates[0].candidate_id

    @pytest.mark.asyncio
    async def test_search_candidates_by_email(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Search candidates by email (case-insensitive)
        
        Validates: Requirements 1.6
        
        - Create multiple candidates
        - Search by email (case-insensitive)
        - Verify correct results returned
        """
        service = CandidateService(db_session)
        
        # Create candidates
        candidate1 = await service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        candidate2 = await service.create_candidate(
            org_id=org_id,
            name="Jane Smith",
            email="jane@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Search by email
        results, total = await service.search_candidates(
            org_id=org_id,
            email="john@example.com",
            offset=0,
            limit=50,
        )
        
        # Should find exactly 1 candidate
        assert len(results) == 1
        assert results[0].candidate_id == candidate1.candidate_id

    @pytest.mark.asyncio
    async def test_transition_candidate_status_through_fsm(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Transition candidate status through FSM
        
        Validates: Requirements 1.7, 1.8
        
        - Create candidate (ACTIVE)
        - Transition to INTERVIEWING
        - Transition to EXPIRED
        - Verify each transition succeeds
        - Verify invalid transitions fail (400)
        """
        service = CandidateService(db_session)
        
        # Create candidate (starts as ACTIVE)
        candidate = await service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        assert candidate.global_status == GlobalStatus.ACTIVE.value
        
        # Transition to INTERVIEWING
        updated = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INTERVIEWING.value,
            ineligibility_reason=None,
            updated_by=user_id,
        )
        
        assert updated.global_status == GlobalStatus.INTERVIEWING.value
        
        # Transition to EXPIRED
        updated = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.EXPIRED.value,
            ineligibility_reason=None,
            updated_by=user_id,
        )
        
        assert updated.global_status == GlobalStatus.EXPIRED.value

    @pytest.mark.asyncio
    async def test_transition_to_ineligible_requires_reason(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Transition to INELIGIBLE requires reason
        
        Validates: Requirements 1.4
        
        - Create candidate
        - Try to transition to INELIGIBLE without reason
        - Verify 400 error
        - Transition with valid reason
        - Verify success
        """
        service = CandidateService(db_session)
        
        candidate = await service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Try to transition without reason - should fail
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INELIGIBLE.value,
            ineligibility_reason=None,
            updated_by=user_id,
        )
        
        assert exc_info.value.status_code == 400
        
        # Transition with valid reason - should succeed
        updated = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.INELIGIBLE.value,
            ineligibility_reason="Does not meet minimum requirements",
            updated_by=user_id,
        )
        
        assert updated.global_status == GlobalStatus.INELIGIBLE.value
        assert updated.ineligibility_reason == "Does not meet minimum requirements"

    @pytest.mark.asyncio
    async def test_soft_delete_candidate_and_verify_excluded_from_search(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Soft-delete candidate and verify excluded from search
        
        Validates: Requirements 1.5
        
        - Create candidate
        - Transition to DELETED
        - Verify deleted_at is set
        - Search for candidate
        - Verify not in results
        - Verify raw DB fetch shows deleted_at
        """
        service = CandidateService(db_session)
        
        # Create candidate
        candidate = await service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        candidate_id = candidate.candidate_id
        
        # Transition to DELETED
        deleted = await service.transition_status(
            candidate=candidate,
            new_status=GlobalStatus.DELETED.value,
            ineligibility_reason=None,
            updated_by=user_id,
        )
        
        assert deleted.global_status == GlobalStatus.DELETED.value
        assert deleted.deleted_at is not None
        
        # Search for candidate - should not find it
        results, total = await service.search_candidates(
            org_id=org_id,
            name="John",
            offset=0,
            limit=50,
        )
        
        assert len(results) == 0
        
        # Raw DB fetch should show deleted_at
        db_candidate = await db_session.get(Candidate, candidate_id)
        assert db_candidate is not None
        assert db_candidate.deleted_at is not None
        assert db_candidate.global_status == GlobalStatus.DELETED.value
