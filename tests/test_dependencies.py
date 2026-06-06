"""
Tests for JWT dependencies (get_current_principal, require_role, require_privilege).

Feature: identity-and-access
Properties: 3, 8, 10

Requirements: 3.5, 3.6, 4.4, 5.3, 5.6, 6.4
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import jwt

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.dependencies import Principal
from app.modules.auth.dependencies import (
    get_current_principal,
    require_role,
    require_privilege,
)
from app.modules.auth.service import RevocationCache
from app.modules.users.service import UserService
from app.modules.rbac.service import RBACService
from app.modules.rbac.models import Role, Privilege, RolePrivilege


@pytest.mark.asyncio
async def test_get_current_principal_valid_token(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test get_current_principal with a valid JWT token."""
    from app.modules.users.service import UserService
    
    # Create a test user
    user_service = UserService(db_session)
    email = f"test-{test_run_id}@example.com"
    user = await user_service.create_user(
        email=email,
        given_name="Test",
        last_name="User",
        org_id=org_id,
    )
    
    # Create a valid JWT
    revocation_cache = RevocationCache()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "org_id": str(org_id),
        "roles": ["Administrator"],
        "exp": now + timedelta(hours=1),
        "iat": now,
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")
    
    # Call get_current_principal
    principal = await get_current_principal(
        token=token,
        revocation_cache=revocation_cache,
        db=db_session,
    )
    
    # Verify principal
    assert principal.user_id == user.user_id
    assert principal.organization_id == org_id
    assert principal.roles == ["Administrator"]
    assert principal.jti == payload["jti"]


@pytest.mark.asyncio
async def test_get_current_principal_revoked_token(
    db_session: AsyncSession, org_id, test_run_id
):
    """Test get_current_principal with a revoked JTI."""
    from app.modules.users.service import UserService
    
    # Create a test user
    user_service = UserService(db_session)
    email = f"test-{test_run_id}@example.com"
    user = await user_service.create_user(
        email=email,
        given_name="Test",
        last_name="User",
        org_id=org_id,
    )
    
    # Create revocation cache and add JTI
    revocation_cache = RevocationCache()
    jti = str(uuid4())
    revocation_cache.revoke(jti)
    
    # Create a valid JWT with the revoked JTI
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "org_id": str(org_id),
        "roles": ["Administrator"],
        "exp": now + timedelta(hours=1),
        "iat": now,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")
    
    # Call get_current_principal - should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_current_principal(
            token=token,
            revocation_cache=revocation_cache,
            db=db_session,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_require_role_success(db_session: AsyncSession, org_id):
    """Test require_role with a principal that has the required role."""
    # Create a principal with Administrator role
    principal = Principal(
        user_id=uuid4(),
        organization_id=org_id,
        role="Administrator",
        roles=["Administrator"],
    )
    
    # Create the dependency
    check_admin = require_role("Administrator")
    
    # Call the dependency
    result = await check_admin(principal=principal)
    
    assert result == principal


@pytest.mark.asyncio
async def test_require_privilege_success(db_session: AsyncSession, org_id):
    """Test require_privilege with a principal that has the required privilege."""
    # Check if Administrator role exists
    role_check = await db_session.execute(
        select(Role).where(Role.role_name == "Administrator")
    )
    role = role_check.scalar_one_or_none()
    
    if not role:
        role = Role(role_name="Administrator", description="Admin role")
        db_session.add(role)
        await db_session.flush()
    
    # Check if users:write privilege exists
    priv_check = await db_session.execute(
        select(Privilege).where(Privilege.name == "users:write")
    )
    privilege = priv_check.scalar_one_or_none()
    
    if not privilege:
        privilege = Privilege(
            privilege_id=uuid4(),
            name="users:write",
            description="Write users",
            resource_category="users",
        )
        db_session.add(privilege)
        await db_session.flush()
    
    # Check if role-privilege link exists
    link_check = await db_session.execute(
        select(RolePrivilege).where(
            (RolePrivilege.role_name == "Administrator") &
            (RolePrivilege.privilege_id == privilege.privilege_id)
        )
    )
    link = link_check.scalar_one_or_none()
    
    if not link:
        role_priv = RolePrivilege(
            role_privilege_id=uuid4(),
            role_name="Administrator",
            privilege_id=privilege.privilege_id,
        )
        db_session.add(role_priv)
        await db_session.flush()
    
    # Create a principal with Administrator role
    principal = Principal(
        user_id=uuid4(),
        organization_id=org_id,
        role="Administrator",
        roles=["Administrator"],
    )
    
    # Create the dependency
    check_privilege = require_privilege("users:write")
    
    # Call the dependency
    result = await check_privilege(principal=principal, db=db_session)
    
    assert result == principal


@pytest.mark.asyncio
async def test_require_privilege_failure(db_session: AsyncSession, org_id):
    """Test require_privilege with a principal that doesn't have the required privilege."""
    # Check if Recruiter role exists
    role_check = await db_session.execute(
        select(Role).where(Role.role_name == "Recruiter")
    )
    role = role_check.scalar_one_or_none()
    
    if not role:
        recruiter_role = Role(role_name="Recruiter", description="Recruiter role")
        db_session.add(recruiter_role)
        await db_session.flush()
    
    # Create a principal with Recruiter role
    principal = Principal(
        user_id=uuid4(),
        organization_id=org_id,
        role="Recruiter",
        roles=["Recruiter"],
    )
    
    # Create the dependency
    check_privilege = require_privilege("users:write")
    
    # Call the dependency - should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await check_privilege(principal=principal, db=db_session)
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
