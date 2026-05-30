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
import hashlib

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.dependencies import Principal
from app.modules.auth.dependencies import (
    get_current_principal,
    require_role,
    require_privilege,
)
from app.modules.auth.service import RevocationCache
from app.modules.users.models import User, UserStatus
from app.modules.organizations.models import Organization
from app.modules.rbac.models import Role, UserRole, Privilege, RolePrivilege
from app.base_model import Base
from app.crypto import encrypt_field, hash_email


@pytest.fixture
async def async_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        
        # Create tables
        await conn.exec_driver_sql("""
            CREATE TABLE organizations (
                organization_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                logo_url TEXT,
                primary_color TEXT,
                secondary_color TEXT,
                terms_url TEXT,
                contact_name TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                feature_flags TEXT DEFAULT '{}',
                shard_id INTEGER NOT NULL DEFAULT 0,
                allowed_origins TEXT,
                rate_limit_per_minute INTEGER NOT NULL DEFAULT 1000,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                deleted_by TEXT
            )
        """)
        
        await conn.exec_driver_sql("""
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                organization_id TEXT REFERENCES organizations(organization_id),
                email TEXT NOT NULL,
                email_hash TEXT NOT NULL,
                given_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PendingInvitation',
                manager_user_id TEXT REFERENCES users(user_id),
                hashed_password TEXT,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                last_failed_login_at TIMESTAMP,
                locale TEXT NOT NULL DEFAULT 'en-US',
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                deleted_by TEXT
            )
        """)
        
        await conn.exec_driver_sql("""
            CREATE TABLE roles (
                role_name TEXT PRIMARY KEY,
                description TEXT
            )
        """)
        
        await conn.exec_driver_sql("""
            CREATE TABLE user_roles (
                user_role_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(user_id),
                role_name TEXT NOT NULL REFERENCES roles(role_name),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                deleted_by TEXT
            )
        """)
        
        await conn.exec_driver_sql("""
            CREATE TABLE privileges (
                privilege_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                resource_category TEXT NOT NULL
            )
        """)
        
        await conn.exec_driver_sql("""
            CREATE TABLE role_privileges (
                role_privilege_id TEXT PRIMARY KEY,
                role_name TEXT NOT NULL REFERENCES roles(role_name),
                privilege_id TEXT NOT NULL REFERENCES privileges(privilege_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                deleted_by TEXT
            )
        """)
    
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def revocation_cache():
    """Create a revocation cache instance."""
    return RevocationCache()


@pytest.fixture
def test_app(async_db, revocation_cache):
    """Create a test FastAPI app with dependencies."""
    app = FastAPI()
    
    async def get_db():
        yield async_db
    
    def get_cache():
        return revocation_cache
    
    @app.get("/protected")
    async def protected_route(
        principal: Principal = Depends(get_current_principal),
    ):
        return {"user_id": str(principal.user_id), "roles": principal.roles}
    
    @app.get("/admin-only")
    async def admin_only_route(
        principal: Principal = Depends(require_role("Administrator")),
    ):
        return {"message": "admin access"}
    
    @app.get("/privilege-check")
    async def privilege_check_route(
        principal: Principal = Depends(require_privilege("users:write")),
    ):
        return {"message": "privilege granted"}
    
    # Override dependencies
    app.dependency_overrides[get_current_principal] = lambda: get_current_principal(
        token="",
        revocation_cache=revocation_cache,
        db=async_db,
    )
    
    from app.database import get_db_session
    app.dependency_overrides[get_db_session] = get_db
    
    from app.modules.auth.dependencies import get_revocation_cache
    app.dependency_overrides[get_revocation_cache] = get_cache
    
    return app


@pytest.mark.asyncio
async def test_get_current_principal_valid_token(async_db, revocation_cache):
    """Test get_current_principal with a valid JWT token."""
    # Create test data
    org_id = str(uuid4())
    user_id = str(uuid4())
    email = "test@example.com"
    
    # Insert organization
    await async_db.execute(
        f"""
        INSERT INTO organizations (organization_id, name, slug)
        VALUES ('{org_id}', 'Test Org', 'test-org')
        """
    )
    
    # Insert user
    email_hash = hash_email(email)
    encrypted_email = encrypt_field(email)
    await async_db.execute(
        f"""
        INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status)
        VALUES ('{user_id}', '{org_id}', '{encrypted_email}', '{email_hash}', 'Test', 'User', 'Active')
        """
    )
    
    # Create a valid JWT
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "org_id": org_id,
        "roles": ["Administrator"],
        "exp": now + timedelta(hours=1),
        "iat": now,
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")
    
    # Call get_current_principal
    from app.modules.auth.dependencies import oauth2_scheme
    principal = await get_current_principal(
        token=token,
        revocation_cache=revocation_cache,
        db=async_db,
    )
    
    # Verify principal
    assert principal.user_id == user_id
    assert principal.organization_id == org_id
    assert principal.roles == ["Administrator"]
    assert principal.jti == payload["jti"]


