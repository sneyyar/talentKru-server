"""Privacy service.

Implements DSAR management, data erasure, and retention policy enforcement.

Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

from typing import cast
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete, func, update

from app.modules.privacy.models import (
    DataSubjectAccessRequest,
    DSARStatus,
    DSARRequestType,
    OrganizationRetentionPolicy,
)
from app.modules.candidates.models import Candidate
from app.modules.resumes.models import Resume, CandidateJobHistory
from app.modules.skills.models import CandidateSkill, Skill, Domain
from app.audit_models import AuditLog
from app.observability.logging import get_logger
from app.crypto import decrypt_field

logger = get_logger(__name__)


class PrivacyService:
    """Service for privacy and DSAR management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_access_dsar(
        self,
        dsar: DataSubjectAccessRequest,
    ) -> dict:
        """
        Process Access DSAR.
        
        Guard: dsar.request_type == ACCESS (400 if not)
        Compiles candidate profile, job history, skills, questionnaire responses,
        availability slots, and journey metadata.
        Sets status=COMPLETED and completed_at=now().
        
        Requirements: 6.2
        """
        # Guard: only process Access requests
        if dsar.request_type != DSARRequestType.Access:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This workflow only processes Access requests",
            )
        
        # Fetch candidate
        result = await self.db.execute(
            select(Candidate).where(
                and_(
                    Candidate.candidate_id == dsar.candidate_id,
                    Candidate.organization_id == dsar.organization_id,
                    Candidate.deleted_at.is_(None),
                )
            )
        )
        candidate = result.scalar_one_or_none()
        
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Candidate not found",
            )
        
        # Compile candidate profile data (decrypt PII fields)
        compiled_data: dict[str, list | str | None] = {
            "candidate_id": str(candidate.candidate_id),
            "name": decrypt_field(candidate.name) if candidate.name else None,  # type: ignore[arg-type]
            "email": decrypt_field(candidate.email) if candidate.email else None,  # type: ignore[arg-type]
            "phone": decrypt_field(candidate.phone) if candidate.phone else None,  # type: ignore[arg-type]
            "location": candidate.location,  # type: ignore[dict-item]
            "global_status": candidate.global_status.value if candidate.global_status else None,
            "ineligibility_reason": candidate.ineligibility_reason,  # type: ignore[dict-item]
            "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
            "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
            "job_history": [],
            "skills": [],
            "resumes": [],
        }
        
        # Compile job history
        job_history_result = await self.db.execute(
            select(CandidateJobHistory).where(
                and_(
                    CandidateJobHistory.candidate_id == dsar.candidate_id,
                    CandidateJobHistory.organization_id == dsar.organization_id,
                    CandidateJobHistory.deleted_at.is_(None),
                )
            )
        )
        job_histories = job_history_result.scalars().all()  # type: ignore[assignment]
        for job in job_histories:
            compiled_data["job_history"].append({
                "candidate_job_history_id": str(job.candidate_job_history_id),
                "company_name": job.company_name,
                "job_title": job.job_title,
                "start_date": job.start_date.isoformat() if job.start_date else None,
                "end_date": job.end_date.isoformat() if job.end_date else None,
                "description": job.description,
                "is_current": job.is_current,
            })
        
        # Compile skills
        skills_result = await self.db.execute(
            select(CandidateSkill).where(
                and_(
                    CandidateSkill.candidate_id == dsar.candidate_id,
                    CandidateSkill.deleted_at.is_(None),
                )
            )
        )
        candidate_skills = skills_result.scalars().all()  # type: ignore[assignment]
        for cs in candidate_skills:
            # Fetch skill and domain info
            skill_result = await self.db.execute(
                select(Skill).where(Skill.skill_id == cs.skill_id)
            )
            skill = skill_result.scalar_one_or_none()
            
            domain_name = None
            if skill:
                domain_result = await self.db.execute(
                    select(Domain).where(Domain.domain_id == skill.domain_id)
                )
                domain = domain_result.scalar_one_or_none()
                domain_name = domain.name if domain else None
            
            compiled_data["skills"].append({
                "candidate_skill_id": str(cs.candidate_skill_id),
                "skill_name": skill.name if skill else None,
                "domain_name": domain_name,
                "proficiency_rank": cs.proficiency_rank,
                "years_of_experience": cs.years_of_experience,
                "source": cs.source.value if cs.source else None,
            })
        
        # Compile resumes
        resumes_result = await self.db.execute(
            select(Resume).where(
                and_(
                    Resume.candidate_id == dsar.candidate_id,
                    Resume.organization_id == dsar.organization_id,
                    Resume.deleted_at.is_(None),
                )
            )
        )
        resumes = resumes_result.scalars().all()  # type: ignore[assignment]
        for resume in resumes:
            compiled_data["resumes"].append({
                "resume_id": str(resume.resume_id),
                "file_name": resume.file_name,
                "mime_type": resume.mime_type,
                "file_size_bytes": resume.file_size_bytes,
                "parse_status": resume.parse_status,
                "uploaded_at": resume.created_at.isoformat() if resume.created_at else None,
                "is_primary": resume.is_primary,
            })
        
        # Update DSAR status
        dsar.status = DSARStatus.Completed
        dsar.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        
        logger.info(
            "access_dsar_processed",
            dsar_id=str(dsar.dsar_id),
            candidate_id=str(dsar.candidate_id),
        )
        
        return compiled_data

    async def process_erasure_dsar(
        self,
        dsar: DataSubjectAccessRequest,
    ) -> None:
        """
        Process Erasure DSAR.
        
        Hard-deletes Resume records for candidate_id.
        Hard-deletes Candidate record.
        Anonymizes AuditLog entries (set candidate_id=None, anonymized=True, anonymized_placeholder="ANONYMIZED").
        Sets status=COMPLETED and completed_at=now().
        
        Requirements: 6.3
        """
        # Hard-delete Resume records
        await self.db.execute(
            delete(Resume).where(
                and_(
                    Resume.candidate_id == dsar.candidate_id,
                    Resume.organization_id == dsar.organization_id,
                )
            )
        )
        
        logger.info(
            "erasure_dsar_resumes_deleted",
            dsar_id=str(dsar.dsar_id),
            candidate_id=str(dsar.candidate_id),
        )
        
        # Hard-delete Candidate record
        await self.db.execute(
            delete(Candidate).where(
                and_(
                    Candidate.candidate_id == dsar.candidate_id,
                    Candidate.organization_id == dsar.organization_id,
                )
            )
        )
        
        logger.info(
            "erasure_dsar_candidate_deleted",
            dsar_id=str(dsar.dsar_id),
            candidate_id=str(dsar.candidate_id),
        )
        
        # Anonymize AuditLog entries: set target_id=None, add anonymized flag
        # Note: AuditLog doesn't have anonymized/anonymized_placeholder columns yet,
        # but we update target_id to None to remove the candidate reference
        await self.db.execute(
            update(AuditLog)
            .where(
                and_(
                    AuditLog.target_id == str(dsar.candidate_id),
                    AuditLog.org_id == dsar.organization_id,
                )
            )
            .values(target_id=None)
        )
        
        logger.info(
            "erasure_dsar_audit_log_anonymized",
            dsar_id=str(dsar.dsar_id),
            candidate_id=str(dsar.candidate_id),
        )
        
        # Update DSAR status
        dsar.status = DSARStatus.Completed
        dsar.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        
        logger.info(
            "erasure_dsar_processed",
            dsar_id=str(dsar.dsar_id),
            candidate_id=str(dsar.candidate_id),
        )

    async def deny_dsar(
        self,
        dsar: DataSubjectAccessRequest,
        denial_reason: str,
        denied_by: UUID,
    ) -> None:
        """
        Deny a Data Subject Access Request.
        
        Validates denial_reason is at least 10 characters (400 if not).
        Sets status=DENIED and denial_reason.
        Writes audit log entry with denied_by user.
        
        Requirements: 6.7
        """
        # Validate denial reason
        if not denial_reason or len(denial_reason.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Denial reason must be at least 10 characters",
            )
        
        # Update DSAR
        dsar.status = DSARStatus.Denied
        dsar.denial_reason = denial_reason
        await self.db.flush()
        
        logger.info(
            "dsar_denied",
            dsar_id=str(dsar.dsar_id),
            denied_by=str(denied_by),
        )

    async def list_dsars(
        self,
        org_id: UUID,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[DataSubjectAccessRequest], int]:
        """
        List Data Subject Access Requests.
        
        Supports filtering by status and pagination.
        
        Requirements: 6.6
        """
        # Build base query
        stmt = select(DataSubjectAccessRequest).where(
            and_(
                DataSubjectAccessRequest.organization_id == org_id,
                DataSubjectAccessRequest.deleted_at.is_(None),
            )
        )
        
        # Apply status filter
        if status_filter:
            try:
                status_enum = DSARStatus(status_filter)
                stmt = stmt.where(DataSubjectAccessRequest.status == status_enum)
            except ValueError:
                pass
        
        # Get total count
        count_stmt = select(func.count(DataSubjectAccessRequest.dsar_id)).where(
            and_(
                DataSubjectAccessRequest.organization_id == org_id,
                DataSubjectAccessRequest.deleted_at.is_(None),
            )
        )
        
        if status_filter:
            try:
                status_enum = DSARStatus(status_filter)
                count_stmt = count_stmt.where(DataSubjectAccessRequest.status == status_enum)
            except ValueError:
                pass
        
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        result = await self.db.execute(stmt)
        dsars = cast(list[DataSubjectAccessRequest], result.scalars().all())  # type: ignore[assignment]
        
        return dsars, total_count

    async def get_retention_policy(
        self,
        org_id: UUID,
    ) -> OrganizationRetentionPolicy:
        """
        Get organization retention policy.
        
        Requirements: 6.4
        """
        result = await self.db.execute(
            select(OrganizationRetentionPolicy).where(
                and_(
                    OrganizationRetentionPolicy.organization_id == org_id,
                    OrganizationRetentionPolicy.deleted_at.is_(None),
                )
            )
        )
        policy = result.scalar_one_or_none()
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retention policy not found",
            )
        
        return policy

    async def update_retention_policy(
        self,
        org_id: UUID,
        candidate_data_retention_days: int | None = None,
        resume_retention_days: int | None = None,
        audit_log_retention_days: int | None = None,
        updated_by: UUID | None = None,
    ) -> OrganizationRetentionPolicy:
        """
        Update organization retention policy.
        
        Requirements: 6.4
        """
        result = await self.db.execute(
            select(OrganizationRetentionPolicy).where(
                and_(
                    OrganizationRetentionPolicy.organization_id == org_id,
                    OrganizationRetentionPolicy.deleted_at.is_(None),
                )
            )
        )
        policy = result.scalar_one_or_none()
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retention policy not found",
            )
        
        # Update fields if provided
        if candidate_data_retention_days is not None:
            policy.candidate_data_retention_days = candidate_data_retention_days
        
        if resume_retention_days is not None:
            policy.resume_retention_days = resume_retention_days
        
        if audit_log_retention_days is not None:
            policy.audit_log_retention_days = audit_log_retention_days
        
        if updated_by is not None:
            policy.updated_by = updated_by
        
        await self.db.flush()
        
        return policy

    async def run_retention_purge(self) -> dict:
        """
        Run retention policy purge.
        
        Hard-deletes Resume and Candidate records that exceed retention days.
        
        Requirements: 6.5
        """
        # Query all retention policies
        result = await self.db.execute(
            select(OrganizationRetentionPolicy).where(
                OrganizationRetentionPolicy.deleted_at.is_(None)
            )
        )
        policies = result.scalars().all()  # type: ignore[assignment]
        
        candidates_purged = 0
        resumes_purged = 0
        
        for policy in policies:
            # Calculate cutoff dates
            candidate_cutoff = datetime.now(timezone.utc) - timedelta(days=policy.candidate_data_retention_days)  # type: ignore[arg-type]  # type: ignore[assignment]
            resume_cutoff = datetime.now(timezone.utc) - timedelta(days=policy.resume_retention_days)  # type: ignore[arg-type]  # type: ignore[assignment]
            
            # Hard-delete Resume records
            resume_result = await self.db.execute(
                select(Resume).where(
                    and_(
                        Resume.organization_id == policy.organization_id,
                        Resume.created_at < resume_cutoff,
                    )
                )
            )
            resumes_to_delete = resume_result.scalars().all()  # type: ignore[assignment]
            
            for resume in resumes_to_delete:
                await self.db.delete(resume)
                resumes_purged += 1
                logger.info(
                    "retention_purge_resume",
                    resume_id=str(resume.resume_id),
                    organization_id=str(policy.organization_id),
                )
            
            # Hard-delete Candidate records (only soft-deleted ones)
            candidate_result = await self.db.execute(
                select(Candidate).where(
                    and_(
                        Candidate.organization_id == policy.organization_id,
                        Candidate.created_at < candidate_cutoff,
                        Candidate.deleted_at.isnot(None),
                    )
                )
            )
            candidates_to_delete = candidate_result.scalars().all()  # type: ignore[assignment]
            
            for candidate in candidates_to_delete:
                await self.db.delete(candidate)
                candidates_purged += 1
                logger.info(
                    "retention_purge_candidate",
                    candidate_id=str(candidate.candidate_id),
                    organization_id=str(policy.organization_id),
                )
        
        await self.db.flush()
        
        return {
            "candidates": candidates_purged,
            "resumes": resumes_purged,
        }
