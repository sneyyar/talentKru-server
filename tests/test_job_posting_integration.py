"""
Integration tests for job posting.

Feature: candidate-lifecycle
Tasks: 17.3 - Job posting integration tests

Requirements: 4.3, 4.4, 4.5
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_profile.models import JobProfile
from app.modules.job_profile.service import JobProfileService
from app.modules.job_profile.schemas import JobProfileCreate
from app.modules.job_posting.models import JobPosting
from app.modules.job_posting.service import JobPostingService


class TestJobPostingSalaryFilterIntegration:
    """Integration tests for job posting salary filtering."""

    @pytest.mark.asyncio
    async def test_salary_overlap_filter_overlapping_ranges(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test: Salary overlap filter - overlapping ranges."""
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        user_id = uuid4()
        
        # Create job profile
        profile_data = JobProfileCreate(
            name=f"Software Engineer-{test_run_id}",
            skills=[],
        )
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=user_id,
        )
        
        # Create posting with description and locations
        posting = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            description="Senior Software Engineer role",
            work_locations=["San Francisco, CA"],
            salary_min=Decimal("50000"),
            salary_max=Decimal("70000"),
            salary_currency="USD",
            sourcing_channel="LinkedIn",
        )
        
        # Verify posting was created
        assert posting.job_posting_id is not None
        assert posting.organization_id == org_id
        assert posting.salary_min == Decimal("50000")
        assert posting.salary_max == Decimal("70000")

    @pytest.mark.asyncio
    async def test_salary_overlap_filter_boundary_conditions(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test: Salary overlap filter - boundary conditions."""
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        user_id = uuid4()
        
        # Create job profile
        profile_data = JobProfileCreate(
            name=f"Software Engineer-{test_run_id}",
            skills=[],
        )
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=user_id,
        )
        
        # Create posting at boundary
        posting = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            description="Engineer role",
            work_locations=["New York, NY"],
            salary_min=Decimal("50000"),
            salary_max=Decimal("70000"),
            salary_currency="USD",
            sourcing_channel="Indeed",
        )
        
        # Verify posting
        assert posting.job_posting_id is not None
        assert posting.salary_min == Decimal("50000")
        assert posting.salary_max == Decimal("70000")

    @pytest.mark.asyncio
    async def test_salary_overlap_filter_partial_overlap(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test: Salary overlap filter - partial overlap."""
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        user_id = uuid4()
        
        # Create job profile
        profile_data = JobProfileCreate(
            name=f"Software Engineer-{test_run_id}",
            skills=[],
        )
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=user_id,
        )
        
        # Create posting with salary range
        posting = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            description="Engineer role",
            work_locations=["Austin, TX"],
            salary_min=Decimal("50000"),
            salary_max=Decimal("70000"),
            salary_currency="USD",
            sourcing_channel="Glassdoor",
        )
        
        # Verify posting
        assert posting.job_posting_id is not None
        assert posting.salary_min == Decimal("50000")
        assert posting.salary_max == Decimal("70000")

    @pytest.mark.asyncio
    async def test_salary_filter_with_multiple_postings(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test: Salary filter with multiple postings."""
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        user_id = uuid4()
        
        # Create job profile
        profile_data = JobProfileCreate(
            name=f"Software Engineer-{test_run_id}",
            skills=[],
        )
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            data=profile_data,
            created_by=user_id,
        )
        
        # Create multiple postings with different salary ranges
        salary_ranges = [
            (Decimal("40000"), Decimal("60000")),
            (Decimal("50000"), Decimal("70000")),
            (Decimal("60000"), Decimal("80000")),
        ]
        
        postings = []
        for i, (min_sal, max_sal) in enumerate(salary_ranges):
            posting = await posting_service.create_posting(
                org_id=org_id,
                job_profile_id=profile.job_profile_id,
                description=f"Engineer role {i+1}",
                work_locations=["San Francisco, CA"],
                salary_min=min_sal,
                salary_max=max_sal,
                salary_currency="USD",
                sourcing_channel="LinkedIn",
            )
            postings.append(posting)
        
        # Verify postings were created
        assert len(postings) == 3
        assert all(p.job_posting_id is not None for p in postings)
        assert postings[0].salary_min == Decimal("40000")
        assert postings[1].salary_min == Decimal("50000")
        assert postings[2].salary_min == Decimal("60000")
