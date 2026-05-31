"""
Tests for Resume and CandidateJobHistory models.

Feature: candidate-lifecycle
Requirements: 2.1, 2.7
"""

import uuid
from datetime import date, datetime, timezone
import pytest
from hypothesis import given, settings, strategies as st

from app.modules.resumes.models import Resume, CandidateJobHistory, ParseStatus


class TestParseStatus:
    """Test suite for ParseStatus enum."""

    def test_parse_status_values(self):
        """Verify ParseStatus enum has correct values."""
        assert ParseStatus.Pending.value == "Pending"
        assert ParseStatus.Completed.value == "Completed"
        assert ParseStatus.Failed.value == "Failed"

    def test_parse_status_is_string_enum(self):
        """Verify ParseStatus is a string enum."""
        assert isinstance(ParseStatus.Pending, str)
        assert isinstance(ParseStatus.Completed, str)
        assert isinstance(ParseStatus.Failed, str)

    def test_parse_status_members(self):
        """Verify all ParseStatus members are present."""
        members = {member.name for member in ParseStatus}
        assert members == {"Pending", "Completed", "Failed"}


class TestResumeModel:
    """Test suite for Resume model."""

    def test_resume_table_name(self):
        """Verify Resume model has correct table name."""
        assert Resume.__tablename__ == "resumes"

    def test_resume_has_required_columns(self):
        """Verify Resume model has all required columns."""
        required_columns = {
            "resume_id",
            "candidate_id",
            "organization_id",
            "storage_location",
            "mime_type",
            "file_name",
            "file_size_bytes",
            "uploaded_by_user_id",
            "is_primary",
            "parse_status",
            "parsed_data",
            # AuditMixin columns
            "created_at",
            "updated_at",
            "deleted_at",
            "created_by",
            "updated_by",
            "deleted_by",
            # VersionMixin column
            "version",
        }
        model_columns = {col.name for col in Resume.__table__.columns}
        assert required_columns.issubset(model_columns)

    def test_resume_column_types(self):
        """Verify Resume model columns have correct types."""
        columns = {col.name: col for col in Resume.__table__.columns}
        
        # Check key columns
        assert str(columns["resume_id"].type).startswith("UUID")
        assert str(columns["candidate_id"].type).startswith("UUID")
        assert str(columns["organization_id"].type).startswith("UUID")
        assert str(columns["storage_location"].type).startswith("VARCHAR")
        assert str(columns["mime_type"].type).startswith("VARCHAR")
        assert str(columns["file_name"].type).startswith("VARCHAR")
        assert str(columns["file_size_bytes"].type).startswith("INTEGER")
        assert str(columns["uploaded_by_user_id"].type).startswith("UUID")
        assert str(columns["is_primary"].type).startswith("BOOLEAN")
        assert str(columns["parse_status"].type).startswith("VARCHAR")
        assert "JSONB" in str(columns["parsed_data"].type)

    def test_resume_column_nullability(self):
        """Verify Resume model columns have correct nullability."""
        columns = {col.name: col for col in Resume.__table__.columns}
        
        # Non-nullable columns
        assert not columns["resume_id"].nullable
        assert not columns["organization_id"].nullable
        assert not columns["storage_location"].nullable
        assert not columns["mime_type"].nullable
        assert not columns["file_name"].nullable
        assert not columns["file_size_bytes"].nullable
        assert not columns["uploaded_by_user_id"].nullable
        assert not columns["is_primary"].nullable
        assert not columns["parse_status"].nullable
        
        # Nullable columns
        assert columns["candidate_id"].nullable
        assert columns["parsed_data"].nullable
        assert columns["deleted_at"].nullable

    def test_resume_default_values(self):
        """Verify Resume model has correct default values."""
        columns = {col.name: col for col in Resume.__table__.columns}
        
        # Check defaults
        assert columns["is_primary"].default.arg is False
        assert columns["parse_status"].default.arg == ParseStatus.Pending.value

    def test_resume_foreign_keys(self):
        """Verify Resume model has correct foreign keys."""
        fks = list(Resume.__table__.foreign_keys)
        
        # Check that foreign keys exist for the expected columns
        fk_columns = {fk.parent.name for fk in fks}
        assert "candidate_id" in fk_columns
        assert "organization_id" in fk_columns
        assert "uploaded_by_user_id" in fk_columns

    def test_resume_indexes(self):
        """Verify Resume model has correct indexes."""
        index_names = {idx.name for idx in Resume.__table__.indexes}
        
        # Check for partial index on candidate_id
        assert "idx_resumes_candidate" in index_names


