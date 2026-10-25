from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import ping
from app.schemas.health import HealthChecks, HealthResponse

logger = logging.getLogger(__name__)


def check(db: Session) -> HealthResponse:
    """Process liveness (`checks.api`) plus database readiness (`checks.database`)."""
    try:
        ping(db)
        database = "ok"
    except SQLAlchemyError as exc:
        logger.warning("readiness_check_failed", extra={"error_type": type(exc).__name__})
        database = "unavailable"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        checks=HealthChecks(api="ok", database=database),
        time=datetime.now(UTC),
    )
