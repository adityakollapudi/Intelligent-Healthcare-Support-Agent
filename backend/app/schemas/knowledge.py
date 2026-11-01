"""Plan documents shown to customers so they can check the assistant's answers."""

from datetime import date, datetime
from uuid import UUID

from app.schemas.common import DATA_ENVIRONMENT, ApiModel, DataEnvironment


class PlanDocumentSummary(ApiModel):
    document_id: UUID
    title: str
    version: str
    document_type: str
    effective_date: date | None
    plan_name: str | None
    is_my_plan: bool


class PlanDocumentSection(ApiModel):
    heading: str | None
    page: int | None
    text: str
    chunk_ids: list[UUID]


class PlanDocumentDetail(PlanDocumentSummary):
    sections: list[PlanDocumentSection]
    retrieved_at: datetime
    data_environment: DataEnvironment = DATA_ENVIRONMENT
