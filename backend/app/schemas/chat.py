"""Chat request/response schemas (doc 06 §3.3)."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import ApiModel, RequestModel, UtcDatetime

AnswerType = Literal[
    "DOCUMENT_GROUNDED", "TOOL_RESULT", "CLARIFICATION", "INSUFFICIENT_EVIDENCE", "UNSUPPORTED_REQUEST", "ERROR"
]
EvidenceStatus = Literal["SUPPORTED", "INSUFFICIENT", "CONFLICTING", "VERIFIED_RECORD", "NOT_APPLICABLE"]
ActionType = Literal["CREATE_SUPPORT_CASE", "UPLOAD_DOCUMENT", "START_READINESS_CHECK", "VIEW_CLAIM", "VIEW_CASE"]


class ChatRequest(RequestModel):
    session_id: UUID | None = None
    client_message_id: UUID
    message: str = Field(min_length=1, max_length=4000)


class Citation(ApiModel):
    marker: str
    chunk_id: UUID | None
    document_id: UUID
    document_title: str
    document_type: str
    document_version: str
    effective_date: date | None
    section_heading: str | None
    page_start: int | None
    page_end: int | None
    excerpt: str


class ProposedAction(ApiModel):
    action_type: ActionType
    label: str
    requires_confirmation: bool
    available: bool = Field(description="False when the action's backend arrives in a later phase.")
    prefill: dict[str, Any] = {}


class Escalation(ApiModel):
    offered: bool
    reason: str | None


class ToolExecution(ApiModel):
    """What happened when a tool was requested (doc 02 §3.8 statuses + CALL_LIMIT_REACHED)."""

    tool_name: str
    result_status: str
    summary: str


class Record(ApiModel):
    """Verified structured output of a successful tool call, for display. `kind` selects the renderer:
    claims | plan_benefits | requirements | support_case_proposal (a proposal is not a created case)."""

    kind: Literal["claims", "plan_benefits", "requirements", "support_case_proposal"]
    data: dict[str, Any]


class ChatResponse(ApiModel):
    session_id: UUID
    message_id: UUID
    intent: str
    answer_type: AnswerType
    evidence_status: EvidenceStatus
    answer_text: str
    citations: list[Citation]
    tool_executions: list[ToolExecution] = []
    records: list[Record] = []
    proposed_actions: list[ProposedAction]
    escalation: Escalation
    disclaimers: list[str]
    latency_ms: int
    created_at: UtcDatetime
    data_environment: Literal["SYNTHETIC_PROTOTYPE"] = "SYNTHETIC_PROTOTYPE"


class SessionSummary(ApiModel):
    session_id: UUID
    title: str
    last_message_at: UtcDatetime
    created_at: UtcDatetime


class SessionPage(ApiModel):
    items: list[SessionSummary]
    next_cursor: str | None = None


class HistoryMessage(ApiModel):
    message_id: UUID
    sender: Literal["USER", "ASSISTANT"]
    content: str
    intent: str | None
    answer_type: AnswerType | None
    evidence_status: EvidenceStatus | None
    citations: list[Citation]
    tool_executions: list[ToolExecution] = []
    records: list[Record] = []
    proposed_actions: list[ProposedAction]
    disclaimers: list[str]
    created_at: UtcDatetime


class SessionDetail(ApiModel):
    session_id: UUID
    title: str
    messages: list[HistoryMessage]
