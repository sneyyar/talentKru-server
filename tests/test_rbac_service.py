"""
Tests for RBACService privilege management.

Feature: identity-and-access
Requirements: 6.1, 6.2, 6.5, 6.6, 6.7, 6.8, 6.9
"""

import pytest
from hypothesis import given, settings as hypothesis_settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from app.modules.rbac.models import Role, Privilege, RolePrivilege
from app.modules.rbac.service import RBACService
# Import models to ensure mappers are properly initialized
from app.modules.users.models import User
from app.modules.auth.models import RefreshToken, RevokedToken


@pytest.fixture
async def async_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        # Create tables in dependency order (only what we need for RBAC tests)
        await conn.run_sync(lambda c: Role.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: Privilege.__table__.create(c, checkfirst=True))
        await conn.run_sync(lambda c: RolePrivilege.__table__.create(c, checkfirst=True))
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def setup_roles_and_privileges(async_db):
    """Set up test roles and privileges."""
    # Create roles
    admin_role = Role(role_name="Administrator", description="Admin role")
    recruiter_role = Role(role_name="Recruiter", description="Recruiter role")
    async_db.add(admin_role)
    async_db.add(recruiter_role)
    
    # Create privileges
    priv1 = Privilege(
        privilege_id=uuid4(),
        name="create_candidates",
        description="Create candidates",
        resource_category="candidates"
    )
    priv2 = Privilege(
        privilege_id=uuid4(),
        name="edit_candidates",
        description="Edit candidates",
        resource_category="candidates"
    )
    priv3 = Privilege(
        privilege_id=uuid4(),
        name="delete_candidates",
        description="Delete candidates",
        resource_category="candidates"
    )
    async_db.add(priv1)
    async_db.add(priv2)
    async_db.add(priv3)
    
    await async_db.flush()
    
    return {
        "admin_role": admin_role,
        "recruiter_role": recruiter_role,
        "priv1": priv1,
        "priv2": priv2,
        "priv3": priv3,
    }


class TestPrivilegeManagementBasics:
    """Basic unit tests for privilege management."""

    @pytest.mark.asyncio
    async def test_assign_privilege_success(self, async_db, setup_roles_and_privileges):
        """Test successful privilege assignment."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock):
            role_privilege = await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
        
        assert role_privilege.role_name == "Administrator"
        assert role_privilege.privilege_id == setup["priv1"].privilege_id
        assert role_privilege.deleted_at is None

    @pytest.mark.asyncio
    async def test_assign_privilege_nonexistent_privilege(self, async_db, setup_roles_and_privileges):
        """Test that assigning non-existent privilege raises ValueError."""
        service = RBACService(async_db)
        actor_id = uuid4()
        nonexistent_id = uuid4()
        
        with pytest.raises(ValueError, match="Privilege .* not found"):
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=nonexistent_id,
                actor_id=actor_id,
            )

    @pytest.mark.asyncio
    async def test_assign_privilege_duplicate(self, async_db, setup_roles_and_privileges):
        """Test that assigning duplicate privilege raises ValueError."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock):
            # First assignment
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
            
            # Second assignment should fail
            with pytest.raises(ValueError, match="already assigned"):
                await service.assign_privilege(
                    role_name="Administrator",
                    privilege_id=setup["priv1"].privilege_id,
                    actor_id=actor_id,
                )

    @pytest.mark.asyncio
    async def test_assign_privilege_writes_audit_log(self, async_db, setup_roles_and_privileges):
        """Test that assigning privilege writes audit log."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock) as mock_audit:
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
            
            # Verify audit log was called
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args[1]
            assert call_kwargs["action"] == "PrivilegeAssigned"
            assert call_kwargs["actor_id"] == actor_id
            assert call_kwargs["target_entity"] == "RolePrivilege"

    @pytest.mark.asyncio
    async def test_remove_privilege_success(self, async_db, setup_roles_and_privileges):
        """Test successful privilege removal."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock):
            # Assign two privileges first
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv2"].privilege_id,
                actor_id=actor_id,
            )
            
            # Remove one privilege
            await service.remove_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
        
        # Verify privilege is soft-deleted
        remaining = await service.get_role_privileges("Administrator")
        assert len(remaining) == 1
        assert remaining[0].privilege_id == setup["priv2"].privilege_id

    @pytest.mark.asyncio
    async def test_remove_privilege_last_privilege_fails(self, async_db, setup_roles_and_privileges):
        """Test that removing last privilege raises ValueError."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock):
            # Assign one privilege
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
            
            # Try to remove it (should fail)
            with pytest.raises(ValueError, match="Cannot remove the last privilege"):
                await service.remove_privilege(
                    role_name="Administrator",
                    privilege_id=setup["priv1"].privilege_id,
                    actor_id=actor_id,
                )

    @pytest.mark.asyncio
    async def test_remove_privilege_not_assigned(self, async_db, setup_roles_and_privileges):
        """Test that removing unassigned privilege raises ValueError."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with pytest.raises(ValueError, match="Privilege not assigned"):
            await service.remove_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )

    @pytest.mark.asyncio
    async def test_remove_privilege_writes_audit_log(self, async_db, setup_roles_and_privileges):
        """Test that removing privilege writes audit log."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock):
            # Assign two privileges
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv2"].privilege_id,
                actor_id=actor_id,
            )
            
            # Remove one
            with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock) as mock_audit:
                await service.remove_privilege(
                    role_name="Administrator",
                    privilege_id=setup["priv1"].privilege_id,
                    actor_id=actor_id,
                )
                
                # Verify audit log was called
                mock_audit.assert_called_once()
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs["action"] == "PrivilegeRemoved"
                assert call_kwargs["actor_id"] == actor_id
                assert call_kwargs["target_entity"] == "RolePrivilege"

    @pytest.mark.asyncio
    async def test_list_privileges(self, async_db, setup_roles_and_privileges):
        """Test listing all privileges."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        
        privileges = await service.list_privileges()
        
        assert len(privileges) == 3
        privilege_names = {p.name for p in privileges}
        assert privilege_names == {"create_candidates", "edit_candidates", "delete_candidates"}

    @pytest.mark.asyncio
    async def test_get_role_privileges(self, async_db, setup_roles_and_privileges):
        """Test getting privileges for a role."""
        setup = setup_roles_and_privileges
        service = RBACService(async_db)
        actor_id = uuid4()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock):
            # Assign privileges
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv1"].privilege_id,
                actor_id=actor_id,
            )
            await service.assign_privilege(
                role_name="Administrator",
                privilege_id=setup["priv2"].privilege_id,
                actor_id=actor_id,
            )
        
        role_privileges = await service.get_role_privileges("Administrator")
        
        assert len(role_privileges) == 2
        privilege_ids = {rp.privilege_id for rp in role_privileges}
        assert privilege_ids == {setup["priv1"].privilege_id, setup["priv2"].privilege_id}

    @pytest.mark.asyncio
    async def test_get_role_privileges_empty(self, async_db, setup_roles_and_privileges):
        """Test getting privileges for role with no privileges."""
        service = RBACService(async_db)
        
        role_privileges = await service.get_role_privileges("Administrator")
        
        assert len(role_privileges) == 0


