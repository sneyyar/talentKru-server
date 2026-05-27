from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import secrets
from app.config import settings

router = APIRouter()
security = HTTPBasic()


def verify_metrics_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, settings.METRICS_USERNAME)
    correct_pass = secrets.compare_digest(credentials.password, settings.METRICS_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get(
    "/metrics",
    dependencies=[Depends(verify_metrics_credentials)],
    operation_id="get_prometheus_metrics",
    summary="Prometheus metrics scrape endpoint",
    description="Returns Prometheus-format metrics. Requires HTTP Basic Auth with METRICS_USERNAME/METRICS_PASSWORD credentials.",
)
async def get_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
