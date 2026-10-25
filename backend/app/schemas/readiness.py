"""Documentation-readiness schemas (doc 06 §3.7). Readiness is documentation completeness only:
no field, enum or value here represents an authorization approval or denial (doc 07 §6.6)."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import DATA_ENVIRONMENT, ApiModel, DataEnvironment, RequestModel, UtcDatetime
from app.schemas.requirements import RequirementSource

ItemStatus = Literal["SATISFIED", "MISSING", "UNREADABLE", "NEEDS_MANUAL_REVIEW"]
ReadinessStatus = Literal["DOCUMENTATION_APPEARS_COMPLETE", "DOCUMENTATION_INCOMPLETE", "MANUAL_REVIEW_REQUIRED"]
ReviewState = Literal["NOT_SUBMITTED", "AWAITING_REVIEW", "UNDER_REVIEW", "REVIEW_COMPLETED"]

DISCLAIMER_VERSION = "1.0"
DISCLAIMER = (
    "This checklist reviews documentation completeness only. It is not an authorization approval, denial, "
    "medical-necessity determination, or guarantee of coverage. An authorized human reviewer makes any "
    "decision that requires judgment."
)


class ReadinessRequest(RequestModel):
    procedure_code: str = Field(pattern=r"^SYN-PROC-[A-Z0-9-]{2,30}$")
    document_ids: list[UUID] = Field(min_length=1, max_length=10)
    provider_note: str | None = Field(default=None, max_length=2000)

    @field_validator("document_ids")
    @classmethod
    def _unique(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("document_ids must not repeat")
        return value


class ItemEvidence(ApiModel):
    field_id: UUID
    document_id: UUID
    field_name: str
    validation_status: str
    normalized_value: str | None
    source_page: int | None


class ChecklistItem(ApiModel):
    requirement_code: str
    description: str
    rule_type: str
    is_mandatory: bool
    item_status: ItemStatus
    explanation: str
    evidence: list[ItemEvidence]
    requirement_source: RequirementSource | None


class ChecklistDocumentRef(ApiModel):
    document_id: UUID
    original_filename: str
    job_id: UUID
    detected_document_type: str | None


class Counts(ApiModel):
    SATISFIED: int
    MISSING: int
    UNREADABLE: int
    NEEDS_MANUAL_REVIEW: int


class ChecklistSummary(ApiModel):
    checklist_id: UUID
    procedure_code: str
    readiness_status: ReadinessStatus
    review_state: ReviewState
    counts: Counts
    created_at: UtcDatetime


class EscalationOffer(ApiModel):
    """Server-decided offer to send the checklist to a support agent (app.cases.escalation).
    Nothing is created until the user confirms POST /support-cases with this prefill."""

    category: str
    escalation_reason: str
    summary: str
    related_checklist_id: UUID
    document_ids: list[UUID]


class ChecklistDetail(ChecklistSummary):
    display_name: str
    requirement_set_version: str
    requirement_source_document: str | None
    rules_version: str
    documents: list[ChecklistDocumentRef]
    items: list[ChecklistItem]
    warnings: list[str]
    provider_note: str | None
    reviewer_summary: str
    escalation_offer: EscalationOffer | None = None
    disclaimer: str = DISCLAIMER
    data_environment: DataEnvironment = DATA_ENVIRONMENT


class ChecklistPage(ApiModel):
    items: list[ChecklistSummary]
    next_cursor: str | None = None


class RequirementSetSummary(ApiModel):
    procedure_code: str
    display_name: str
    version: str
    data_environment: DataEnvironment = DATA_ENVIRONMENT
