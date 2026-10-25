from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer

DataEnvironment = Literal["SYNTHETIC_PROTOTYPE"]
DATA_ENVIRONMENT: DataEnvironment = "SYNTHETIC_PROTOTYPE"


def _utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


# Timestamps are always serialized as ISO 8601 UTC with a trailing Z (doc 06 §1).
UtcDatetime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str)]

# Public identifier patterns (doc 05 §2).
CLAIM_NUMBER_PATTERN = r"^SYN-CLM-\d{4}-\d{6}$"
PLAN_CODE_PATTERN = r"^SYN-PLAN-[A-Z0-9-]{2,20}$"
BENEFIT_CATEGORY_PATTERN = r"^[A-Z][A-Z_]{1,59}$"


class ApiModel(BaseModel):
    """Response base: explicit fields only; nothing from ORM objects leaks implicitly."""

    model_config = ConfigDict(extra="forbid")


class RequestModel(BaseModel):
    """Request base: unknown fields are rejected (FIELD_NOT_ALLOWED)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorDetail(ApiModel):
    field: str | None = None
    issue: str
    allowed: list[Any] | None = None


class ErrorInfo(ApiModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None


class ErrorResponse(ApiModel):
    error: ErrorInfo
