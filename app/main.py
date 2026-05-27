from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.config import settings
from app.database import get_db_session
from app.dependencies import require_super_admin
from app.domain_events.retry import retry_failed_events
from app.middleware.cors import DynamicCORSMiddleware
from app.modules.agents.router import router as agents_router
from app.modules.auth.router import router as auth_router
from app.modules.candidates.router import router as candidates_router
from app.modules.interviews.router import router as interviews_router
from app.modules.job_posting.router import router as job_posting_router
from app.modules.job_profile.router import router as job_profile_router
from app.modules.journeys.router import router as journeys_router
from app.modules.matching.router import router as matching_router
from app.modules.observability.router import router as observability_router
from app.modules.organizations.router import router as organizations_router
from app.modules.portal.router import router as portal_router
from app.modules.questionnaires.router import router as questionnaires_router
from app.modules.rbac.router import router as rbac_router
from app.modules.reporting.router import router as reporting_router
from app.modules.requisitions.router import router as requisitions_router
from app.modules.resumes.router import router as resumes_router
from app.modules.skills.router import router as skills_router
from app.modules.users.router import router as users_router
from app.observability.logging import get_logger
from app.observability.middleware import CorrelationIDMiddleware, correlation_id_var
from app.observability.tracing import instrument_app

logger = get_logger(__name__)

app = FastAPI(
    title="TalentKru.ai API",
    version=settings.APP_VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(StaleDataError)
async def stale_data_handler(request: Request, exc: StaleDataError) -> JSONResponse:
    """Handle optimistic lock conflicts (SQLAlchemy StaleDataError → HTTP 409)."""
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Resource has been modified by another request",
            "hint": "Re-fetch the resource and retry your update",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler that returns 500 with the correlation ID for tracing."""
    cid = correlation_id_var.get("")
    logger.error(
        "unhandled_exception",
        correlation_id=cid,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "correlation_id": cid},
    )


# ---------------------------------------------------------------------------
# Middleware registration
# Starlette processes middleware in LIFO order (last added = first executed),
# so we add in reverse of the desired execution order:
#   1. CorrelationIDMiddleware  (first to execute — generates X-Correlation-ID)
#   2. DynamicCORSMiddleware    (second — resolves per-org CORS policy)
# TODO: add StructuredLoggingMiddleware once implemented
# TODO: add TracingMiddleware once implemented
# TODO: add MetricsMiddleware once implemented
# ---------------------------------------------------------------------------
app.add_middleware(DynamicCORSMiddleware)
app.add_middleware(CorrelationIDMiddleware)

# Instrument the app with OpenTelemetry auto-instrumentation.
instrument_app(app)

# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

# Module routers — all under /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(rbac_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(candidates_router, prefix="/api/v1")
app.include_router(resumes_router, prefix="/api/v1")
app.include_router(requisitions_router, prefix="/api/v1")
app.include_router(job_profile_router, prefix="/api/v1")
app.include_router(job_posting_router, prefix="/api/v1")
app.include_router(skills_router, prefix="/api/v1")
app.include_router(matching_router, prefix="/api/v1")
app.include_router(journeys_router, prefix="/api/v1")
app.include_router(interviews_router, prefix="/api/v1")
app.include_router(questionnaires_router, prefix="/api/v1")
app.include_router(portal_router, prefix="/api/v1")
app.include_router(reporting_router, prefix="/api/v1")

# Internal agent router — uses its own /internal/agents prefix (no /api/v1)
app.include_router(agents_router)

# Observability router — metrics endpoint, no /api/v1 prefix
app.include_router(observability_router)


# ---------------------------------------------------------------------------
# Platform endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    tags=["platform"],
    operation_id="health_check",
    summary="Application health check",
    description=(
        "Returns application status and version. "
        "Status is 'healthy' when the app and database are operational."
    ),
)
async def health_check(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Return application health status and version."""
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    status_val = "healthy" if db_ok else "unhealthy"
    return {"status": status_val, "version": settings.APP_VERSION}


# ---------------------------------------------------------------------------
# Internal endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/internal/domain-events/retry",
    operation_id="retry_failed_domain_events",
    summary="Retry failed domain events",
    description=(
        "Re-dispatches all domain events with Failed status. "
        "Restricted to SuperAdministrator role."
    ),
    dependencies=[Depends(require_super_admin)],
    tags=["internal"],
)
async def retry_domain_events_endpoint(
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Re-dispatch all domain events currently in Failed status."""
    return await retry_failed_events(db)
