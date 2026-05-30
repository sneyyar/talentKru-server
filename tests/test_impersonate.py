"""
Tests for SuperAdmin impersonation functionality.

Feature: identity-and-access
Task: 11 - SuperAdmin impersonation

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import jwt

from app.config import settings
from app.modules.auth.service import AuthService, RevocationCache
from app.dependencies import Principal


class TestImpersonateMethod:
    """Tests for the impersonate method."""

    @pytest.mark.asyncio
    async def test_impersonate_rejects_nested_impersonation(self):
        """
        Test that nested impersonation is rejected with 403.
        
        Requirement: 2.7 - Nested impersonation not allowed
        """
        from fastapi import HTTPException
        
        # Create mock database session
        db = AsyncMock()
        revocation_cache = RevocationCache()
        service = AuthService(db, revocation_cache)
        
        # Create a principal with obo_by set (indicating on-behalf-of)
        principal = Principal(
            user_id=uuid4(),
            organization_id=uuid4(),
            role="Administrator",
            roles=["Administrator"],
            obo_by="some-super-admin-id",
        )
        
        # Attempt to impersonate should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await service.impersonate(
                principal,
                uuid4(),
                uuid4(),
            )
        
        assert exc_info.value.status_code == 403
        assert "Nested impersonation" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_impersonate_returns_404_for_nonexistent_user(self):
        """
        Test that impersonating a non-existent user returns 404.
        
        Requirement: 2.1 - Look up target user; 404 if not found
        """
        from fastapi import HTTPException
        
        # Create mock database session that returns None
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        
        revocation_cache = RevocationCache()
        service = AuthService(db, revocation_cache)
        
        # Create a SuperAdmin principal
        principal = Principal(
            user_id=uuid4(),
            organization_id=uuid4(),
            role="SuperAdministrator",
            roles=["SuperAdministrator"],
        )
        
        target_org_id = uuid4()
        target_user_id = uuid4()
        
        # Attempt to impersonate non-existent user should raise 404
        with pytest.raises(HTTPException) as exc_info:
            await service.impersonate(principal, target_org_id, target_user_id)
        
        assert exc_info.value.status_code == 404
        assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_impersonate_returns_403_for_non_administrator(self):
        """
        Test that impersonating a non-Administrator user returns 403.
        
        Requirement: 2.2 - Target must hold Administrator role
        """
        from fastapi import HTTPException
        
        # Create a mock user without Administrator role
        mock_user = MagicMock()
        mock_user.user_id = uuid4()
        mock_user.email = "user@example.com"
        mock_user.organization_id = uuid4()
        
        # Mock user_roles to return a role that's not Administrator
        mock_role = MagicMock()
        mock_role.role_name = "Recruiter"
        mock_user.user_roles = [mock_role]
        
        # Create mock database session
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user)))
        
        revocation_cache = RevocationCache()
        service = AuthService(db, revocation_cache)
        
        # Create a SuperAdmin principal
        principal = Principal(
            user_id=uuid4(),
            organization_id=uuid4(),
            role="SuperAdministrator",
            roles=["SuperAdministrator"],
        )
        
        target_org_id = mock_user.organization_id
        target_user_id = mock_user.user_id
        
        # Attempt to impersonate non-Administrator should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await service.impersonate(principal, target_org_id, target_user_id)
        
        assert exc_info.value.status_code == 403
        assert "Administrator role" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_impersonate_issues_obo_jwt_with_correct_claims(self):
        """
        Test that impersonate issues a JWT with correct obo_by claim.
        
        Requirements: 2.3 - Issue JWT with obo_by claim
                     2.4 - Write audit log entry
        """
        # Create a mock Administrator user
        mock_user = MagicMock()
        mock_user.user_id = uuid4()
        mock_user.email = "admin@example.com"
        mock_user.organization_id = uuid4()
        
        # Mock user_roles to return Administrator role
        mock_role = MagicMock()
        mock_role.role_name = "Administrator"
        mock_user.user_roles = [mock_role]
        
        # Create mock database session
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user)))
        
        revocation_cache = RevocationCache()
        service = AuthService(db, revocation_cache)
        
        # Create a SuperAdmin principal
        super_admin_id = uuid4()
        principal = Principal(
            user_id=super_admin_id,
            organization_id=uuid4(),
            role="SuperAdministrator",
            roles=["SuperAdministrator"],
        )
        
        target_org_id = mock_user.organization_id
        target_user_id = mock_user.user_id
        
        # Patch write_audit_log to avoid actual logging
        with patch('app.audit.write_audit_log', new_callable=AsyncMock):
            token = await service.impersonate(principal, target_org_id, target_user_id)
        
        # Verify token is a string
        assert isinstance(token, str)
        
        # Decode the token to verify claims
        decoded = jwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=["HS256"])
        
        # Verify required claims
        assert decoded["sub"] == mock_user.email
        assert decoded["org_id"] == str(target_org_id)
        assert decoded["roles"] == ["Administrator"]
        assert "jti" in decoded
        assert "exp" in decoded
        assert "iat" in decoded
        
        # Verify obo_by claim is set to SuperAdmin's user_id (not email)
        assert decoded["obo_by"] == str(super_admin_id)

    @pytest.mark.asyncio
    async def test_impersonate_writes_audit_log(self):
        """
        Test that impersonate writes an audit log entry.
        
        Requirement: 2.4 - Write audit log entry
        """
        # Create a mock Administrator user
        mock_user = MagicMock()
        mock_user.user_id = uuid4()
        mock_user.email = "admin@example.com"
        mock_user.organization_id = uuid4()
        
        # Mock user_roles to return Administrator role
        mock_role = MagicMock()
        mock_role.role_name = "Administrator"
        mock_user.user_roles = [mock_role]
        
        # Create mock database session
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user)))
        
        revocation_cache = RevocationCache()
        service = AuthService(db, revocation_cache)
        
        # Create a SuperAdmin principal
        super_admin_id = uuid4()
        principal = Principal(
            user_id=super_admin_id,
            organization_id=uuid4(),
            role="SuperAdministrator",
            roles=["SuperAdministrator"],
        )
        
        target_org_id = mock_user.organization_id
        target_user_id = mock_user.user_id
        
        # Patch write_audit_log to track calls
        with patch('app.audit.write_audit_log', new_callable=AsyncMock) as mock_audit:
            await service.impersonate(principal, target_org_id, target_user_id)
            
            # Verify audit log was called
            mock_audit.assert_called_once()
            
            # Verify audit log parameters
            call_kwargs = mock_audit.call_args.kwargs
            assert call_kwargs["actor_id"] == super_admin_id
            assert call_kwargs["action"] == "ImpersonationStarted"
            assert call_kwargs["target_entity"] == "User"
            assert call_kwargs["target_id"] == target_user_id
            assert call_kwargs["org_id"] == target_org_id
            assert "timestamp" in call_kwargs
