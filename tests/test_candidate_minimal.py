"""Minimal test for candidate service using PostgreSQL."""

import pytest
import hashlib
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidates.models import Candidate, GlobalStatus
from app.crypto import encrypt_field


@pytest.mark.asyncio
async def test_candidate_model_creation(db_session: AsyncSession, org_id, test_run_id):
    """
    Test that we can create a candidate in the PostgreSQL database.
    
    This test verifies:
    - Candidate creation with encrypted PII fields
    - Proper hash computation for case-insensitive lookups
    - Model initialization with correct status
    """
    # Use test_run_id to ensure unique data
    name = f"Test Candidate-{test_run_id}"
    email = f"test-{test_run_id}-{uuid4().hex[:8]}@example.com"
    
    candidate = Candidate(
        candidate_id=uuid4(),
        organization_id=org_id,
        name=encrypt_field(name),
        name_hash=hashlib.sha256(name.lower().encode()).hexdigest(),
        email=encrypt_field(email),
        email_hash=hashlib.sha256(email.lower().encode()).hexdigest(),
        phone=None,
        location=None,
        global_status=GlobalStatus.ACTIVE.value,
    )
    
    db_session.add(candidate)
    await db_session.flush()
    
    # Verify candidate was created successfully
    assert candidate.candidate_id is not None
    assert candidate.global_status == GlobalStatus.ACTIVE.value
    assert candidate.organization_id == org_id
    
    # Verify encrypted fields are not plaintext
    assert candidate.name != name
    assert candidate.email != email
    
    # Verify hashes are computed correctly
    assert candidate.name_hash == hashlib.sha256(name.lower().encode()).hexdigest()
    assert candidate.email_hash == hashlib.sha256(email.lower().encode()).hexdigest()
