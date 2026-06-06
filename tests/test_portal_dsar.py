"""
Tests for portal DSAR creation functionality.

Feature: candidate-lifecycle
Task: 13.1 - Implement portal DSAR creation

Requirements: 6.1
"""

import pytest
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.portal.service import PortalService
from app.modules.privacy.models import DataSubjectAccessRequest, DSARStatus, DSARRequestType
from app.modules.candidates.service import CandidateService


class TestPortalDSARCreation:
    """Tests for portal DSAR creation functionality."""

    @pytest.mark.asyncio
    async def test_create_dsar_access_request(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test creating a DSAR with RequestType=Access.
        
        Validates: Requirements 6.1
        
        - DSAR is created with status=PENDING
        - requested_at is set to current time
        - request_type is set to ACCESS
        """
        # Create a candidate first
        candidate_service = CandidateService(db_session)
        user_id = uuid4()
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        service = PortalService(db_session)
        
        dsar = await service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type="ACCESS",
        )
        
        assert dsar.dsar_id is not None
        assert dsar.candidate_id == candidate.candidate_id
        assert dsar.organization_id == org_id
        assert dsar.request_type == DSARRequestType.ACCESS.value
        assert dsar.status == DSARStatus.PENDING.value
        assert dsar.requested_at is not None
        assert isinstance(dsar.requested_at, datetime)
        assert dsar.completed_at is None
        assert dsar.denial_reason is None

    @pytest.mark.asyncio
    async def test_create_dsar_erasure_request(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test creating a DSAR with RequestType=Erasure.
        
        Validates: Requirements 6.1
        
        - DSAR is created with status=PENDING
        - request_type is set to ERASURE
        """
        # Create a candidate first
        candidate_service = CandidateService(db_session)
        user_id = uuid4()
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        service = PortalService(db_session)
        
        dsar = await service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type="ERASURE",
        )
        
        assert dsar.dsar_id is not None
        assert dsar.candidate_id == candidate.candidate_id
        assert dsar.organization_id == org_id
        assert dsar.request_type == DSARRequestType.ERASURE.value
        assert dsar.status == DSARStatus.PENDING.value
        assert dsar.requested_at is not None

    @pytest.mark.asyncio
    async def test_dsar_persisted_to_database(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test that DSAR is persisted to the database.
        
        Validates: Requirements 6.1
        
        - After creating a DSAR, it can be retrieved from the database
        """
        # Create a candidate first
        candidate_service = CandidateService(db_session)
        user_id = uuid4()
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        service = PortalService(db_session)
        
        dsar = await service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type="ACCESS",
        )
        
        dsar_id = dsar.dsar_id
        
        # Retrieve from database
        result = await db_session.execute(
            select(DataSubjectAccessRequest).where(
                DataSubjectAccessRequest.dsar_id == dsar_id
            )
        )
        retrieved = result.scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.dsar_id == dsar_id
        assert retrieved.candidate_id == candidate.candidate_id
        assert retrieved.organization_id == org_id
        assert retrieved.request_type == DSARRequestType.ACCESS.value
        assert retrieved.status == DSARStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_multiple_dsars_for_same_candidate(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test creating multiple DSARs for the same candidate.
        
        Validates: Requirements 6.1
        
        - Multiple DSARs can be created for the same candidate
        - Each DSAR has a unique ID
        """
        # Create a candidate first
        candidate_service = CandidateService(db_session)
        user_id = uuid4()
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        service = PortalService(db_session)
        
        dsar1 = await service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type="ACCESS",
        )
        
        dsar2 = await service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type="ERASURE",
        )
        
        assert dsar1.dsar_id != dsar2.dsar_id
        assert dsar1.request_type == DSARRequestType.ACCESS.value
        assert dsar2.request_type == DSARRequestType.ERASURE.value
        assert dsar1.status == DSARStatus.PENDING.value
        assert dsar2.status == DSARStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_dsar_audit_fields_populated(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """
        Test that DSAR audit fields are populated.
        
        Validates: Requirements 6.1
        
        - created_at is set
        - updated_at is set
        - deleted_at is None
        """
        # Create a candidate first
        candidate_service = CandidateService(db_session)
        user_id = uuid4()
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name=f"Test Candidate {test_run_id}",
            email=f"candidate-{test_run_id}@example.com",
            created_by=user_id,
        )
        
        service = PortalService(db_session)
        
        dsar = await service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type="ACCESS",
        )
        
        assert dsar.created_at is not None
        assert dsar.updated_at is not None
        assert dsar.deleted_at is None
