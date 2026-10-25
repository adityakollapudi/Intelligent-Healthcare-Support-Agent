from datetime import date

from app.models.enums import ClaimStatus
from app.schemas.common import DATA_ENVIRONMENT, ApiModel, DataEnvironment, UtcDatetime


class ClaimSummary(ApiModel):
    claim_number: str
    plan_code: str
    provider_name: str | None
    service_date: date
    submission_date: date
    status: ClaimStatus
    status_reason_code: str | None
    last_status_change_at: UtcDatetime


class ClaimDetail(ClaimSummary):
    """Fields from doc 06 §3.5. billed_amount and internal IDs are intentionally not exposed."""

    member_number: str
    status_description: str | None
    data_environment: DataEnvironment = DATA_ENVIRONMENT


class ClaimPage(ApiModel):
    items: list[ClaimSummary]
    next_cursor: str | None
    data_environment: DataEnvironment = DATA_ENVIRONMENT
