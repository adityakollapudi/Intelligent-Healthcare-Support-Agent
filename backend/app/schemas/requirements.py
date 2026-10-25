from datetime import date
from typing import Literal
from uuid import UUID

from app.schemas.common import DATA_ENVIRONMENT, ApiModel, DataEnvironment


class RequirementSource(ApiModel):
    document_id: UUID
    document_title: str
    document_version: str
    effective_date: date | None
    section_heading: str | None
    page_start: int | None
    chunk_id: UUID
    excerpt: str


class RequirementItem(ApiModel):
    requirement_code: str
    description: str
    is_mandatory: bool
    rule_type: str
    source: RequirementSource | None  # None: the stated passage could not be verified in the source


class RequirementSetResponse(ApiModel):
    procedure_code: str
    display_name: str
    version: str
    source_document_title: str
    source_document_version: str
    # SUPPORTED: every requirement's passage was found in the active source document.
    evidence_status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED"]
    requirements: list[RequirementItem]
    disclaimer: str = (
        "Documentation requirements only. Meeting them is not an authorization approval, "
        "a medical-necessity determination or a guarantee of coverage."
    )
    data_environment: DataEnvironment = DATA_ENVIRONMENT
