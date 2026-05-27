from fastapi import Request, HTTPException, status
from app.config import settings


async def require_agent_api_key(request: Request):
    """FastAPI dependency for /internal/agents/* endpoints."""
    key = request.headers.get("X-Agent-API-Key", "")
    if not settings.AGENT_API_KEY or key != settings.AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Agent-API-Key",
        )
