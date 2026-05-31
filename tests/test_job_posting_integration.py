"""
Integration tests for job posting salary overlap filter.

Feature: candidate-lifecycle
Tasks: 17.3 - Job posting salary overlap filter integration tests

Requirements: 4.5
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.job_profile.models import JobProfile
from app.modules.job_profile.service import JobProfileService
from app.modules.job_posting.models import JobPosting
from app.modules.job_posting.service import JobPostingService


class TestJobPostingSalaryFilterIntegration:
    """Integration tests for job posting salary overlap filtering."""

    @pytest.mark.asyncio
    async def test_salary_overlap_filter_overlapping_ranges(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Salary overlap filter - overlapping ranges
        
        Validates: Requirements 4.5
        
        - Create postings with salary ranges:
          - Posting A: 50k-70k
          - Posting B: 60k-80k
          - Posting C: 90k-110k
        - Filter with range 65k-75k
        - Verify A and B returned, C excluded
        """
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create postings with different salary ranges
        posting_a = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Engineer A",
            salary_min=Decimal("50000"),
            salary_max=Decimal("70000"),
            salary_currency="USD",
            created_by=user_id,
        )
        
        posting_b = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Engineer B",
            salary_min=Decimal("60000"),
            salary_max=Decimal("80000"),
            salary_currency="USD",
            created_by=user_id,
        )
        
        posting_c = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Senior Engineer C",
            salary_min=Decimal("90000"),
            salary_max=Decimal("110000"),
            salary_currency="USD",
            created_by=user_id,
        )
        
        # Filter with range 65k-75k
        results = await posting_service.list_postings(
            org_id=org_id,
            salary_filter_min=Decimal("65000"),
            salary_filter_max=Decimal("75000"),
            page=1,
            page_size=50,
        )
        
        # Should find A and B, not C
        assert len(results) == 2
        posting_ids = {p.job_posting_id for p in results}
        assert posting_a.job_posting_id in posting_ids
        assert posting_b.job_posting_id in posting_ids
        assert posting_c.job_posting_id not in posting_ids

    @pytest.mark.asyncio
    async def test_salary_overlap_filter_boundary_conditions(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Salary overlap filter - boundary conditions
        
        Validates: Requirements 4.5
        
        - Create posting: 50k-70k
        - Filter with exact boundaries: 50k-70k
        - Verify posting returned
        - Filter with 70k-90k (no overlap)
        - Verify posting excluded
        """
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create posting: 50k-70k
        posting = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Engineer",
            salary_min=Decimal("50000"),
            salary_max=Decimal("70000"),
            salary_currency="USD",
            created_by=user_id,
        )
        
        # Filter with exact boundaries: 50k-70k
        results = await posting_service.list_postings(
            org_id=org_id,
            salary_filter_min=Decimal("50000"),
            salary_filter_max=Decimal("70000"),
            page=1,
            page_size=50,
        )
        
        # Should find posting
        assert len(results) == 1
        assert results[0].job_posting_id == posting.job_posting_id
        
        # Filter with 70k-90k (no overlap)
        results = await posting_service.list_postings(
            org_id=org_id,
            salary_filter_min=Decimal("70000"),
            salary_filter_max=Decimal("90000"),
            page=1,
            page_size=50,
        )
        
        # Should not find posting (no overlap)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_salary_overlap_filter_partial_overlap(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Salary overlap filter - partial overlap
        
        Validates: Requirements 4.5
        
        - Create posting: 50k-70k
        - Filter with 60k-80k (partial overlap)
        - Verify posting returned
        """
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create posting: 50k-70k
        posting = await posting_service.create_posting(
            org_id=org_id,
            job_profile_id=profile.job_profile_id,
            title="Engineer",
            salary_min=Decimal("50000"),
            salary_max=Decimal("70000"),
            salary_currency="USD",
            created_by=user_id,
        )
        
        # Filter with 60k-80k (partial overlap)
        results = await posting_service.list_postings(
            org_id=org_id,
            salary_filter_min=Decimal("60000"),
            salary_filter_max=Decimal("80000"),
            page=1,
            page_size=50,
        )
        
        # Should find posting (overlap exists)
        assert len(results) == 1
        assert results[0].job_posting_id == posting.job_posting_id

    @pytest.mark.asyncio
    async def test_salary_filter_with_multiple_postings(
        self, db_session: AsyncSession, org_id, user_id
    ):
        """
        Test: Salary filter with multiple postings
        
        Validates: Requirements 4.5
        
        - Create 5 postings with different salary ranges
        - Filter with specific range
        - Verify correct postings returned
        """
        profile_service = JobProfileService(db_session)
        posting_service = JobPostingService(db_session)
        
        # Create job profile
        profile = await profile_service.create_job_profile(
            org_id=org_id,
            name="Software Engineer",
            skills=[],
            created_by=user_id,
        )
        
        # Create 5 postings with different ranges
        salary_ranges = [
            (Decimal("40000"), Decimal("60000")),
            (Decimal("50000"), Decimal("70000")),
            (Decimal("60000"), Decimal("80000")),
            (Decimal("80000"), Decimal("100000")),
            (Decimal("100000"), Decimal("120000")),
        ]
        
        postings = []
        for i, (min_sal, max_sal) in enumerate(salary_ranges):
            posting = await posting_service.create_posting(
                org_id=org_id,
                job_profile_id=profile.job_profile_id,
                title=f"Engineer {i+1}",
                salary_min=min_sal,
                salary_max=max_sal,
                salary_currency="USD",
                created_by=user_id,
            )
            postings.append(posting)
        
        # Filter with 65k-85k
        results = await posting_service.list_postings(
            org_id=org_id,
            salary_filter_min=Decimal("65000"),
            salary_filter_max=Decimal("85000"),
            page=1,
            page_size=50,
        )
        
        # Should find postings 2, 3, 4 (indices 1, 2, 3)
        assert len(results) == 3
        posting_ids = {p.job_posting_id for p in results}
        assert postings[1].job_posting_id in posting_ids
        assert postings[2].job_posting_id in posting_ids
        assert postings[3].job_posting_id in posting_ids
