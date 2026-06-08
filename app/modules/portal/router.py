"""Portal router.

Endpoints:
- POST /api/v1/portal/token — get portal token for candidate
- POST /api/v1/portal/verify — verify email and get JWT session token
- POST /api/v1/portal/questionnaires — get list of candidate questionnaires

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.modules.portal.schemas import (
    PortalTokenResponse,
    PortalVerifyRequest,
    PortalJWTResponse,
)
from app.modules.portal.service import CandidatePortalService
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/portal", tags=["portal"])
