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
    related_checklist_id: UUID | None = None
    document_ids: list[UUID] = Field(default_factory=list, max_length=10)


class UpdateCaseRequest(RequestModel):
    """doc 06 §3.8 PATCH. version is required (optimistic locking); everything else is optional."""

    version: int = Field(ge=1)
    status: CaseStatus | None = None
    note: str | None = Field(default=None, min_length=1, max_length=2000)
    resolution_note: str | None = Field(default=None, min_length=1, max_length=2000)
    assign_to_me: bool = False
    release: bool = False
    assigned_to_user_id: UUID | None = None
    unassign: bool = False
    reason: str | None = Field(default=None, min_length=1, max_length=500)


class Person(ApiModel):
    id: UUID | None = None
    display_name: str
    role: str | None = None


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
    assigned_to: Person | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class CaseDocument(ApiModel):
    document_id: UUID
    original_filename: str


class ExcerptMessage(ApiModel):
    sender: str
    content: str
    created_at: UtcDatetime


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
    # Phase 7. "full": creator / assigned agent. "summary": queue agent or admin (no linked content).
    view: Literal["full", "summary"] = "full"
    created_by: Person | None = None
    assigned_to: Person | None = None
    related_checklist_id: UUID | None = None
    related_claim_status: str | None = None
    documents: list[CaseDocument] = []
    conversation_excerpt: list[ExcerptMessage] = []
    allowed_actions: list[str] = []
    resolved_at: UtcDatetime | None = None
    closed_at: UtcDatetime | None = None
    data_environment: Literal["SYNTHETIC_PROTOTYPE"] = "SYNTHETIC_PROTOTYPE"


class CasePage(ApiModel):
    items: list[CaseSummary]
    next_cursor: str | None = None


class AgentSummary(ApiModel):
    id: UUID
    display_name: str
    open_assigned_count: int
