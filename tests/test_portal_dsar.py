"""
Tests for portal DSAR creation functionality.

Feature: candidate-lifecycle
Task: 13.1 - Implement portal DSAR creation

Requirements: 6.1
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event

from app.base_model import Base
from app.modules.portal.service import PortalService
from app.modules.privacy.models import DataSubjectAccessRequest, DSARStatus, DSARRequestType


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
def candidate_id():
    """Fixture for candidate ID."""
    return uuid4()


@pytest.fixture
def org_id():
    """Fixture for organization ID."""
    return uuid4()


class TestPortalDSARCreation:
    """Tests for portal DSAR creation functionality."""

    @pytest.mark.asyncio
    async def test_create_dsar_access_request(
        self, test_db: AsyncSession, candidate_id, org_id
    ):
        """
        Test creating a DSAR with RequestType=Access.
        
        Validates: Requirements 6.1
        
        - DSAR is created with status=PENDING
        - requested_at is set to current time
        - request_type is set to ACCESS
        """
        service = PortalService(test_db)
        
        dsar = await service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type="access",
        )
        
        assert dsar.dsar_id is not None
        assert dsar.candidate_id == candidate_id
        assert dsar.organization_id == org_id
        assert dsar.request_type == DSARRequestType.ACCESS.value
        assert dsar.status == DSARStatus.PENDING.value
        assert dsar.requested_at is not None
        assert isinstance(dsar.requested_at, datetime)
        assert dsar.completed_at is None
        assert dsar.denial_reason is None

    @pytest.mark.asyncio
    async def test_create_dsar_erasure_request(
        self, test_db: AsyncSession, candidate_id, org_id
    ):
        """
        Test creating a DSAR with RequestType=Erasure.
        
        Validates: Requirements 6.1
        
        - DSAR is created with status=PENDING
        - request_type is set to ERASURE
        """
        service = PortalService(test_db)
        
        dsar = await service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type="erasure",
        )
        
        assert dsar.dsar_id is not None
        assert dsar.candidate_id == candidate_id
        assert dsar.organization_id == org_id
        assert dsar.request_type == DSARRequestType.ERASURE.value
        assert dsar.status == DSARStatus.PENDING.value
        assert dsar.requested_at is not None

    @pytest.mark.asyncio
    async def test_dsar_persisted_to_database(
        self, test_db: AsyncSession, candidate_id, org_id
    ):
        """
        Test that DSAR is persisted to the database.
        
        Validates: Requirements 6.1
        
        - After creating a DSAR, it can be retrieved from the database
        """
        service = PortalService(test_db)
        
        dsar = await service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type="access",
        )
        
        dsar_id = dsar.dsar_id
        
        # Retrieve from database
        retrieved = await test_db.get(DataSubjectAccessRequest, dsar_id)
        
        assert retrieved is not None
        assert retrieved.dsar_id == dsar_id
        assert retrieved.candidate_id == candidate_id
        assert retrieved.organization_id == org_id
        assert retrieved.request_type == DSARRequestType.ACCESS.value
        assert retrieved.status == DSARStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_multiple_dsars_for_same_candidate(
        self, test_db: AsyncSession, candidate_id, org_id
    ):
        """
        Test creating multiple DSARs for the same candidate.
        
        Validates: Requirements 6.1
        
        - Multiple DSARs can be created for the same candidate
        - Each DSAR has a unique ID
        """
        service = PortalService(test_db)
        
        dsar1 = await service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type="access",
        )
        
        dsar2 = await service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type="erasure",
        )
        
        assert dsar1.dsar_id != dsar2.dsar_id
        assert dsar1.request_type == DSARRequestType.ACCESS.value
        assert dsar2.request_type == DSARRequestType.ERASURE.value
        assert dsar1.status == DSARStatus.PENDING.value
        assert dsar2.status == DSARStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_dsar_audit_fields_populated(
        self, test_db: AsyncSession, candidate_id, org_id
    ):
        """
        Test that DSAR audit fields are populated.
        
        Validates: Requirements 6.1
        
        - created_at is set
        - updated_at is set
        - deleted_at is None
        """
        service = PortalService(test_db)
        
        dsar = await service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type="access",
        )
        
        assert dsar.created_at is not None
        assert dsar.updated_at is not None
        assert dsar.deleted_at is None