class TestCandidateJobHistoryModel:
    """Test suite for CandidateJobHistory model."""

    def test_candidate_job_history_table_name(self):
        """Verify CandidateJobHistory model has correct table name."""
        assert CandidateJobHistory.__tablename__ == "candidate_job_history"

    def test_candidate_job_history_has_required_columns(self):
        """Verify CandidateJobHistory model has all required columns."""
        required_columns = {
            "candidate_job_history_id",
            "candidate_id",
            "organization_id",
            "company_name",
            "job_title",
            "start_date",
            "end_date",
            "description",
            "is_current",
            # AuditMixin columns
            "created_at",
            "updated_at",
            "deleted_at",
            "created_by",
            "updated_by",
            "deleted_by",
            # VersionMixin column
            "version",
        }
        model_columns = {col.name for col in CandidateJobHistory.__table__.columns}
        assert required_columns.issubset(model_columns)

    def test_candidate_job_history_column_types(self):
        """Verify CandidateJobHistory model columns have correct types."""
        columns = {col.name: col for col in CandidateJobHistory.__table__.columns}
        
        # Check key columns
        assert str(columns["candidate_job_history_id"].type).startswith("UUID")
        assert str(columns["candidate_id"].type).startswith("UUID")
        assert str(columns["organization_id"].type).startswith("UUID")
        assert str(columns["company_name"].type).startswith("VARCHAR")
        assert str(columns["job_title"].type).startswith("VARCHAR")
        assert str(columns["start_date"].type).startswith("DATE")
        assert str(columns["end_date"].type).startswith("DATE")
        assert str(columns["description"].type).startswith("VARCHAR")
        assert str(columns["is_current"].type).startswith("BOOLEAN")

    def test_candidate_job_history_column_nullability(self):
        """Verify CandidateJobHistory model columns have correct nullability."""
        columns = {col.name: col for col in CandidateJobHistory.__table__.columns}
        
        # Non-nullable columns
        assert not columns["candidate_job_history_id"].nullable
        assert not columns["candidate_id"].nullable
        assert not columns["organization_id"].nullable
        assert not columns["company_name"].nullable
        assert not columns["job_title"].nullable
        assert not columns["start_date"].nullable
        assert not columns["is_current"].nullable
        
        # Nullable columns
        assert columns["end_date"].nullable
        assert columns["description"].nullable
        assert columns["deleted_at"].nullable

    def test_candidate_job_history_default_values(self):
        """Verify CandidateJobHistory model has correct default values."""
        columns = {col.name: col for col in CandidateJobHistory.__table__.columns}
        
        # Check defaults
        assert columns["is_current"].default.arg is False

    def test_candidate_job_history_foreign_keys(self):
        """Verify CandidateJobHistory model has correct foreign keys."""
        fks = list(CandidateJobHistory.__table__.foreign_keys)
        
        # Check that foreign keys exist for the expected columns
        fk_columns = {fk.parent.name for fk in fks}
        assert "candidate_id" in fk_columns
        assert "organization_id" in fk_columns

    def test_candidate_job_history_column_lengths(self):
        """Verify CandidateJobHistory model columns have correct max lengths."""
        columns = {col.name: col for col in CandidateJobHistory.__table__.columns}
        
        # Check string column lengths
        assert columns["company_name"].type.length == 200
        assert columns["job_title"].type.length == 200
        assert columns["description"].type.length == 2000


class TestResumeModelProperties:
    """Property-based tests for Resume model."""

    @given(
        storage_location=st.text(min_size=1, max_size=1024),
        mime_type=st.sampled_from(["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]),
        file_name=st.text(min_size=1, max_size=255),
        file_size_bytes=st.integers(min_value=1, max_value=10 * 1024 * 1024),
    )
    @settings(max_examples=10)
    def test_resume_column_constraints(self, storage_location, mime_type, file_name, file_size_bytes):
        """
        Property: Resume model columns respect their constraints.
        
        For any valid storage_location, mime_type, file_name, and file_size_bytes,
        the Resume model should accept them without constraint violations.
        
        Validates: Requirements 2.1, 2.7
        """
        # This is a structural test - we're verifying the model definition
        # In a real integration test, we would create a Resume instance
        columns = {col.name: col for col in Resume.__table__.columns}
        
        # Verify column types and lengths
        assert columns["storage_location"].type.length >= len(storage_location)
        assert columns["mime_type"].type.length >= len(mime_type)
        assert columns["file_name"].type.length >= len(file_name)


class TestCandidateJobHistoryModelProperties:
    """Property-based tests for CandidateJobHistory model."""

    @given(
        company_name=st.text(min_size=1, max_size=200),
        job_title=st.text(min_size=1, max_size=200),
        description=st.text(min_size=0, max_size=2000),
    )
    @settings(max_examples=10)
    def test_candidate_job_history_column_constraints(self, company_name, job_title, description):
        """
        Property: CandidateJobHistory model columns respect their constraints.
        
        For any valid company_name, job_title, and description,
        the CandidateJobHistory model should accept them without constraint violations.
        
        Validates: Requirements 2.1, 2.7
        """
        # This is a structural test - we're verifying the model definition
        columns = {col.name: col for col in CandidateJobHistory.__table__.columns}
        
        # Verify column types and lengths
        assert columns["company_name"].type.length >= len(company_name)
        assert columns["job_title"].type.length >= len(job_title)
        assert columns["description"].type.length >= len(description)
