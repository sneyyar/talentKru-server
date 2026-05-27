from fastapi import APIRouter, Depends

from app.middleware.auth import require_agent_api_key

router = APIRouter(
    prefix="/internal/agents",
    tags=["agents"],
    dependencies=[Depends(require_agent_api_key)],
)


# Stub endpoint to verify the router is wired correctly
@router.get(
    "/health",
    operation_id="agent_health_check",
    summary="Agent endpoint health check",
    description="Verifies the internal agent endpoint is reachable with a valid API key.",
)
async def agent_health():
    return {"status": "ok"}
