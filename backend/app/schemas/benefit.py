from datetime import date
from uuid import UUID

from app.schemas.common import DATA_ENVIRONMENT, ApiModel, DataEnvironment


class BenefitSource(ApiModel):
    document_title: str
    document_version: str
    effective_date: date | None
    page_start: int | None
    chunk_id: UUID


class BenefitItem(ApiModel):
    benefit_category: str
    service_name: str
    in_network_cost_share: str | None
    out_of_network_cost_share: str | None
    prior_auth_required: bool
    visit_limit: str | None
    limitations: str | None
    # Always null until knowledge documents are ingested in Phase 4 (doc 05 §2.5 source_chunk_id).
    source: BenefitSource | None = None


class BenefitsResponse(ApiModel):
    plan_code: str
    plan_name: str
    plan_year: int
    effective_start: date
    effective_end: date | None
    benefits: list[BenefitItem]
    data_environment: DataEnvironment = DATA_ENVIRONMENT
