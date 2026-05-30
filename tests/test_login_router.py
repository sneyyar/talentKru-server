"""
Tests for the POST /token login router endpoint.

Feature: identity-and-access
Task: 6.6 - Implement POST /token router

Requirements: 3.1, 3.2, 3.9
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import hashlib

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.router import login
from app.modules.auth.schemas import TokenResponse
from app.modules.auth.service import AuthenticationError, RevocationCache
from app.modules.users.models import User, UserStatus


class TestLoginRouter:
    """Tests for the login router endpoint."""

    @pytest.mark.asyncio
    async def test_login_missing_email(self):
        """
        Test that login returns 422 when email is missing.
        
        Requirement: 3.9 - Return 422 if email or password missing
        """
        # Create mock dependencies
        db = AsyncMock(spec=AsyncSession)
        revocation_cache = MagicMock(spec=RevocationCache)
        
        # Create form data with missing email
        form_data = MagicMock()
        form_data.username = None
        form_data.password = "ValidPass123!"
        
        # Call the endpoint
        with pytest.raises(HTTPException) as exc_info:
            await login(form_data, db, revocation_cache)
        
        # Verify 422 response
        assert exc_info.value.status_code == 422
        assert "username" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_login_missing_password(self):
        """
        Test that login returns 422 when password is missing.
        
        Requirement: 3.9 - Return 422 if email or password missing
        """
        # Create mock dependencies
        db = AsyncMock(spec=AsyncSession)
        revocation_cache = MagicMock(spec=RevocationCache)
        
        # Create form data with missing password
        form_data = MagicMock()
        form_data.username = "test@example.com"
        form_data.password = None
        
        # Call the endpoint
        with pytest.raises(HTTPException) as exc_info:
            await login(form_data, db, revocation_cache)
        
        # Verify 422 response
        assert exc_info.value.status_code == 422
        assert "password" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        """
        Test that login returns 401 when user is not found.
        
        Requirement: 3.2 - Return 401 on invalid credentials (no field disclosure)
        """
        # Create mock dependencies
        db = AsyncMock(spec=AsyncSession)
        revocation_cache = MagicMock(spec=RevocationCache)
        
        # Mock database execute to return no user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        
        # Create form data
        form_data = MagicMock()
        form_data.username = "nonexistent@example.com"
        form_data.password = "ValidPass123!"
        
        # Call the endpoint
        with pytest.raises(HTTPException) as exc_info:
            await login(form_data, db, revocation_cache)
        
        # Verify 401 response without field disclosure
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """
        Test that login returns 401 when credentials are invalid.
        
        Requirement: 3.2 - Return 401 on invalid credentials (no field disclosure)
        """
        # Create mock dependencies
        db = AsyncMock(spec=AsyncSession)
        revocation_cache = MagicMock(spec=RevocationCache)
        
        # Create a mock user
        mock_user = MagicMock(spec=User)
        mock_user.user_id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.organization_id = uuid4()
        mock_user.status = UserStatus.ACTIVE
        
        # Mock database execute to return the user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        db.execute = AsyncMock(return_value=mock_result)
        
        # Mock AuthService to raise AuthenticationError
        with patch('app.modules.auth.router.AuthService') as mock_auth_service:
            mock_service_instance = MagicMock()
            mock_service_instance.authenticate = AsyncMock(
                side_effect=AuthenticationError("Invalid credentials")
            )
            mock_auth_service.return_value = mock_service_instance
            
            # Create form data
            form_data = MagicMock()
            form_data.username = "test@example.com"
            form_data.password = "WrongPassword123!"
            
            # Call the endpoint
            with pytest.raises(HTTPException) as exc_info:
                await login(form_data, db, revocation_cache)
            
            # Verify 401 response without field disclosure
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_success(self):
        """
        Test that login returns TokenResponse on successful authentication.
        
        Requirement: 3.1 - Accept application/x-www-form-urlencoded and return TokenResponse
        """
        # Create mock dependencies
        db = AsyncMock(spec=AsyncSession)
        revocation_cache = MagicMock(spec=RevocationCache)
        
        # Create a mock user
        mock_user = MagicMock(spec=User)
        mock_user.user_id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.organization_id = uuid4()
        mock_user.status = UserStatus.ACTIVE
        
        # Mock database execute to return the user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        db.execute = AsyncMock(return_value=mock_result)
        
        # Mock AuthService to return tokens
        with patch('app.modules.auth.router.AuthService') as mock_auth_service:
            mock_service_instance = MagicMock()
            mock_service_instance.authenticate = AsyncMock(
                return_value=("access_token_value", "refresh_token_value")
            )
            mock_auth_service.return_value = mock_service_instance
            
            # Create form data
            form_data = MagicMock()
            form_data.username = "test@example.com"
            form_data.password = "ValidPass123!"
            
            # Call the endpoint
            response = await login(form_data, db, revocation_cache)
            
            # Verify TokenResponse
            assert isinstance(response, TokenResponse)
            assert response.access_token == "access_token_value"
            assert response.refresh_token == "refresh_token_value"
            assert response.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_accepts_form_urlencoded(self):
        """
        Test that login accepts application/x-www-form-urlencoded format.
        
        Requirement: 3.1 - Accept application/x-www-form-urlencoded
        """
        # This test verifies that the endpoint uses OAuth2PasswordRequestForm
        # which automatically handles application/x-www-form-urlencoded
        from app.modules.auth.router import login
        import inspect
        
        # Get the function signature
        sig = inspect.signature(login)
        
        # Verify that form_data parameter uses OAuth2PasswordRequestForm
        form_data_param = sig.parameters['form_data']
        assert form_data_param.annotation.__name__ == 'OAuth2PasswordRequestForm'
