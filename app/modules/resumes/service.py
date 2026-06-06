"""Resume service.

Implements resume upload, file validation, storage dispatch, and ingestion task management.

Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.8
"""

import httpx
from uuid import UUID
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionFactory
from app.decorators import transactional, read_only
from app.modules.resumes.models import Resume, ParseStatus, CandidateJobHistory
from app.modules.resumes.storage import StorageService, ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES
from app.modules.candidates.service import CandidateService
from app.modules.skills.service import SkillService
from app.modules.candidates.models import Candidate
from app.observability.logging import get_logger
from app.observability.middleware import correlation_id_var

logger = get_logger(__name__)


class ResumeService:
    """Service for resume management operations."""

    def __init__(self, db: AsyncSession, storage: StorageService):
        """Initialize the service with a database session and storage backend.
        
        Args:
            db: AsyncSession for database operations
            storage: StorageService instance for file storage
        """
        self.db = db
        self.storage = storage

    def validate_file(self, mime_type: str, file_size: int) -> None:
        """
        Validate resume file format and size.

        Requirement 2.2, 2.3: Accept only PDF, DOC, DOCX with max 10 MB.
        
        Args:
            mime_type: MIME type of the file
            file_size: Size of the file in bytes
            
        Raises:
            HTTPException: 422 if format unsupported or size exceeds 10 MB
        """
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file format: {mime_type}. Accepted formats: PDF, DOC, DOCX",
            )
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=422,
                detail=f"File size {file_size} bytes exceeds maximum of 10 MB ({MAX_FILE_SIZE_BYTES} bytes)",
            )

    @transactional()
    async def upload_resume(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        org_id: UUID,
        uploaded_by: UUID,
        candidate_id: UUID | None,
        background_tasks: BackgroundTasks,
    ) -> Resume:
        """
        Upload a resume file and enqueue ingestion task.

        Requirement 2.2, 2.3, 2.4, 2.5: Validate file, store in backend, insert Resume record,
        enqueue background ingestion task.
        
        Args:
            file_bytes: The resume file content as bytes
            filename: Original filename
            mime_type: MIME type of the file
            org_id: Organization ID
            uploaded_by: User ID uploading the resume
            candidate_id: Candidate ID (optional; nullable at upload)
            background_tasks: FastAPI BackgroundTasks for async ingestion
            
        Returns:
            Created Resume instance with parse_status=PENDING
            
        Raises:
            HTTPException: 422 if file validation fails
        """
        # Requirement 2.2, 2.3: Validate file format and size
        self.validate_file(mime_type, len(file_bytes))

        # Requirement 2.4: Store file in configured storage backend
        storage_uri = await self.storage.store(file_bytes, filename, str(org_id))

        # Requirement 2.2: Insert Resume record with parse_status=PENDING
        resume = Resume(
            organization_id=org_id,
            candidate_id=candidate_id,
            storage_location=storage_uri,
            mime_type=mime_type,
            file_name=filename,
            file_size_bytes=len(file_bytes),
            uploaded_by_user_id=uploaded_by,
            is_primary=candidate_id is None,  # First resume for candidate becomes primary
            parse_status=ParseStatus.PENDING.value,
        )
        self.db.add(resume)
        await self.db.flush()

        logger.info(
            "resume_uploaded",
            resume_id=str(resume.resume_id),
            org_id=str(org_id),
            candidate_id=str(candidate_id) if candidate_id else None,
            filename=filename,
            file_size_bytes=len(file_bytes),
            storage_uri=storage_uri,
        )

        # Requirement 2.5: Enqueue background task for ingestion
        background_tasks.add_task(
            _run_ingestion,
            resume_id=resume.resume_id,
            storage_uri=storage_uri,
            org_id=org_id,
            correlation_id=correlation_id_var.get(""),
        )

        return resume


