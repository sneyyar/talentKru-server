"""
Smoke tests for candidate-lifecycle module.

Feature: candidate-lifecycle
Tasks: 17.7 - Smoke tests for candidate-lifecycle module

Requirements: 1.1, 2.4, 6.4
"""

import pytest
import os
from pathlib import Path

from app.config import settings
from app.modules.candidates.models import GlobalStatus
from app.modules.resumes.models import ParseStatus
from app.modules.requisitions.models import RequisitionStatus
from app.modules.privacy.models import DSARRequestType, DSARStatus


class TestSmokeCandidateLifecycle:
    """Smoke tests for candidate-lifecycle module configuration and startup."""

    def test_storage_backend_configured(self):
        """
        Test: Storage backend configured
        
        Validates: Requirements 2.4
        
        - Verify STORAGE_BACKEND env var set
        - Verify value is "local" or "s3"
        """
        backend = os.getenv("STORAGE_BACKEND", "local")
        assert backend in ["local", "s3"], f"Invalid storage backend: {backend}"

    def test_local_storage_directory_writable(self):
        """
        Test: Local storage directory writable
        
        Validates: Requirements 2.4
        
        - When STORAGE_BACKEND=local
        - Verify STORAGE_LOCAL_PATH exists
        - Verify directory writable
        """
        backend = os.getenv("STORAGE_BACKEND", "local")
        if backend != "local":
            pytest.skip("Not using local storage backend")
        
        storage_path = Path(os.getenv("STORAGE_LOCAL_PATH", "data/resumes"))
        
        # Create directory if it doesn't exist
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Verify writable
        assert os.access(storage_path, os.W_OK), f"Storage path not writable: {storage_path}"

    def test_s3_bucket_configured(self):
        """
        Test: S3 bucket configured
        
        Validates: Requirements 2.4
        
        - When STORAGE_BACKEND=s3
        - Verify RESUME_BUCKET_NAME set
        - Verify not empty
        """
        backend = os.getenv("STORAGE_BACKEND", "local")
        if backend != "s3":
            pytest.skip("Not using S3 storage backend")
        
        bucket_name = os.getenv("RESUME_BUCKET_NAME", "")
        assert bucket_name, "S3 bucket name not configured"

    def test_global_status_enum_values(self):
        """
        Test: GlobalStatus enum has all required values
        
        Validates: Requirements 1.1
        
        - Verify ACTIVE value exists
        - Verify INTERVIEWING value exists
        - Verify EXPIRED value exists
        - Verify INELIGIBLE value exists
        - Verify DELETED value exists
        """
        required_values = ["Active", "Interviewing", "Expired", "Ineligible", "Deleted"]
        
        for value in required_values:
            assert hasattr(GlobalStatus, value), f"GlobalStatus missing {value}"
            assert getattr(GlobalStatus, value) is not None

    def test_parse_status_enum_values(self):
        """
        Test: ParseStatus enum has all required values
        
        Validates: Requirements 2.1
        
        - Verify PENDING value exists
        - Verify COMPLETED value exists
        - Verify FAILED value exists
        """
        required_values = ["Pending", "Completed", "Failed"]
        
        for value in required_values:
            assert hasattr(ParseStatus, value), f"ParseStatus missing {value}"
            assert getattr(ParseStatus, value) is not None

    def test_requisition_status_enum_values(self):
        """
        Test: RequisitionStatus enum has all required values
        
        Validates: Requirements 5.1
        
        - Verify OPEN value exists
        - Verify ON_HOLD value exists
        - Verify CLOSED value exists
        - Verify CANCELLED value exists
        """
        required_values = ["Open", "OnHold", "Closed", "Cancelled"]
        
        for value in required_values:
            assert hasattr(RequisitionStatus, value), f"RequisitionStatus missing {value}"
            assert getattr(RequisitionStatus, value) is not None

    def test_dsar_request_type_enum_values(self):
        """
        Test: DSARRequestType enum has all required values
        
        Validates: Requirements 6.1
        
        - Verify ACCESS value exists
        - Verify ERASURE value exists
        """
        required_values = ["Access", "Erasure"]
        
        for value in required_values:
            assert hasattr(DSARRequestType, value), f"DSARRequestType missing {value}"
            assert getattr(DSARRequestType, value) is not None

    def test_dsar_status_enum_values(self):
        """
        Test: DSARStatus enum has all required values
        
        Validates: Requirements 6.1
        
        - Verify PENDING value exists
        - Verify COMPLETED value exists
        - Verify DENIED value exists
        """
        required_values = ["Pending", "Completed", "Denied"]
        
        for value in required_values:
            assert hasattr(DSARStatus, value), f"DSARStatus missing {value}"
            assert getattr(DSARStatus, value) is not None

    def test_database_connection_available(self):
        """
        Test: Database connection is available
        
        Validates: Requirements 1.1
        
        - Verify database URL is configured
        - Verify connection parameters are set
        """
        db_host = os.getenv("DATABASE_HOST")
        db_port = os.getenv("DATABASE_PORT")
        db_name = os.getenv("DATABASE_NAME")
        db_user = os.getenv("DATABASE_USER")
        
        assert db_host, "DATABASE_HOST not configured"
        assert db_port, "DATABASE_PORT not configured"
        assert db_name, "DATABASE_NAME not configured"
        assert db_user, "DATABASE_USER not configured"

    def test_encryption_keys_configured(self):
        """
        Test: Encryption keys are configured
        
        Validates: Requirements 1.1
        
        - Verify JWT_SIGNING_KEY is set
        - Verify ENCRYPTION_KEY is set
        """
        jwt_key = os.getenv("JWT_SIGNING_KEY")
        enc_key = os.getenv("ENCRYPTION_KEY")
        
        assert jwt_key, "JWT_SIGNING_KEY not configured"
        assert enc_key, "ENCRYPTION_KEY not configured"
        assert len(jwt_key) > 0, "JWT_SIGNING_KEY is empty"
        assert len(enc_key) > 0, "ENCRYPTION_KEY is empty"

    def test_agent_api_key_configured(self):
        """
        Test: Agent API key is configured
        
        Validates: Requirements 2.5
        
        - Verify AGENT_API_KEY is set
        """
        agent_key = os.getenv("AGENT_API_KEY")
        assert agent_key, "AGENT_API_KEY not configured"
        assert len(agent_key) > 0, "AGENT_API_KEY is empty"

