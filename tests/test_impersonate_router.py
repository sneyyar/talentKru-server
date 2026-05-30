"""
Tests for SuperAdmin impersonation router endpoint.

Feature: identity-and-access
Task: 11 - SuperAdmin impersonation

Requirements: 2.1, 2.5
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from app.modules.auth.router import impersonate
from app.modules.auth.schemas import ImpersonateRequest, TokenResponse
from app.dependencies import Principal


class TestImpersonateRouter:
    """Tests for the impersonate router endpoint."""

    @pytest.mark.asyncio
    async def test_impersonate_endpoint_requires_super_admin_role(self):
        """
        Test that the impersonate endpoint requires SuperAdministrator role.
        
        Requirement: 2.5 - Restricted to SuperAdministrator role
        """
        # Create a principal without SuperAdministrator role
        principal = Principal(
            user_id=uuid4(),
            organization_id=uuid4(),
            role="Administrator",
            roles=["Administrator"],
        )
        
        # Create mock dependencies
        db = AsyncMock()
        revocation_cache = MagicMock()
        
        request = ImpersonateRequest(
            target_org_id=uuid4(),
            target_user_id=uuid4(),
        )
        
        # The require_role dependency should raise 403
        # We'll test this by calling the dependency directly
        from app.modules.auth.dependencies import require_role
        
        role_check = require_role("SuperAdministrator")
        
        with pytest.raises(HTTPException) as exc_info:
            await role_check(principal)
        
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_impersonate_endpoint_accepts_super_admin(self):
        """
        Test that the impersonate endpoint accepts SuperAdministrator role.
        
        Requirement: 2.5 - Restricted to SuperAdministrator role
        """
        # Create a SuperAdmin principal
        principal = Principal(
            user_id=uuid4(),
            organization_id=uuid4(),
            role="SuperAdministrator",
            roles=["SuperAdministrator"],
        )
        
        # The require_role dependency should pass
        from app.modules.auth.dependencies import require_role
        
        role_check = require_role("SuperAdministrator")
        result = await role_check(principal)
        
        assert result == principal

    @pytest.mark.asyncio
    async def test_impersonate_endpoint_returns_token_response(self):
        """
        Test that the impersonate endpoint returns a TokenResponse.
        
        Requirement: 2.1 - Return scoped on-behalf-of JWT
        """
        # Create a SuperAdmin principal
        super_admin_id = uuid4()
        principal = Principal(
            user_id=super_admin_id,
            organization_id=uuid4(),
            role="SuperAdministrator",
            roles=["SuperAdministrator"],
        )
        
        # Create mock dependencies
        db = AsyncMock()
        revocation_cache = MagicMock()
        
        # Create a mock Administrator user
        mock_user = MagicMock()
        mock_user.user_id = uuid4()
        mock_user.email = "admin@example.com"
        mock_user.organization_id = uuid4()
        
        # Mock user_roles to return Administrator role
        mock_role = MagicMock()
        mock_role.role_name = "Administrator"
        mock_user.user_roles = [mock_role]
        
        # Mock database execute
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user)))
        
        request = ImpersonateRequest(
            target_org_id=mock_user.organization_id,
            target_user_id=mock_user.user_id,
        )
        
        # Patch write_audit_log to avoid actual logging
        with patch('app.audit.write_audit_log', new_callable=AsyncMock):
            # Call the endpoint
            response = await impersonate(
                request=request,
                principal=principal,
                db=db,
                revocation_cache=revocation_cache,
                _=principal,  # This is the result of require_role dependency
            )
        
        # Verify response is TokenResponse
        assert isinstance(response, TokenResponse)
        assert response.token_type == "bearer"
        assert response.access_token  # Should have a token
        assert response.refresh_token == ""  # No refresh token for OBO sessions
