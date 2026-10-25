"""Support-case schemas (doc 06 §3.8). Server-controlled fields (creator, assignee, status,
case_number, version) are not accepted from clients: RequestModel forbids unknown fields."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import ApiModel, RequestModel, UtcDatetime

CaseCategory = Literal[
    "BENEFITS_QUESTION",
    "CLAIM_INQUIRY",
    "DOCUMENT_ISSUE",
    "PA_READINESS_REVIEW",
    "KNOWLEDGE_GAP",
    "TECHNICAL_ISSUE",
    "OTHER",
]
EscalationReason = Literal[
    "NO_ADEQUATE_ANSWER",
    "CONFLICTING_INFORMATION",
    "USER_REQUESTED_HUMAN",
    "DOCUMENT_REQUIRES_REVIEW",
    "TOOL_FAILURE",
    "APPROVAL_REQUIRED",
    "OUT_OF_SCOPE",
    "USER_INITIATED",
]
CaseStatus = Literal["OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_USER", "RESOLVED", "CLOSED", "CANCELLED"]


class CreateCaseRequest(RequestModel):
    category: CaseCategory
    summary: str = Field(min_length=10, max_length=2000)
    escalation_reason: EscalationReason = "USER_INITIATED"
    related_session_id: UUID | None = None
    related_claim_number: str | None = Field(default=None, pattern=r"^SYN-CLM-\d{4}-\d{6}$")


class CaseEvent(ApiModel):
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    actor_display_name: str
    created_at: UtcDatetime


class CaseSummary(ApiModel):
    case_id: UUID
    case_number: str
    category: CaseCategory
    status: CaseStatus
    escalation_reason: EscalationReason
    summary_preview: str
    created_at: UtcDatetime
    updated_at: UtcDatetime


class CaseDetail(ApiModel):
    case_id: UUID
    case_number: str
    category: CaseCategory
    status: CaseStatus
    escalation_reason: EscalationReason
    summary: str
    related_session_id: UUID | None
    related_claim_number: str | None
    resolution_note: str | None
    version: int
    events: list[CaseEvent]
    created_at: UtcDatetime
    updated_at: UtcDatetime
    data_environment: Literal["SYNTHETIC_PROTOTYPE"] = "SYNTHETIC_PROTOTYPE"


class CasePage(ApiModel):
    items: list[CaseSummary]
    next_cursor: str | None = None
