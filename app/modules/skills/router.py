"""
Skills router for domain and skill taxonomy management.

Endpoints:
- GET /api/v1/domains, POST /api/v1/domains — `require_role("Recruiter", "Administrator")`
- GET /api/v1/domains/{domain_id}/skills, POST /api/v1/domains/{domain_id}/skills — `require_role("Recruiter", "Administrator")`
- GET /api/v1/candidates/{candidate_id}/skills, POST /api/v1/candidates/{candidate_id}/skills — `require_role("Recruiter", "Administrator", "HiringManager")`
- GET /api/v1/unmatched-skill-reviews — `require_role("Administrator")`; paginated list of unresolved reviews

Requirements: 3.1, 3.2, 3.3
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from typing import Optional

from app.database import get_db_session
from app.dependencies import Principal
from app.modules.auth.dependencies import get_current_principal, require_role
from app.modules.skills.schemas import (
    DomainCreate,
    DomainResponse,
    SkillCreate,
    SkillResponse,
    CandidateSkillCreate,
    CandidateSkillResponse,
)
from app.modules.skills.service import SkillService
from app.modules.skills.models import (
    Domain,
    Skill,
    CandidateSkill,
    UnmatchedSkillReview,
)
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["skills"])


# ============================================================================
# Domain Endpoints
# ============================================================================


@router.get(
    "/domains",
    response_model=list[DomainResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_domains",
    summary="List all skill domains",
    description="Retrieve a list of all skill domains for organizing skills into categories.",
    responses={
        200: {"description": "Domains retrieved successfully", "model": list[DomainResponse]},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_domains(
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> list[DomainResponse]:
    """
    List all skill domains.

    Requirements: 3.1
    """
    stmt = select(Domain).where(Domain.deleted_at.is_(None))
    result = await db.execute(stmt)
    domains = result.scalars().all()
    return [DomainResponse.from_orm(d) for d in domains]


@router.post(
    "/domains",
    response_model=DomainResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_domain",
    summary="Create a new skill domain",
    description="Create a new skill domain for organizing skills into categories.",
    responses={
        201: {"description": "Domain created successfully", "model": DomainResponse},
        403: {"description": "Forbidden: User does not have required role"},
        409: {"description": "Conflict: Domain name already exists"},
    },
)
async def create_domain_endpoint(
    request: DomainCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> DomainResponse:
    """
    Create a new skill domain.

    Requirements: 3.1
    """
    try:
        service = SkillService(db)
        domain = await service.create_domain(request.name)
        return DomainResponse.from_orm(domain)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_domain_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create domain",
        )


# ============================================================================
# Skill Endpoints
# ============================================================================


@router.get(
    "/domains/{domain_id}/skills",
    response_model=list[SkillResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_skills_in_domain",
    summary="List skills in a domain",
    description="Retrieve all skills within a specific skill domain.",
    responses={
        200: {"description": "Skills retrieved successfully", "model": list[SkillResponse]},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Domain not found"},
    },
)
async def list_skills_in_domain(
    domain_id: UUID,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> list[SkillResponse]:
    """
    List all skills in a domain.

    Requirements: 3.1
    """
    # Verify domain exists
    domain_stmt = select(Domain).where(
        Domain.domain_id == domain_id,
        Domain.deleted_at.is_(None),
    )
    domain_result = await db.execute(domain_stmt)
    if domain_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found",
        )

    stmt = select(Skill).where(
        Skill.domain_id == domain_id,
        Skill.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    skills = result.scalars().all()
    return [SkillResponse.from_orm(s) for s in skills]


@router.post(
    "/domains/{domain_id}/skills",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_skill",
    summary="Create a new skill in a domain",
    description="Create a new skill within a specific skill domain.",
    responses={
        201: {"description": "Skill created successfully", "model": SkillResponse},
        403: {"description": "Forbidden: User does not have required role"},
        404: {"description": "Not Found: Domain not found"},
        409: {"description": "Conflict: Skill name already exists in domain"},
    },
)
async def create_skill_endpoint(
    domain_id: UUID,
    request: SkillCreate,
    principal: Principal = Depends(require_role("Recruiter", "Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> SkillResponse:
    """
    Create a new skill in a domain.

    Requirements: 3.1
    """
    # Verify domain exists
    domain_stmt = select(Domain).where(
        Domain.domain_id == domain_id,
        Domain.deleted_at.is_(None),
    )
    domain_result = await db.execute(domain_stmt)
    if domain_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found",
        )

    try:
        service = SkillService(db)
        skill = await service.create_skill(domain_id, request.name)
        return SkillResponse.from_orm(skill)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_skill_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create skill",
        )


# ============================================================================
# Candidate Skill Endpoints
# ============================================================================


@router.get(
    "/candidates/{candidate_id}/skills",
    response_model=list[CandidateSkillResponse],
    status_code=status.HTTP_200_OK,
    operation_id="list_candidate_skills",
    summary="List candidate skills",
    description="Retrieve all skills associated with a specific candidate.",
    responses={
        200: {"description": "Candidate skills retrieved successfully", "model": list[CandidateSkillResponse]},
        403: {"description": "Forbidden: User does not have required role"},
    },
)
async def list_candidate_skills(
    candidate_id: UUID,
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> list[CandidateSkillResponse]:
    """
    List all skills for a candidate.

    Requirements: 3.2
    """
    stmt = select(CandidateSkill).where(
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    candidate_skills = result.scalars().all()
    return [CandidateSkillResponse.from_orm(cs) for cs in candidate_skills]


@router.post(
    "/candidates/{candidate_id}/skills",
    response_model=CandidateSkillResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="add_skill_to_candidate",
    summary="Add a skill to a candidate",
    description="Add a skill with proficiency level and years of experience to a candidate.",
    responses={
        201: {"description": "Skill added to candidate successfully", "model": CandidateSkillResponse},
        403: {"description": "Forbidden: User does not have required role"},
        409: {"description": "Conflict: Candidate already has this skill"},
        422: {"description": "Unprocessable Entity: Invalid proficiency rank or years of experience"},
    },
)
async def add_skill_to_candidate(
    candidate_id: UUID,
    request: CandidateSkillCreate,
    principal: Principal = Depends(
        require_role("Recruiter", "Administrator", "HiringManager")
    ),
    db: AsyncSession = Depends(get_db_session),
) -> CandidateSkillResponse:
    """
    Add a skill to a candidate.

    Requirements: 3.2
    """
    try:
        service = SkillService(db)
        candidate_skill = await service.add_candidate_skill(
            candidate_id,
            request.skill_id,
            request.proficiency_rank,
            request.years_of_experience,
        )
        return CandidateSkillResponse.from_orm(candidate_skill)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_candidate_skill_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add skill to candidate",
        )


# ============================================================================
# Unmatched Skill Review Endpoints
# ============================================================================


@router.get(
    "/unmatched-skill-reviews",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    operation_id="list_unmatched_skill_reviews",
    summary="List unmatched skill reviews",
    description="Retrieve a paginated list of unresolved unmatched skill reviews for manual taxonomy review.",
    responses={
        200: {"description": "Unmatched skill reviews retrieved successfully"},
        403: {"description": "Forbidden: User does not have Administrator role"},
    },
)
async def list_unmatched_skill_reviews(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page, max 100"),
    principal: Principal = Depends(require_role("Administrator")),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List unmatched skill reviews with pagination.

    Returns a paginated list of unresolved unmatched skill reviews.

    Requirements: 3.3
    """
    # Calculate offset
    offset = (page - 1) * page_size

    # Get total count
    count_stmt = select(func.count(UnmatchedSkillReview.unmatched_skill_review_id)).where(
        UnmatchedSkillReview.resolved.is_(False),
        UnmatchedSkillReview.deleted_at.is_(None),
    )
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar() or 0

    # Get paginated results
    stmt = (
        select(UnmatchedSkillReview)
        .where(
            UnmatchedSkillReview.resolved.is_(False),
            UnmatchedSkillReview.deleted_at.is_(None),
        )
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    reviews = result.scalars().all()

    return {
        "items": [
            {
                "unmatched_skill_review_id": str(r.unmatched_skill_review_id),
                "candidate_id": str(r.candidate_id),
                "organization_id": str(r.organization_id),
                "unmatched_skill_name": r.unmatched_skill_name,
                "resolved": r.resolved,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in reviews
        ],
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
    }
