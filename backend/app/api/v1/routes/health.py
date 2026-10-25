from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse
from app.services import health_service

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and database readiness (public)",
    responses={503: {"model": HealthResponse, "description": "Database unavailable (degraded)"}},
)
def get_health(response: Response, db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    result = health_service.check(db)
    if result.status != "ok":
        response.status_code = 503
    return result
