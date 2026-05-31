"""Minimal test for candidate service."""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event

from app.base_model import Base
from app.modules.candidates.models import Candidate, GlobalStatus
from app.domain_events.models import DomainEvent


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


@pytest.mark.asyncio
async def test_candidate_model_creation(test_db: AsyncSession):
    """Test that we can create a candidate in the database."""
    from app.crypto import encrypt_field
    import hashlib
    
    org_id = uuid4()
    name = "Test Candidate"
    email = "test@example.com"
    
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
    
    test_db.add(candidate)
    await test_db.flush()
    
    assert candidate.candidate_id is not None
    assert candidate.global_status == GlobalStatus.ACTIVE.value