@pytest.mark.asyncio
async def test_get_current_principal_expired_token(async_db, revocation_cache):
    """Test get_current_principal with an expired JWT token."""
    org_id = str(uuid4())
    email = "test@example.com"
    
    # Create an expired JWT
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "org_id": org_id,
        "roles": ["Administrator"],
        "exp": now - timedelta(hours=1),  # Expired
        "iat": now,
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")
    
    # Call get_current_principal - should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_current_principal(
            token=token,
            revocation_cache=revocation_cache,
            db=async_db,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_principal_revoked_token(async_db, revocation_cache):
    """Test get_current_principal with a revoked JTI."""
    org_id = str(uuid4())
    user_id = str(uuid4())
    email = "test@example.com"
    jti = str(uuid4())
    
    # Insert organization and user
    await async_db.execute(
        f"""
        INSERT INTO organizations (organization_id, name, slug)
        VALUES ('{org_id}', 'Test Org', 'test-org')
        """
    )
    
    email_hash = hash_email(email)
    encrypted_email = encrypt_field(email)
    await async_db.execute(
        f"""
        INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status)
        VALUES ('{user_id}', '{org_id}', '{encrypted_email}', '{email_hash}', 'Test', 'User', 'Active')
        """
    )
    
    # Add JTI to revocation cache
    revocation_cache.revoke(jti)
    
    # Create a valid JWT with the revoked JTI
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "org_id": org_id,
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
            db=async_db,
        )
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_require_role_success(async_db, revocation_cache):
    """Test require_role with a principal that has the required role."""
    org_id = str(uuid4())
    user_id = str(uuid4())
    email = "test@example.com"
    
    # Insert organization and user
    await async_db.execute(
        f"""
        INSERT INTO organizations (organization_id, name, slug)
        VALUES ('{org_id}', 'Test Org', 'test-org')
        """
    )
    
    email_hash = hash_email(email)
    encrypted_email = encrypt_field(email)
    await async_db.execute(
        f"""
        INSERT INTO users (user_id, organization_id, email, email_hash, given_name, last_name, status)
        VALUES ('{user_id}', '{org_id}', '{encrypted_email}', '{email_hash}', 'Test', 'User', 'Active')
        """
    )
    
    # Create a principal with Administrator role
    principal = Principal(
        user_id=user_id,
        organization_id=org_id,
        role="Administrator",
        roles=["Administrator"],
    )
    
    # Create the dependency
    check_admin = require_role("Administrator")
    
    # Mock get_current_principal to return our principal
    async def mock_get_principal():
        return principal
    
    # Call the dependency
    result = await check_admin(principal=principal)
    
    assert result == principal


@pytest.mark.asyncio
async def test_require_role_failure(async_db, revocation_cache):
    """Test require_role with a principal that doesn't have the required role."""
    org_id = str(uuid4())
    user_id = str(uuid4())
    
    # Create a principal without Administrator role
    principal = Principal(
        user_id=user_id,
        organization_id=org_id,
        role="Recruiter",
        roles=["Recruiter"],
    )
    
    # Create the dependency
    check_admin = require_role("Administrator")
    
    # Call the dependency - should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await check_admin(principal=principal)
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_privilege_success(async_db, revocation_cache):
    """Test require_privilege with a principal that has the required privilege."""
    org_id = str(uuid4())
    user_id = str(uuid4())
    
    # Insert role and privilege
    await async_db.execute(
        """
        INSERT INTO roles (role_name, description)
        VALUES ('Administrator', 'Admin role')
        """
    )
    
    privilege_id = str(uuid4())
    await async_db.execute(
        f"""
        INSERT INTO privileges (privilege_id, name, description, resource_category)
        VALUES ('{privilege_id}', 'users:write', 'Write users', 'users')
        """
    )
    
    # Link role to privilege
    await async_db.execute(
        f"""
        INSERT INTO role_privileges (role_privilege_id, role_name, privilege_id)
        VALUES ('{uuid4()}', 'Administrator', '{privilege_id}')
        """
    )
    
    # Create a principal with Administrator role
    principal = Principal(
        user_id=user_id,
        organization_id=org_id,
        role="Administrator",
        roles=["Administrator"],
    )
    
    # Create the dependency
    check_privilege = require_privilege("users:write")
    
    # Call the dependency
    result = await check_privilege(principal=principal, db=async_db)
    
    assert result == principal


@pytest.mark.asyncio
async def test_require_privilege_failure(async_db, revocation_cache):
    """Test require_privilege with a principal that doesn't have the required privilege."""
    org_id = str(uuid4())
    user_id = str(uuid4())
    
    # Insert role but no privilege
    await async_db.execute(
        """
        INSERT INTO roles (role_name, description)
        VALUES ('Recruiter', 'Recruiter role')
        """
    )
    
    # Create a principal with Recruiter role
    principal = Principal(
        user_id=user_id,
        organization_id=org_id,
        role="Recruiter",
        roles=["Recruiter"],
    )
    
    # Create the dependency
    check_privilege = require_privilege("users:write")
    
    # Call the dependency - should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await check_privilege(principal=principal, db=async_db)
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
