"""Portal service.

Implements candidate self-service DSAR portal functionality.

Requirements: 6.1
"""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.privacy.models import DataSubjectAccessRequest, DSARStatus, DSARRequestType
from app.observability.logging import get_logger
from app.decorators import transactional

logger = get_logger(__name__)


class PortalService:
    """Service for candidate portal operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @transactional()
    async def create_dsar(
        self,
        candidate_id: UUID,
        org_id: UUID,
        request_type: str,
    ) -> DataSubjectAccessRequest:
        """
        Create a Data Subject Access Request.
        
        Inserts DataSubjectAccessRequest with status=PENDING and requested_at=now().
        
        Requirements: 6.1
        """
        # request_type is already a string value (e.g., "ACCESS", "ERASURE")
        # Store it directly without enum conversion
        dsar = DataSubjectAccessRequest(
            dsar_id=uuid4(),
            organization_id=org_id,
            candidate_id=candidate_id,
            request_type=request_type,
            status=DSARStatus.PENDING.value,
            requested_at=datetime.now(timezone.utc),
        )
        
        self.db.add(dsar)
        await self.db.flush()
        
        logger.info(
            "dsar_created",
            dsar_id=str(dsar.dsar_id),
            candidate_id=str(candidate_id),
            organization_id=str(org_id),
            request_type=request_type,
        )
        
        return dsar
