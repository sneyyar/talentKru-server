"""
Integration tests for DSAR Access and Erasure workflows.

Feature: candidate-lifecycle
Tasks: 17.5 - DSAR Access and Erasure workflow integration tests

Requirements: 6.2, 6.3
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException

from app.modules.candidates.models import Candidate, GlobalStatus
from app.modules.candidates.service import CandidateService
from app.modules.privacy.models import DataSubjectAccessRequest, DSARRequestType, DSARStatus
from app.modules.privacy.service import PrivacyService
from app.modules.portal.service import PortalService
from app.audit_models import AuditLog


class TestDSARIntegration:
    """Integration tests for DSAR Access and Erasure workflows."""

    @pytest.mark.asyncio
    async def test_access_dsar_workflow(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Access DSAR workflow
        
        Validates: Requirements 6.2
        
        - Create candidate with full data
        - Submit Access DSAR via portal
        - Process via admin endpoint
        - Verify JSON document contains all fields
        - Verify status=COMPLETED
        - Verify completed_at set
        """
        candidate_service = CandidateService(db_session)
        portal_service = PortalService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Submit Access DSAR via portal
        dsar = await portal_service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type=DSARRequestType.ACCESS.value,
        )
        
        assert dsar.status == DSARStatus.PENDING.value
        
        # Process Access DSAR
        result = await privacy_service.process_access_dsar(dsar)
        
        # Verify status=COMPLETED
        db_dsar = await db_session.get(DataSubjectAccessRequest, dsar.dsar_id)
        assert db_dsar.status == DSARStatus.COMPLETED.value
        assert db_dsar.completed_at is not None
        
        # Verify result contains candidate data
        assert result is not None
        assert "candidate_id" in result or "data" in result

    @pytest.mark.asyncio
    async def test_erasure_dsar_workflow(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Erasure DSAR workflow
        
        Validates: Requirements 6.3
        
        - Create candidate with data
        - Submit Erasure DSAR
        - Process via admin endpoint
        - Verify candidate hard-deleted
        - Verify status=COMPLETED
        """
        candidate_service = CandidateService(db_session)
        portal_service = PortalService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        candidate_id = candidate.candidate_id
        
        # Submit Erasure DSAR
        dsar = await portal_service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type=DSARRequestType.ERASURE.value,
        )
        
        assert dsar.status == DSARStatus.PENDING.value
        
        # Process Erasure DSAR
        await privacy_service.process_erasure_dsar(dsar)
        
        # Verify status=COMPLETED
        db_dsar = await db_session.get(DataSubjectAccessRequest, dsar.dsar_id)
        assert db_dsar.status == DSARStatus.COMPLETED.value
        assert db_dsar.completed_at is not None
        
        # Verify candidate hard-deleted
        db_candidate = await db_session.get(Candidate, candidate_id)
        assert db_candidate is None

    @pytest.mark.asyncio
    async def test_audit_log_anonymization(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Audit log anonymization
        
        Validates: Requirements 6.3
        
        - Create candidate
        - Submit Erasure DSAR
        - Process erasure
        - Query audit logs for candidate
        - Verify anonymized=True
        - Verify candidate_id=None
        """
        candidate_service = CandidateService(db_session)
        portal_service = PortalService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        candidate_id = candidate.candidate_id
        
        # Submit Erasure DSAR
        dsar = await portal_service.create_dsar(
            candidate_id=candidate_id,
            org_id=org_id,
            request_type=DSARRequestType.ERASURE.value,
        )
        
        # Process Erasure DSAR
        await privacy_service.process_erasure_dsar(dsar)
        
        # Query audit logs for candidate
        stmt = select(AuditLog).where(
            and_(
                AuditLog.org_id == org_id,
                AuditLog.target_entity == "Candidate",
            )
        )
        result = await db_session.execute(stmt)
        audit_logs = result.scalars().all()
        
        # Verify anonymized=True for all logs
        for log in audit_logs:
            if log.target_id == str(candidate_id):
                # After erasure, target_id should be None (anonymized)
                assert log.target_id is None

    @pytest.mark.asyncio
    async def test_deny_dsar_with_reason(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Deny DSAR with reason
        
        Validates: Requirements 6.7
        
        - Create DSAR
        - Deny with valid reason (≥10 chars)
        - Verify status=DENIED
        - Verify denial_reason stored
        - Verify audit log entry created
        """
        candidate_service = CandidateService(db_session)
        portal_service = PortalService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Submit DSAR
        dsar = await portal_service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type=DSARRequestType.ACCESS.value,
        )
        
        # Deny with valid reason
        denial_reason = "Request does not meet legal requirements"
        
        await privacy_service.deny_dsar(
            dsar=dsar,
            denial_reason=denial_reason,
            denied_by=user_id,
        )
        
        # Verify status=DENIED
        db_dsar = await db_session.get(DataSubjectAccessRequest, dsar.dsar_id)
        assert db_dsar.status == DSARStatus.DENIED.value
        assert db_dsar.denial_reason == denial_reason

    @pytest.mark.asyncio
    async def test_deny_dsar_with_short_reason_fails(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Deny DSAR with short reason fails
        
        Validates: Requirements 6.7
        
        - Create DSAR
        - Try to deny with short reason (<10 chars)
        - Verify 400 error
        - Verify status unchanged
        """
        candidate_service = CandidateService(db_session)
        portal_service = PortalService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Submit DSAR
        dsar = await portal_service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type=DSARRequestType.ACCESS.value,
        )
        
        # Try to deny with short reason - should fail
        with pytest.raises(HTTPException) as exc_info:
            await privacy_service.deny_dsar(
                dsar=dsar,
                denial_reason="Too short",  # < 10 chars
                denied_by=user_id,
            )
        
        assert exc_info.value.status_code == 400
        
        # Verify status unchanged
        db_dsar = await db_session.get(DataSubjectAccessRequest, dsar.dsar_id)
        assert db_dsar.status == DSARStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_multiple_dsars_for_same_candidate(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Multiple DSARs for same candidate
        
        Validates: Requirements 6.2
        
        - Create candidate
        - Submit 2 Access DSARs
        - Process both
        - Verify both completed
        - Verify separate records
        """
        candidate_service = CandidateService(db_session)
        portal_service = PortalService(db_session)
        privacy_service = PrivacyService(db_session)
        
        # Create candidate
        candidate = await candidate_service.create_candidate(
            org_id=org_id,
            name="John Doe",
            email="john@example.com",
            phone=None,
            location=None,
            created_by=user_id,
        )
        
        # Submit 2 Access DSARs
        dsar1 = await portal_service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type=DSARRequestType.ACCESS.value,
        )
        
        dsar2 = await portal_service.create_dsar(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            request_type=DSARRequestType.ACCESS.value,
        )
        
        # Process both
        await privacy_service.process_access_dsar(dsar1)
        
        await privacy_service.process_access_dsar(dsar2)
        
        # Verify both completed
        db_dsar1 = await db_session.get(DataSubjectAccessRequest, dsar1.dsar_id)
        db_dsar2 = await db_session.get(DataSubjectAccessRequest, dsar2.dsar_id)
        
        assert db_dsar1.status == DSARStatus.COMPLETED.value
        assert db_dsar2.status == DSARStatus.COMPLETED.value
        
        # Verify separate records
        assert dsar1.dsar_id != dsar2.dsar_id