class TestPrivilegeManagementProperties:
    """Property-based tests for privilege management.
    
    **Validates: Requirements 6.8**
    """

    @given(
        num_privileges=st.integers(min_value=2, max_value=5),
    )
    @hypothesis_settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_role_minimum_privilege_invariant(self, async_db, num_privileges):
        """
        Property 12: Role minimum privilege invariant
        
        For any role with exactly one privilege, assert removing that privilege 
        returns 400; role still has 1 privilege after rejection.
        
        **Validates: Requirements 6.8**
        """
        # Setup
        service = RBACService(async_db)
        actor_id = uuid4()
        
        # Create role
        role = Role(role_name=f"TestRole_{uuid4().hex[:8]}", description="Test role")
        async_db.add(role)
        
        # Create privileges
        privileges = []
        for i in range(num_privileges):
            priv = Privilege(
                privilege_id=uuid4(),
                name=f"priv_{uuid4().hex[:8]}",
                description=f"Privilege {i}",
                resource_category="test"
            )
            async_db.add(priv)
            privileges.append(priv)
        
        await async_db.flush()
        
        with patch('app.modules.rbac.service.write_audit_log', new_callable=AsyncMock):
            # Assign all privileges
            for priv in privileges:
                await service.assign_privilege(
                    role_name=role.role_name,
                    privilege_id=priv.privilege_id,
                    actor_id=actor_id,
                )
            
            # Remove all but one
            for priv in privileges[:-1]:
                await service.remove_privilege(
                    role_name=role.role_name,
                    privilege_id=priv.privilege_id,
                    actor_id=actor_id,
                )
            
            # Verify role has exactly one privilege
            remaining = await service.get_role_privileges(role.role_name)
            assert len(remaining) == 1
            
            # Try to remove the last privilege (should fail)
            with pytest.raises(ValueError, match="Cannot remove the last privilege"):
                await service.remove_privilege(
                    role_name=role.role_name,
                    privilege_id=privileges[-1].privilege_id,
                    actor_id=actor_id,
                )
            
            # Verify role still has exactly one privilege
            remaining = await service.get_role_privileges(role.role_name)
            assert len(remaining) == 1
