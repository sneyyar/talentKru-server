"""
Authentication extraction middleware.

Extracts org_id and org_rate_limit from JWT and stores in request.state
for use by rate limiting and other middleware.

Requirements: 8.3, 8.4
"""

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_session
from app.modules.organizations.models import Organization


class AuthExtractionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts org_id and org_rate_limit from JWT.
    
    Stores them in request.state for use by rate limiting middleware.
    
    Requirements: 8.3, 8.4
    """

    async def dispatch(self, request: Request, call_next):
        """
        Extract org_id and org_rate_limit from JWT if present.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Response from next middleware/handler
        """
        # Try to extract org_id from JWT
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = jwt.decode(
                    token, settings.JWT_SIGNING_KEY, algorithms=["HS256"]
                )
                org_id_str = payload.get("org_id")
                if org_id_str:
                    request.state.org_id = org_id_str
                    
                    # Fetch the organization's rate limit from the database
                    try:
                        async with get_db_session() as db:
                            stmt = select(Organization).where(
                                Organization.organization_id == org_id_str
                            )
                            result = await db.execute(stmt)
                            org = result.scalar_one_or_none()
                            if org:
                                request.state.org_rate_limit = org.rate_limit_per_minute
                    except Exception:
                        # If we can't fetch the org, use default
                        request.state.org_rate_limit = 1000
            except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
                # Invalid or expired token, skip extraction
                pass
        
        response = await call_next(request)
        return response
