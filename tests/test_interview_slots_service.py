"""
Unit and property-based tests for InterviewSlotService (Req 2.1-2.10).

Tests verify:
- Property 5: Slot duration validation
- Property 6: Interviewer preference enforcement
- Property 7: Default interviewer limits
- Property 8: AttendanceStatus update timing
"""

import pytest
import time
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from hypothesis import given, settings as hypothesis_settings, assume
import hypothesis.strategies as st

from app.base_model import current_user_id_var
from app.modules.slots.service import InterviewSlotService
from app.modules.slots.models import (
    InterviewSlot,
    InterviewerPreference,
    SlotStatus,
    InvitationStatus,
    AttendanceStatus,
)
from fastapi import HTTPException


# ============================================================================
# Unit Tests
# ============================================================================


class TestCreateSlot:
    """Tests for create_slot method."""

    @pytest.mark.asyncio
    async def test_create_slot_basic_success(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test successful creation of a basic interview slot without interviewer."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=60)

        slot = await service.create_slot(
            org_id=org_id,
            journey_id=journey_id,
            slot_type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone_str="America/New_York",
            interviewer_user_id=None,
        )

        assert slot.interview_slot_id is not None
        assert slot.organization_id == org_id
        assert slot.interview_journey_id == journey_id
        assert slot.type == "TECHNICAL"
        assert slot.scheduled_start == start
        assert slot.scheduled_end == end
        assert slot.timezone == "America/New_York"
        assert slot.status == SlotStatus.SCHEDULED.value
        assert slot.invitation_status is None
        assert slot.attendance_status == AttendanceStatus.UNKNOWN.value
        assert slot.interviewer_user_id is None

    @pytest.mark.asyncio
    async def test_create_slot_with_interviewer_no_preference(
        self, db_session: AsyncSession, org_id, test_run_id
    ):
        """Test slot creation with interviewer (no existing preference)."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        interviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=60)

        slot = await service.create_slot(
            org_id=org_id,
            journey_id=journey_id,
            slot_type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone_str="America/New_York",
            interviewer_user_id=interviewer_id,
        )

        assert slot.interviewer_user_id == interviewer_id
        assert slot.invitation_status == InvitationStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_create_slot_start_end_validation(
        self, db_session: AsyncSession, org_id
    ):
        """Test slot creation fails if start >= end."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)

        # Test start == end
        with pytest.raises(HTTPException) as exc:
            await service.create_slot(
                org_id=org_id,
                journey_id=journey_id,
                slot_type="TECHNICAL",
                scheduled_start=start,
                scheduled_end=start,
                timezone_str="America/New_York",
            )
        assert exc.value.status_code == 422

        # Test start > end
        with pytest.raises(HTTPException) as exc:
            await service.create_slot(
                org_id=org_id,
                journey_id=journey_id,
                slot_type="TECHNICAL",
                scheduled_start=start,
                scheduled_end=start - timedelta(minutes=30),
                timezone_str="America/New_York",
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_slot_duration_too_short(
        self, db_session: AsyncSession, org_id
    ):
        """Test slot creation fails if duration < 15 minutes."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=14)

        with pytest.raises(HTTPException) as exc:
            await service.create_slot(
                org_id=org_id,
                journey_id=journey_id,
                slot_type="TECHNICAL",
                scheduled_start=start,
                scheduled_end=end,
                timezone_str="America/New_York",
            )
        assert exc.value.status_code == 422
        assert "15" in exc.value.detail

    @pytest.mark.asyncio
    async def test_create_slot_duration_too_long(
        self, db_session: AsyncSession, org_id
    ):
        """Test slot creation fails if duration > 480 minutes."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=481)

        with pytest.raises(HTTPException) as exc:
            await service.create_slot(
                org_id=org_id,
                journey_id=journey_id,
                slot_type="TECHNICAL",
                scheduled_start=start,
                scheduled_end=end,
                timezone_str="America/New_York",
            )
        assert exc.value.status_code == 422
        assert "480" in exc.value.detail

    @pytest.mark.asyncio
    async def test_create_slot_duration_boundary_15_minutes(
        self, db_session: AsyncSession, org_id
    ):
        """Test slot creation succeeds with exactly 15 minutes duration."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=15)

        slot = await service.create_slot(
            org_id=org_id,
            journey_id=journey_id,
            slot_type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone_str="America/New_York",
        )

        assert slot.interview_slot_id is not None
        assert slot.scheduled_start == start
        assert slot.scheduled_end == end

    @pytest.mark.asyncio
    async def test_create_slot_duration_boundary_480_minutes(
        self, db_session: AsyncSession, org_id
    ):
        """Test slot creation succeeds with exactly 480 minutes (8 hours) duration."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=480)

        slot = await service.create_slot(
            org_id=org_id,
            journey_id=journey_id,
            slot_type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone_str="America/New_York",
        )

        assert slot.interview_slot_id is not None
        assert slot.scheduled_start == start
        assert slot.scheduled_end == end


class TestValidateInterviewerAssignment:
    """Tests for _validate_interviewer_assignment method."""

    @pytest.mark.asyncio
    async def test_validate_slot_type_not_allowed(
        self, db_session: AsyncSession, org_id
    ):
        """Test validation fails if slot type not in allowed types."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)

        # Create preference with only MANAGER and TECHNICAL types
        pref = InterviewerPreference(
            interviewer_preference_id=uuid4(),
            interviewer_user_id=interviewer_id,
            organization_id=org_id,
            allowed_interview_types=["MANAGER", "TECHNICAL"],
            max_interviews_per_day=5,
            max_interviews_per_week=20,
        )
        db_session.add(pref)
        await db_session.flush()

        # Try to create slot with BEHAVIORAL type (not allowed)
        with pytest.raises(HTTPException) as exc:
            await service._validate_interviewer_assignment(
                org_id, interviewer_id, "BEHAVIORAL", start
            )
        assert exc.value.status_code == 409
        assert "does not allow" in exc.value.detail

    @pytest.mark.asyncio
    async def test_validate_max_per_day_reached(
        self, db_session: AsyncSession, org_id
    ):
        """Test validation fails if daily limit reached."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Create preference with max 2 per day
        pref = InterviewerPreference(
            interviewer_preference_id=uuid4(),
            interviewer_user_id=interviewer_id,
            organization_id=org_id,
            allowed_interview_types=["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"],
            max_interviews_per_day=2,
            max_interviews_per_week=20,
        )
        db_session.add(pref)
        await db_session.flush()

        # Create 2 existing slots today
        for i in range(2):
            slot = InterviewSlot(
                interview_slot_id=uuid4(),
                organization_id=org_id,
                interview_journey_id=uuid4(),
                type="MANAGER",
                scheduled_start=day_start + timedelta(hours=i),
                scheduled_end=day_start + timedelta(hours=i + 1),
                timezone="America/New_York",
                status=SlotStatus.SCHEDULED.value,
                attendance_status=AttendanceStatus.UNKNOWN.value,
                interviewer_user_id=interviewer_id,
            )
            db_session.add(slot)
        await db_session.flush()

        # Try to create a third slot today
        with pytest.raises(HTTPException) as exc:
            await service._validate_interviewer_assignment(
                org_id,
                interviewer_id,
                "MANAGER",
                day_start + timedelta(hours=3),
            )
        assert exc.value.status_code == 409
        assert "maximum interviews per day" in exc.value.detail

    @pytest.mark.asyncio
    async def test_validate_max_per_week_reached(
        self, db_session: AsyncSession, org_id
    ):
        """Test validation fails if weekly limit reached."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        # Create preference with max 2 per week
        pref = InterviewerPreference(
            interviewer_preference_id=uuid4(),
            interviewer_user_id=interviewer_id,
            organization_id=org_id,
            allowed_interview_types=["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"],
            max_interviews_per_day=10,
            max_interviews_per_week=2,
        )
        db_session.add(pref)
        await db_session.flush()

        # Create 2 existing slots this week
        for i in range(2):
            slot = InterviewSlot(
                interview_slot_id=uuid4(),
                organization_id=org_id,
                interview_journey_id=uuid4(),
                type="MANAGER",
                scheduled_start=week_start + timedelta(days=i, hours=9),
                scheduled_end=week_start + timedelta(days=i, hours=10),
                timezone="America/New_York",
                status=SlotStatus.SCHEDULED.value,
                attendance_status=AttendanceStatus.UNKNOWN.value,
                interviewer_user_id=interviewer_id,
            )
            db_session.add(slot)
        await db_session.flush()

        # Try to create a third slot this week
        with pytest.raises(HTTPException) as exc:
            await service._validate_interviewer_assignment(
                org_id,
                interviewer_id,
                "MANAGER",
                week_start + timedelta(days=5, hours=9),
            )
        assert exc.value.status_code == 409
        assert "maximum interviews per week" in exc.value.detail

    @pytest.mark.asyncio
    async def test_validate_cancelled_slots_not_counted(
        self, db_session: AsyncSession, org_id
    ):
        """Test that cancelled slots are not counted toward limits."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Create preference with max 1 per day
        pref = InterviewerPreference(
            interviewer_preference_id=uuid4(),
            interviewer_user_id=interviewer_id,
            organization_id=org_id,
            allowed_interview_types=["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"],
            max_interviews_per_day=1,
            max_interviews_per_week=20,
        )
        db_session.add(pref)
        await db_session.flush()

        # Create 1 cancelled slot today
        slot = InterviewSlot(
            interview_slot_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=uuid4(),
            type="MANAGER",
            scheduled_start=day_start + timedelta(hours=0),
            scheduled_end=day_start + timedelta(hours=1),
            timezone="America/New_York",
            status=SlotStatus.CANCELLED.value,
            attendance_status=AttendanceStatus.UNKNOWN.value,
            interviewer_user_id=interviewer_id,
        )
        db_session.add(slot)
        await db_session.flush()

        # Should be able to create a new slot since cancelled doesn't count
        await service._validate_interviewer_assignment(
            org_id,
            interviewer_id,
            "MANAGER",
            day_start + timedelta(hours=2),
        )
        # No exception raised means test passed


class TestUpdateInvitationStatus:
    """Tests for update_invitation_status method."""

    @pytest.mark.asyncio
    async def test_update_invitation_status_accepted(
        self, db_session: AsyncSession, org_id
    ):
        """Test updating invitation status to ACCEPTED."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=60)

        slot = InterviewSlot(
            interview_slot_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=journey_id,
            type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone="America/New_York",
            status=SlotStatus.SCHEDULED.value,
            invitation_status=InvitationStatus.PENDING.value,
            attendance_status=AttendanceStatus.UNKNOWN.value,
            interviewer_user_id=interviewer_id,
        )
        db_session.add(slot)
        await db_session.flush()

        updated_slot = await service.update_invitation_status(
            slot, InvitationStatus.ACCEPTED.value
        )

        assert updated_slot.invitation_status == InvitationStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_update_invitation_status_declined(
        self, db_session: AsyncSession, org_id
    ):
        """Test updating invitation status to DECLINED."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=60)

        slot = InterviewSlot(
            interview_slot_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=journey_id,
            type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone="America/New_York",
            status=SlotStatus.SCHEDULED.value,
            invitation_status=InvitationStatus.PENDING.value,
            attendance_status=AttendanceStatus.UNKNOWN.value,
            interviewer_user_id=interviewer_id,
        )
        db_session.add(slot)
        await db_session.flush()

        updated_slot = await service.update_invitation_status(
            slot, InvitationStatus.DECLINED.value
        )

        assert updated_slot.invitation_status == InvitationStatus.DECLINED.value


class TestUpdateAttendanceStatus:
    """Tests for update_attendance_status method."""

    @pytest.mark.asyncio
    async def test_update_attendance_status_after_slot_ends(
        self, db_session: AsyncSession, org_id
    ):
        """Test updating attendance status after slot has ended."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        # Create a slot that ended 1 hour ago
        end = now - timedelta(hours=1)
        start = end - timedelta(minutes=60)

        slot = InterviewSlot(
            interview_slot_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=journey_id,
            type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone="America/New_York",
            status=SlotStatus.COMPLETE.value,
            attendance_status=AttendanceStatus.UNKNOWN.value,
        )
        db_session.add(slot)
        await db_session.flush()

        updated_slot = await service.update_attendance_status(
            slot, AttendanceStatus.ATTENDED.value
        )

        assert updated_slot.attendance_status == AttendanceStatus.ATTENDED.value

    @pytest.mark.asyncio
    async def test_update_attendance_status_before_slot_ends(
        self, db_session: AsyncSession, org_id
    ):
        """Test updating attendance status fails if slot hasn't ended yet."""
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        # Create a slot that ends in the future
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=60)

        slot = InterviewSlot(
            interview_slot_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=journey_id,
            type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone="America/New_York",
            status=SlotStatus.SCHEDULED.value,
            attendance_status=AttendanceStatus.UNKNOWN.value,
        )
        db_session.add(slot)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await service.update_attendance_status(slot, AttendanceStatus.ATTENDED.value)
        assert exc.value.status_code == 409
        assert "after" in exc.value.detail.lower()


class TestCreateOrUpdatePreference:
    """Tests for create_or_update_preference method."""

    @pytest.mark.asyncio
    async def test_create_preference_success(
        self, db_session: AsyncSession, org_id
    ):
        """Test creating a new interviewer preference."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        user_id_var_token = current_user_id_var.set(str(interviewer_id))

        try:
            pref = await service.create_or_update_preference(
                org_id=org_id,
                interviewer_user_id=interviewer_id,
                current_user_id=interviewer_id,
                current_user_role="Interviewer",
                allowed_interview_types=["MANAGER", "TECHNICAL"],
                max_interviews_per_day=5,
                max_interviews_per_week=20,
            )

            assert pref.interviewer_user_id == interviewer_id
            assert pref.organization_id == org_id
            assert pref.allowed_interview_types == ["MANAGER", "TECHNICAL"]
            assert pref.max_interviews_per_day == 5
            assert pref.max_interviews_per_week == 20
        finally:
            current_user_id_var.reset(user_id_var_token)

    @pytest.mark.asyncio
    async def test_create_preference_invalid_max_per_day(
        self, db_session: AsyncSession, org_id
    ):
        """Test preference creation fails if max_per_day < 1."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()

        with pytest.raises(HTTPException) as exc:
            await service.create_or_update_preference(
                org_id=org_id,
                interviewer_user_id=interviewer_id,
                current_user_id=interviewer_id,
                current_user_role="Interviewer",
                allowed_interview_types=["MANAGER"],
                max_interviews_per_day=0,
                max_interviews_per_week=20,
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_preference_invalid_max_per_day_too_high(
        self, db_session: AsyncSession, org_id
    ):
        """Test preference creation fails if max_per_day > 20."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()

        with pytest.raises(HTTPException) as exc:
            await service.create_or_update_preference(
                org_id=org_id,
                interviewer_user_id=interviewer_id,
                current_user_id=interviewer_id,
                current_user_role="Interviewer",
                allowed_interview_types=["MANAGER"],
                max_interviews_per_day=21,
                max_interviews_per_week=20,
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_preference_invalid_max_per_week(
        self, db_session: AsyncSession, org_id
    ):
        """Test preference creation fails if max_per_week < 1."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()

        with pytest.raises(HTTPException) as exc:
            await service.create_or_update_preference(
                org_id=org_id,
                interviewer_user_id=interviewer_id,
                current_user_id=interviewer_id,
                current_user_role="Interviewer",
                allowed_interview_types=["MANAGER"],
                max_interviews_per_day=5,
                max_interviews_per_week=0,
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_preference_invalid_max_per_week_too_high(
        self, db_session: AsyncSession, org_id
    ):
        """Test preference creation fails if max_per_week > 100."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()

        with pytest.raises(HTTPException) as exc:
            await service.create_or_update_preference(
                org_id=org_id,
                interviewer_user_id=interviewer_id,
                current_user_id=interviewer_id,
                current_user_role="Interviewer",
                allowed_interview_types=["MANAGER"],
                max_interviews_per_day=5,
                max_interviews_per_week=101,
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_preference_unauthorized_user(
        self, db_session: AsyncSession, org_id
    ):
        """Test preference creation fails if not authorized."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        other_user_id = uuid4()

        with pytest.raises(HTTPException) as exc:
            await service.create_or_update_preference(
                org_id=org_id,
                interviewer_user_id=interviewer_id,
                current_user_id=other_user_id,
                current_user_role="Interviewer",
                allowed_interview_types=["MANAGER"],
                max_interviews_per_day=5,
                max_interviews_per_week=20,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_preference_admin_authorized(
        self, db_session: AsyncSession, org_id
    ):
        """Test preference creation by Administrator succeeds."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        admin_id = uuid4()

        pref = await service.create_or_update_preference(
            org_id=org_id,
            interviewer_user_id=interviewer_id,
            current_user_id=admin_id,
            current_user_role="Administrator",
            allowed_interview_types=["MANAGER"],
            max_interviews_per_day=5,
            max_interviews_per_week=20,
        )

        assert pref.interviewer_user_id == interviewer_id

    @pytest.mark.asyncio
    async def test_update_preference_success(
        self, db_session: AsyncSession, org_id
    ):
        """Test updating an existing interviewer preference."""
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()

        # Create initial preference
        pref1 = await service.create_or_update_preference(
            org_id=org_id,
            interviewer_user_id=interviewer_id,
            current_user_id=interviewer_id,
            current_user_role="Interviewer",
            allowed_interview_types=["MANAGER"],
            max_interviews_per_day=5,
            max_interviews_per_week=20,
        )

        # Update preference
        pref2 = await service.create_or_update_preference(
            org_id=org_id,
            interviewer_user_id=interviewer_id,
            current_user_id=interviewer_id,
            current_user_role="Interviewer",
            allowed_interview_types=["MANAGER", "TECHNICAL"],
            max_interviews_per_day=10,
            max_interviews_per_week=40,
        )

        assert pref2.interviewer_preference_id == pref1.interviewer_preference_id
        assert pref2.max_interviews_per_day == 10
        assert pref2.max_interviews_per_week == 40
        assert set(pref2.allowed_interview_types) == {"MANAGER", "TECHNICAL"}


# ============================================================================
# Property-Based Tests (using Hypothesis)
# ============================================================================


class TestSlotDurationValidationProperty:
    """Property 5: Slot duration validation (Req 2.4)."""

    @pytest.mark.asyncio
    @hypothesis_settings(max_examples=200)
    @given(duration_minutes=st.integers(min_value=-60, max_value=600))
    async def test_slot_duration_validation_property(
        self, db_session: AsyncSession, org_id, duration_minutes
    ):
        """
        Validates: Requirements 2.4

        For any duration in range [-60, 600]:
        - duration < 15, > 480, or <= 0 → HTTPException 422
        - 15 <= duration <= 480 → slot created successfully
        """
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=duration_minutes)

        if duration_minutes <= 0:
            with pytest.raises(HTTPException) as exc:
                await service.create_slot(
                    org_id=org_id,
                    journey_id=journey_id,
                    slot_type="TECHNICAL",
                    scheduled_start=start,
                    scheduled_end=end,
                    timezone_str="America/New_York",
                )
            assert exc.value.status_code == 422
        elif duration_minutes < 15 or duration_minutes > 480:
            with pytest.raises(HTTPException) as exc:
                await service.create_slot(
                    org_id=org_id,
                    journey_id=journey_id,
                    slot_type="TECHNICAL",
                    scheduled_start=start,
                    scheduled_end=end,
                    timezone_str="America/New_York",
                )
            assert exc.value.status_code == 422
        else:
            slot = await service.create_slot(
                org_id=org_id,
                journey_id=journey_id,
                slot_type="TECHNICAL",
                scheduled_start=start,
                scheduled_end=end,
                timezone_str="America/New_York",
            )
            assert slot.interview_slot_id is not None
            assert slot.status == SlotStatus.SCHEDULED.value


class TestInterviewerPreferenceEnforcementProperty:
    """Property 6: Interviewer preference enforcement (Req 2.2, 2.3)."""

    @pytest.mark.asyncio
    @hypothesis_settings(max_examples=100)
    @given(
        day_count=st.integers(min_value=0, max_value=10),
        week_count=st.integers(min_value=0, max_value=25),
        slot_type=st.sampled_from(["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"]),
        allowed_types=st.lists(
            st.sampled_from(["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"]),
            min_size=0,
            max_size=4,
            unique=True,
        ),
    )
    async def test_interviewer_preference_enforcement_property(
        self,
        db_session: AsyncSession,
        org_id,
        day_count,
        week_count,
        slot_type,
        allowed_types,
    ):
        """
        Validates: Requirements 2.2, 2.3

        For any combination of:
        - Existing day_count slots (0-10)
        - Existing week_count slots (0-25)
        - Desired slot_type
        - Allowed interview types
        - Preference max_per_day=5, max_per_week=20

        Verify:
        - If slot_type not in allowed_types → 409
        - If day_count >= 5 → 409
        - If week_count >= 20 → 409
        - Otherwise → slot created successfully
        """
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        # Create preference
        pref = InterviewerPreference(
            interviewer_preference_id=uuid4(),
            interviewer_user_id=interviewer_id,
            organization_id=org_id,
            allowed_interview_types=allowed_types if allowed_types else ["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"],
            max_interviews_per_day=5,
            max_interviews_per_week=20,
        )
        db_session.add(pref)
        await db_session.flush()

        # Create day_count existing slots
        for i in range(min(day_count, 5)):
            slot = InterviewSlot(
                interview_slot_id=uuid4(),
                organization_id=org_id,
                interview_journey_id=uuid4(),
                type="MANAGER",
                scheduled_start=day_start + timedelta(hours=i * 2),
                scheduled_end=day_start + timedelta(hours=i * 2 + 1),
                timezone="America/New_York",
                status=SlotStatus.SCHEDULED.value,
                attendance_status=AttendanceStatus.UNKNOWN.value,
                interviewer_user_id=interviewer_id,
            )
            db_session.add(slot)
        
        # Create week_count existing slots (distributed throughout week)
        remaining_week = max(0, week_count - min(day_count, 5))
        for i in range(min(remaining_week, 20)):
            day_offset = (i + (5 if day_count >= 5 else day_count)) % 7
            if day_offset < 5:  # Within working week
                slot = InterviewSlot(
                    interview_slot_id=uuid4(),
                    organization_id=org_id,
                    interview_journey_id=uuid4(),
                    type="MANAGER",
                    scheduled_start=week_start + timedelta(days=day_offset, hours=9),
                    scheduled_end=week_start + timedelta(days=day_offset, hours=10),
                    timezone="America/New_York",
                    status=SlotStatus.SCHEDULED.value,
                    attendance_status=AttendanceStatus.UNKNOWN.value,
                    interviewer_user_id=interviewer_id,
                )
                db_session.add(slot)
        await db_session.flush()

        # Try to create new slot
        test_start = week_start + timedelta(days=6, hours=10)

        # Determine expected outcome
        should_fail = False
        if allowed_types and slot_type not in allowed_types:
            should_fail = True
        elif day_count >= 5:
            should_fail = True
        elif week_count >= 20:
            should_fail = True

        if should_fail:
            with pytest.raises(HTTPException) as exc:
                await service._validate_interviewer_assignment(
                    org_id, interviewer_id, slot_type, test_start
                )
            assert exc.value.status_code == 409
        else:
            # Should not raise
            await service._validate_interviewer_assignment(
                org_id, interviewer_id, slot_type, test_start
            )


class TestDefaultInterviewerLimitsProperty:
    """Property 7: Default interviewer limits (Req 2.10)."""

    @pytest.mark.asyncio
    @hypothesis_settings(max_examples=100)
    @given(slot_type=st.sampled_from(["MANAGER", "TECHNICAL", "BEHAVIORAL", "PANEL"]))
    async def test_default_interviewer_limits_property(
        self, db_session: AsyncSession, org_id, slot_type
    ):
        """
        Validates: Requirement 2.10

        For any slot_type:
        - If no InterviewerPreference exists → apply defaults (MaxPerDay=5, MaxPerWeek=20, all types)
        - Slot creation should succeed for valid type within limits
        """
        service = InterviewSlotService(db_session)
        interviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)

        # Do NOT create a preference - should use defaults
        # Validation should succeed since we haven't exceeded defaults
        await service._validate_interviewer_assignment(
            org_id, interviewer_id, slot_type, start
        )
        # No exception raised = defaults applied successfully


class TestAttendanceStatusUpdateTimingProperty:
    """Property 8: AttendanceStatus update timing (Req 2.7)."""

    @pytest.mark.asyncio
    @hypothesis_settings(max_examples=100)
    @given(minutes_offset=st.integers(min_value=-120, max_value=120))
    async def test_attendance_status_update_timing_property(
        self, db_session: AsyncSession, org_id, minutes_offset
    ):
        """
        Validates: Requirement 2.7

        For any minutes_offset in [-120, 120]:
        - If scheduled_end in future (positive offset) → HTTPException 409
        - If scheduled_end in past (negative offset) → update succeeds
        """
        service = InterviewSlotService(db_session)
        journey_id = uuid4()
        now = datetime.now(timezone.utc)
        end = now + timedelta(minutes=minutes_offset)
        start = end - timedelta(minutes=60)

        slot = InterviewSlot(
            interview_slot_id=uuid4(),
            organization_id=org_id,
            interview_journey_id=journey_id,
            type="TECHNICAL",
            scheduled_start=start,
            scheduled_end=end,
            timezone="America/New_York",
            status=SlotStatus.SCHEDULED.value,
            attendance_status=AttendanceStatus.UNKNOWN.value,
        )
        db_session.add(slot)
        await db_session.flush()

        if minutes_offset > 0:
            # Slot ends in the future
            with pytest.raises(HTTPException) as exc:
                await service.update_attendance_status(slot, AttendanceStatus.ATTENDED.value)
            assert exc.value.status_code == 409
        else:
            # Slot ended in the past - should succeed
            updated_slot = await service.update_attendance_status(
                slot, AttendanceStatus.ATTENDED.value
            )
            assert updated_slot.attendance_status == AttendanceStatus.ATTENDED.value
