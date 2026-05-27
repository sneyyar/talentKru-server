"""
Dynamic per-organization CORS middleware.

Resolves the requesting organization from the request path, looks up its
``allowed_origins`` list, and sets CORS headers only when the origin is
permitted.  Unauthorized origins are logged at WARN level; no CORS headers
are emitted so the browser blocks the request.

Preflight (OPTIONS) requests are handled inline — a 200 response with the
full set of CORS headers is returned immediately when the origin is allowed,
or a 403 when it is not.

An in-process dict-based cache with a 60-second TTL avoids a DB round-trip
on every preflight while still picking up origin-list changes within a
reasonable window.

Requirements: 6.1, 6.2, 6.3
"""

import time
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# In-process TTL cache for allowed origins
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS: float = 60.0

# Maps org_id -> (origins_list, expiry_timestamp)
_origins_cache: dict[UUID, tuple[list[str], float]] = {}


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces per-organization CORS policies.

    For each request that carries an ``Origin`` header the middleware:

    1. Extracts the organization ID from the request path.
    2. Fetches (or returns from cache) the org's allowed-origins list.
    3. For OPTIONS preflight requests: returns 200 + CORS headers when the
       origin is allowed, or 403 when it is not.
    4. For all other requests: sets CORS headers when the origin is allowed,
       or logs a WARN and omits headers when it is not.
    """

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")

        # No Origin header — not a CORS request; pass through unchanged.
        if not origin:
            return await call_next(request)

        org_id = _extract_org_id(request)
        allowed = await _get_allowed_origins(org_id) if org_id else []

        # ------------------------------------------------------------------
        # Preflight handling
        # ------------------------------------------------------------------
        if request.method == "OPTIONS":
            if origin in allowed:
                response = Response(status_code=200)
                _set_cors_headers(response, origin)
                return response
            else:
                logger.warning(
                    "cors_unauthorized_origin",
                    origin=origin,
                    organization_id=str(org_id) if org_id else "unknown",
                )
                return Response(status_code=403)

        # ------------------------------------------------------------------
        # Actual request
        # ------------------------------------------------------------------
        response = await call_next(request)

        if origin in allowed:
            _set_cors_headers(response, origin)
        else:
            logger.warning(
                "cors_unauthorized_origin",
                origin=origin,
                organization_id=str(org_id) if org_id else "unknown",
            )

        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_cors_headers(response: Response, origin: str) -> None:
    """Attach the standard CORS response headers to *response*."""
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = (
        "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    )
    response.headers["Access-Control-Allow-Headers"] = (
        "Authorization,Content-Type,X-Correlation-ID,X-Agent-API-Key"
    )


def _extract_org_id(request: Request) -> UUID | None:
    """
    Try to extract an organization UUID from the request.

    Resolution order:
    1. FastAPI path parameters (``request.path_params["org_id"]``) — set
       automatically when the route template contains ``{org_id}``.
    2. URL path segment following ``/organizations/`` — covers cases where
       the middleware runs before FastAPI has parsed path params.

    Returns ``None`` when no valid UUID can be found.
    """
    # 1. FastAPI path params (populated after routing)
    org_id_raw = request.path_params.get("org_id")
    if org_id_raw:
        try:
            return UUID(str(org_id_raw))
        except (ValueError, AttributeError):
            pass

    # 2. Parse the URL path directly
    path = request.url.path
    marker = "/organizations/"
    idx = path.find(marker)
    if idx != -1:
        segment_start = idx + len(marker)
        # Take the next path segment (up to the next "/" or end of string)
        segment_end = path.find("/", segment_start)
        segment = path[segment_start:] if segment_end == -1 else path[segment_start:segment_end]
        if segment:
            try:
                return UUID(segment)
            except ValueError:
                pass

    return None


async def _get_allowed_origins(org_id: UUID) -> list[str]:
    """
    Return the list of allowed CORS origins for *org_id*.

    Results are cached in ``_origins_cache`` for ``_CACHE_TTL_SECONDS``
    (60 s) to avoid a database round-trip on every preflight request.
    The cache entry is invalidated automatically when it expires; it can
    also be cleared externally (e.g., on organization-update domain events)
    by deleting the key from ``_origins_cache``.
    """
    now = time.monotonic()

    cached = _origins_cache.get(org_id)
    if cached is not None:
        origins, expiry = cached
        if now < expiry:
            return origins
        # Entry expired — remove it and re-fetch below
        del _origins_cache[org_id]

    origins = await _fetch_allowed_origins_from_db(org_id)
    _origins_cache[org_id] = (origins, now + _CACHE_TTL_SECONDS)
    return origins


async def _fetch_allowed_origins_from_db(org_id: UUID) -> list[str]:
    """
    Query the database for the organization's ``allowed_origins`` column.

    Returns an empty list when the organization does not exist or has been
    soft-deleted.
    """
    from sqlalchemy import select

    from app.database import AsyncSessionFactory
    from app.modules.organizations.models import Organization

    async with AsyncSessionFactory() as db:
        stmt = select(Organization.allowed_origins).where(
            Organization.organization_id == org_id,
            Organization.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return list(row) if row else []
