from typing import Literal

from app.schemas.common import ApiModel, UtcDatetime


class HealthChecks(ApiModel):
    api: Literal["ok"]
    database: Literal["ok", "unavailable"]


class HealthResponse(ApiModel):
    """Deliberately minimal: no versions, hosts or configuration (FR-036)."""

    status: Literal["ok", "degraded"]
    checks: HealthChecks
    time: UtcDatetime