async def _run_ingestion(
    resume_id: UUID,
    storage_uri: str,
    org_id: UUID,
    correlation_id: str,
) -> None:
    """
    Background task to run resume ingestion via the ResumeIngestionAgent.

    Requirement 2.5, 2.6, 2.8: Call agent endpoint, apply results on success,
    set parse_status=FAILED on exception.
    
    Args:
        resume_id: Resume ID to ingest
        storage_uri: Storage URI of the resume file
        org_id: Organization ID
        correlation_id: Correlation ID for tracing
    """
    async with AsyncSessionFactory() as db:
        resume = await db.get(Resume, resume_id)
        if not resume:
            logger.error(
                "resume_not_found_for_ingestion",
                resume_id=str(resume_id),
                correlation_id=correlation_id,
            )
            return

        try:
            # Call ResumeIngestionAgent via internal endpoint
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.INTERNAL_API_BASE_URL}/agents/resume-ingestion",
                    json={
                        "storage_uri": storage_uri,
                        "resume_id": str(resume_id),
                        "org_id": str(org_id),
                    },
                    headers={
                        "X-Agent-API-Key": settings.AGENT_API_KEY,
                        "X-Correlation-ID": correlation_id,
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                parsed_data = response.json()

            # Requirement 2.6: Apply ingestion results
            await _apply_ingestion_results(resume, parsed_data, org_id, db)

            # Requirement 2.6: Set parse_status=COMPLETED
            resume.parse_status = ParseStatus.COMPLETED.value  # type: ignore[assignment]
            resume.parsed_data = parsed_data

            logger.info(
                "resume_ingestion_completed",
                resume_id=str(resume_id),
                org_id=str(org_id),
                correlation_id=correlation_id,
            )

        except Exception as exc:
            # Requirement 2.8: Set parse_status=FAILED and log error
            resume.parse_status = ParseStatus.FAILED.value  # type: ignore[assignment]
            logger.error(
                "resume_ingestion_failed",
                resume_id=str(resume_id),
                org_id=str(org_id),
                correlation_id=correlation_id,
                error=str(exc),
                exc_info=True,
            )

        finally:
            await db.commit()


async def _apply_ingestion_results(
    resume: Resume,
    parsed_data: dict,
    org_id: UUID,
    db: AsyncSession,
) -> None:
    """
    Apply parsed resume data to create/update candidate and related records.

    Requirement 2.6: Upsert Candidate, CandidateJobHistory, and CandidateSkill records.
    
    Args:
        resume: Resume record being ingested
        parsed_data: Parsed data from ResumeIngestionAgent
        org_id: Organization ID
        db: AsyncSession for database operations
    """
    # Extract parsed fields
    extracted_name = parsed_data.get("name")
    extracted_email = parsed_data.get("email")
    extracted_phone = parsed_data.get("phone")
    job_history_list = parsed_data.get("job_history", [])
    skills_list = parsed_data.get("skills", [])

    # Requirement 2.6: Upsert candidate if extracted data available
    candidate_service = CandidateService(db)
    candidate = None

    if extracted_name and extracted_email:
        # Try to find existing candidate by email
        import hashlib
        email_hash = hashlib.sha256(extracted_email.lower().encode()).hexdigest()
        from sqlalchemy import select, and_
        result = await db.execute(
            select(Candidate).where(
                and_(
                    Candidate.organization_id == org_id,
                    Candidate.email_hash == email_hash,
                    Candidate.deleted_at.is_(None),
                )
            )
        )
        candidate = result.scalar_one_or_none()

        if not candidate:
            # Create new candidate
            candidate = await candidate_service.create_candidate(
                org_id=org_id,
                name=extracted_name,
                email=extracted_email,
                phone=extracted_phone,
                location=None,
                created_by=org_id,  # Agent system ID would be better, but using org_id as fallback
            )  # type: ignore[arg-type]
        else:
            # Update existing candidate with parsed data
            from app.crypto import encrypt_field
            candidate.name = encrypt_field(extracted_name)  # type: ignore[assignment]
            candidate.phone = encrypt_field(extracted_phone) if extracted_phone else None  # type: ignore[assignment]

    # Associate resume with candidate if we have one
    if candidate:
        resume.candidate_id = candidate.candidate_id

    # Requirement 2.6: Insert CandidateJobHistory records
    for job_entry in job_history_list:
        if candidate:
            job_history = CandidateJobHistory(
                candidate_id=candidate.candidate_id,
                organization_id=org_id,
                company_name=job_entry.get("company_name", ""),
                job_title=job_entry.get("job_title", ""),
                start_date=job_entry.get("start_date"),
                end_date=job_entry.get("end_date"),
                description=job_entry.get("description"),
                is_current=job_entry.get("is_current", False),
            )
            db.add(job_history)

    # Requirement 2.6, 3.5, 3.6: Match and link skills
    if candidate and skills_list:
        skills_service = SkillService(db)
        await skills_service.match_and_link_skills(
            candidate_id=candidate.candidate_id,
            org_id=org_id,
            extracted_skills=skills_list,
        )

    await db.flush()
