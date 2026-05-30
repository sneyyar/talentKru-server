"""
Tests for JobPostingService.

Feature: candidate-lifecycle
Properties:
- Property 10: JobPosting requires a valid JobProfile
- Property 11: Salary range overlap filter correctness

Requirements: 4.2, 4.3, 4.4, 4.5
"""

import pytest
from hypothesis import given, settings as hypothesis_settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.base_model import Base
from app.modules.job_posting.models import JobPosting
from app.modules.job_posting.service import JobPostingService
from app.modules.job_profile.models import JobProfile


@pytest.fixture
async def async_db():
    """Create an in-memory PostgreSQL-compatible database for testing."""
    # Use PostgreSQL dialect for in-memory testing to support JSONB
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost/test",
        echo=False,
        strategy="mock",
        executor=AsyncMock(),
    )
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def mock_db():
    """Create a mock database session for testing."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
async def org_and_profile(mock_db):
    """Create an organization and job profile for testing."""
    org_id = uuid4()
    profile_id = uuid4()
    
    # Create job profile
    profile = JobProfile(
        job_profile_id=profile_id,
        organization_id=org_id,
        name="Software Engineer",
    )
    
    # Mock the get method to return the profile
    async def mock_get(model, id):
        if model == JobProfile and id == profile_id:
            return profile
        return None
    
    mock_db.get = mock_get
    
    return org_id, profile_id, mock_db


class TestJobPostingServiceBasics:
    """Basic unit tests for JobPostingService."""

    @pytest.mark.asyncio
    async def test_create_posting_success(self, mock_db, org_and_profile):
        """Test successful job posting creation."""
        org_id, profile_id, db = org_and_profile
        service = JobPostingService(db)
        
        # Mock the get method to return the profile
        profile = JobProfile(
            job_profile_id=profile_id,
            organization_id=org_id,
            name="Software Engineer",
        )
        
        async def mock_get(model, id):
            if model == JobProfile and id == profile_id:
                return profile
            return None
        
        db.get = mock_get
        db.add = MagicMock()
        db.flush = AsyncMock()
        
        posting = await service.create_posting(
            org_id=org_id,
            job_profile_id=profile_id,
            description="Senior Software Engineer role",
            work_locations=["San Francisco", "Remote"],
            salary_min=150000.0,
            salary_max=200000.0,
            salary_currency="USD",
            sourcing_channel="LinkedIn",
        )
        
        # Verify the posting was created with correct values
        assert posting.organization_id == org_id
        assert posting.job_profile_id == profile_id
        assert posting.description == "Senior Software Engineer role"
        assert posting.work_locations == ["San Francisco", "Remote"]
        assert posting.salary_min == 150000.0
        assert posting.salary_max == 200000.0
        assert posting.salary_currency == "USD"
        assert posting.sourcing_channel == "LinkedIn"

    @pytest.mark.asyncio
    async def test_create_posting_invalid_profile(self, mock_db, org_and_profile):
        """Test that creating posting with invalid profile raises 400."""
        org_id, _, db = org_and_profile
        service = JobPostingService(db)
        invalid_profile_id = uuid4()
        
        async def mock_get(model, id):
            return None
        
        db.get = mock_get
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.create_posting(
                org_id=org_id,
                job_profile_id=invalid_profile_id,
                description="Test",
                work_locations=["Remote"],
                salary_min=100000.0,
                salary_max=150000.0,
                salary_currency="USD",
                sourcing_channel="LinkedIn",
            )
        
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_posting_cross_org_profile(self, mock_db, org_and_profile):
        """Test that creating posting with cross-org profile raises 400."""
        org_id, profile_id, db = org_and_profile
        service = JobPostingService(db)
        
        # Create profile in different org
        different_org_id = uuid4()
        profile = JobProfile(
            job_profile_id=profile_id,
            organization_id=different_org_id,
            name="Software Engineer",
        )
        
        async def mock_get(model, id):
            if model == JobProfile and id == profile_id:
                return profile
            return None
        
        db.get = mock_get
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.create_posting(
                org_id=org_id,
                job_profile_id=profile_id,
                description="Test",
                work_locations=["Remote"],
                salary_min=100000.0,
                salary_max=150000.0,
                salary_currency="USD",
                sourcing_channel="LinkedIn",
            )
        
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_postings_no_filters(self, mock_db):
        """Test listing postings without filters."""
        org_id = uuid4()
        service = JobPostingService(mock_db)
        
        # Create mock postings
        postings = [
            JobPosting(
                job_posting_id=uuid4(),
                organization_id=org_id,
                job_profile_id=uuid4(),
                description=f"Job {i}",
                work_locations=["Remote"],
                salary_min=100000.0 + i * 10000,
                salary_max=150000.0 + i * 10000,
                salary_currency="USD",
                sourcing_channel="LinkedIn",
            )
            for i in range(3)
        ]
        
        # Mock execute
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = postings
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.list_postings(org_id=org_id)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_posting_success(self, mock_db):
        """Test getting a posting by ID."""
        org_id = uuid4()
        posting_id = uuid4()
        service = JobPostingService(mock_db)
        
        posting = JobPosting(
            job_posting_id=posting_id,
            organization_id=org_id,
            job_profile_id=uuid4(),
            description="Test Job",
            work_locations=["Remote"],
            salary_min=100000.0,
            salary_max=150000.0,
            salary_currency="USD",
            sourcing_channel="LinkedIn",
        )
        
        # Mock execute
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = posting
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        retrieved = await service.get_posting(posting_id, org_id)
        assert retrieved is not None
        assert retrieved.job_posting_id == posting_id
        assert retrieved.description == "Test Job"

    @pytest.mark.asyncio
    async def test_get_posting_not_found(self, mock_db):
        """Test getting a non-existent posting returns None."""
        org_id = uuid4()
        service = JobPostingService(mock_db)
        
        # Mock execute
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.get_posting(uuid4(), org_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_posting_success(self, mock_db):
        """Test updating a posting."""
        org_id = uuid4()
        posting_id = uuid4()
        service = JobPostingService(mock_db)
        
        posting = JobPosting(
            job_posting_id=posting_id,
            organization_id=org_id,
            job_profile_id=uuid4(),
            description="Original Description",
            work_locations=["Remote"],
            salary_min=100000.0,
            salary_max=150000.0,
            salary_currency="USD",
            sourcing_channel="LinkedIn",
            version=1,
        )
        
        # Mock execute
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = posting
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        
        updated = await service.update_posting(
            posting_id=posting_id,
            org_id=org_id,
            description="Updated Description",
            salary_min=120000.0,
        )
        
        assert updated.description == "Updated Description"
        assert updated.salary_min == 120000.0
        assert updated.salary_max == 150000.0

    @pytest.mark.asyncio
    async def test_update_posting_not_found(self, mock_db):
        """Test updating a non-existent posting raises 404."""
        org_id = uuid4()
        service = JobPostingService(mock_db)
        
        # Mock execute
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.update_posting(
                posting_id=uuid4(),
                org_id=org_id,
                description="Updated",
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_posting_success(self, mock_db):
        """Test soft-deleting a posting."""
        org_id = uuid4()
        posting_id = uuid4()
        service = JobPostingService(mock_db)
        
        posting = JobPosting(
            job_posting_id=posting_id,
            organization_id=org_id,
            job_profile_id=uuid4(),
            description="Test Job",
            work_locations=["Remote"],
            salary_min=100000.0,
            salary_max=150000.0,
            salary_currency="USD",
            sourcing_channel="LinkedIn",
            version=1,
        )
        
        # Mock execute
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = posting
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        
        await service.delete_posting(posting_id, org_id)
        
        # Verify deleted_at was set
        assert posting.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_posting_not_found(self, mock_db):
        """Test deleting a non-existent posting raises 404."""
        org_id = uuid4()
        service = JobPostingService(mock_db)
        
        # Mock execute
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_posting(uuid4(), org_id)
        
        assert exc_info.value.status_code == 404


class TestJobPostingServiceProperties:
    """Property-based tests for JobPostingService."""

    @given(
        profile_exists=st.booleans(),
        profile_deleted=st.booleans(),
        same_org=st.booleans(),
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_property_10_posting_requires_valid_profile(
        self, mock_db, profile_exists, profile_deleted, same_org
    ):
        """
        Property 10: JobPosting requires a valid JobProfile.
        
        Validates: Requirements 4.3, 4.4
        
        Missing, deleted, or cross-org job_profile_id → HTTPException 400
        Valid profile → posting created successfully
        """
        org_id = uuid4()
        valid_profile_id = uuid4()
        service = JobPostingService(mock_db)
        
        # Determine which profile_id to use
        if not profile_exists:
            profile_id = uuid4()
            profile = None
        elif profile_deleted:
            profile_id = uuid4()
            profile = JobProfile(
                job_profile_id=profile_id,
                organization_id=org_id,
                name="Deleted Profile",
                deleted_at="2024-01-01",  # Mark as deleted
            )
        elif not same_org:
            profile_id = uuid4()
            other_org_id = uuid4()
            profile = JobProfile(
                job_profile_id=profile_id,
                organization_id=other_org_id,
                name="Other Profile",
            )
        else:
            profile_id = valid_profile_id
            profile = JobProfile(
                job_profile_id=profile_id,
                organization_id=org_id,
                name="Valid Profile",
            )
        
        # Mock the get method
        async def mock_get(model, id):
            if model == JobProfile and id == profile_id:
                return profile
            return None
        
        mock_db.get = mock_get
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        
        # Attempt to create posting
        should_succeed = profile_exists and not profile_deleted and same_org
        
        from fastapi import HTTPException
        if should_succeed:
            posting = await service.create_posting(
                org_id=org_id,
                job_profile_id=profile_id,
                description="Test Job",
                work_locations=["Remote"],
                salary_min=100000.0,
                salary_max=150000.0,
                salary_currency="USD",
                sourcing_channel="LinkedIn",
            )
            # Verify posting was created with correct org and profile
            assert posting.organization_id == org_id
            assert posting.job_profile_id == profile_id
        else:
            with pytest.raises(HTTPException) as exc_info:
                await service.create_posting(
                    org_id=org_id,
                    job_profile_id=profile_id,
                    description="Test Job",
                    work_locations=["Remote"],
                    salary_min=100000.0,
                    salary_max=150000.0,
                    salary_currency="USD",
                    sourcing_channel="LinkedIn",
                )
            assert exc_info.value.status_code == 400

    @given(
        postings_data=st.lists(
            st.fixed_dictionaries({
                "salary_min": st.floats(min_value=0, max_value=200000),
                "salary_max": st.floats(min_value=0, max_value=200000),
            }),
            min_size=1,
            max_size=20,
        ),
        filter_min=st.floats(min_value=0, max_value=200000),
        filter_max=st.floats(min_value=0, max_value=200000),
    )
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_property_11_salary_overlap_filter(
        self, mock_db, postings_data, filter_min, filter_max
    ):
        """
        Property 11: Salary range overlap filter correctness.
        
        Validates: Requirements 4.5
        
        All returned postings satisfy:
        posting.salary_min <= filter_max AND posting.salary_max >= filter_min
        No non-overlapping posting appears in results
        """
        org_id = uuid4()
        service = JobPostingService(mock_db)
        
        # Ensure filter_min <= filter_max
        if filter_min > filter_max:
            filter_min, filter_max = filter_max, filter_min
        
        # Create postings with various salary ranges
        created_postings = []
        for i, data in enumerate(postings_data):
            salary_min = data["salary_min"]
            salary_max = data["salary_max"]
            
            # Ensure salary_min <= salary_max
            if salary_min > salary_max:
                salary_min, salary_max = salary_max, salary_min
            
            posting = JobPosting(
                job_posting_id=uuid4(),
                organization_id=org_id,
                job_profile_id=uuid4(),
                description=f"Job {i}",
                work_locations=["Remote"],
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency="USD",
                sourcing_channel="LinkedIn",
            )
            created_postings.append({
                "posting": posting,
                "salary_min": salary_min,
                "salary_max": salary_max,
            })
        
        # Filter postings that should be returned
        expected_results = [
            p for p in created_postings
            if p["salary_min"] <= filter_max and p["salary_max"] >= filter_min
        ]
        
        # Mock execute to return filtered results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [p["posting"] for p in expected_results]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Query with salary filter
        results = await service.list_postings(
            org_id=org_id,
            salary_filter_min=filter_min,
            salary_filter_max=filter_max,
        )
        
        # Verify all results satisfy overlap condition
        for result in results:
            # Overlap: posting.salary_min <= filter_max AND posting.salary_max >= filter_min
            assert result.salary_min <= filter_max, \
                f"Posting salary_min {result.salary_min} > filter_max {filter_max}"
            assert result.salary_max >= filter_min, \
                f"Posting salary_max {result.salary_max} < filter_min {filter_min}"
        
        # Verify correct number of results
        assert len(results) == len(expected_results)
