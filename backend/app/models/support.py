"""Support cases, their history, prior-authorization requirement sets and the tool-call log
(doc 05 §2.12–2.13, §2.17–2.18, §2.23). Status values come from doc 02 §3."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAt, Synthetic, Timestamps, UUIDPrimaryKey

CASE_STATUSES = ("OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_USER", "RESOLVED", "CLOSED", "CANCELLED")
CASE_CATEGORIES = (
    "BENEFITS_QUESTION",
    "CLAIM_INQUIRY",
    "DOCUMENT_ISSUE",
    "PA_READINESS_REVIEW",
    "KNOWLEDGE_GAP",
    "TECHNICAL_ISSUE",
    "OTHER",
)
ESCALATION_REASONS = (
    "NO_ADEQUATE_ANSWER",
    "CONFLICTING_INFORMATION",
    "USER_REQUESTED_HUMAN",
    "DOCUMENT_REQUIRES_REVIEW",
    "TOOL_FAILURE",
    "APPROVAL_REQUIRED",
    "OUT_OF_SCOPE",
    "USER_INITIATED",
)
CASE_EVENT_TYPES = ("CREATED", "ASSIGNED", "UNASSIGNED", "STATUS_CHANGED", "NOTE_ADDED")
RULE_TYPES = ("FIELD_PRESENT", "FIELD_PATTERN", "DATE_WITHIN_DAYS", "DOCUMENT_TYPE_PRESENT", "MANUAL_ONLY")
TOOL_NAMES = ("get_claim_status", "get_plan_benefits", "get_required_documents", "create_support_case")
TOOL_RESULT_STATUSES = (
    "SUCCEEDED",
    "CONFIRMATION_REQUIRED",
    "INVALID_ARGUMENTS",
    "PERMISSION_DENIED",
    "NOT_FOUND",
    "EXECUTION_ERROR",
    "CALL_LIMIT_REACHED",
)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class SupportCase(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "support_cases"
    __table_args__ = (
        CheckConstraint("case_number ~ '^CASE-[0-9]{4}-[0-9]{6}$'", name="case_number_format"),
        CheckConstraint(f"status IN ({_in(CASE_STATUSES)})", name="status_valid"),
        CheckConstraint(f"category IN ({_in(CASE_CATEGORIES)})", name="category_valid"),
        CheckConstraint(f"escalation_reason IN ({_in(ESCALATION_REASONS)})", name="escalation_reason_valid"),
        CheckConstraint("char_length(summary) BETWEEN 10 AND 2000", name="summary_length"),
        CheckConstraint("version >= 1", name="version_positive"),
        # Same key from the same creator can never create a second case (FR-025 idempotency).
        UniqueConstraint("created_by_user_id", "idempotency_key"),
        Index(None, "assigned_to_user_id", "status"),
        Index(None, "status", "created_at"),
        Index(None, "created_by_user_id", "created_at"),
    )

    case_number: Mapped[str] = mapped_column(String(20), unique=True)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_to_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    category: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'OPEN'"))
    escalation_reason: Mapped[str] = mapped_column(String(30), server_default=text("'USER_INITIATED'"))
    summary: Mapped[str] = mapped_column(String(2000))
    related_session_id: Mapped[UUID | None] = mapped_column(ForeignKey("conversation_sessions.id", ondelete="SET NULL"))
    related_claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id", ondelete="RESTRICT"))
    # Phase 7: a readiness checklist sent for human review (must be the creator's own).
    related_checklist_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("authorization_checklists.id", ondelete="RESTRICT"), index=True
    )
    evidence_references: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    resolution_note: Mapped[str | None] = mapped_column(String(2000))
    idempotency_key: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))  # detects a reused key with a different body
    version: Mapped[int] = mapped_column(server_default=text("1"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["SupportCaseEvent"]] = relationship(
        cascade="all, delete-orphan", order_by="SupportCaseEvent.created_at"
    )
    documents: Mapped[list["SupportCaseDocument"]] = relationship(cascade="all, delete-orphan")


class SupportCaseDocument(Base):
    """Uploaded documents linked to a case (doc 05 §2.19); owned by the case creator at link time."""

    __tablename__ = "support_case_documents"

    case_id: Mapped[UUID] = mapped_column(ForeignKey("support_cases.id", ondelete="CASCADE"), primary_key=True)
    uploaded_document_id: Mapped[UUID] = mapped_column(ForeignKey("uploaded_documents.id"), primary_key=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class SupportCaseEvent(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "support_case_events"
    __table_args__ = (
        CheckConstraint(f"event_type IN ({_in(CASE_EVENT_TYPES)})", name="event_type_valid"),
        Index(None, "case_id", "created_at"),
    )

    case_id: Mapped[UUID] = mapped_column(ForeignKey("support_cases.id", ondelete="CASCADE"))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    from_assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    to_assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    note: Mapped[str | None] = mapped_column(String(2000))


class PaRequirementSet(UUIDPrimaryKey, Synthetic, CreatedAt, Base):
    """A configured (fictional) documentation-requirement set. Its source is the ACTIVE version of the
    knowledge document `source_document_key`, resolved at query time (deviation D5-02)."""

    __tablename__ = "pa_requirement_sets"
    __table_args__ = (
        UniqueConstraint("procedure_code", "version"),
        CheckConstraint("procedure_code ~ '^SYN-PROC-[A-Z0-9-]{2,30}$'", name="procedure_code_format"),
        Index("uq_pa_requirement_sets_active_code", "procedure_code", unique=True, postgresql_where=text("is_active")),
    )

    procedure_code: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(150))
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    version: Mapped[str] = mapped_column(String(20))
    source_document_key: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    requirements: Mapped[list["PaRequirement"]] = relationship(
        cascade="all, delete-orphan", order_by="PaRequirement.display_order"
    )


class PaRequirement(UUIDPrimaryKey, Base):
    __tablename__ = "pa_requirements"
    __table_args__ = (
        UniqueConstraint("requirement_set_id", "requirement_code"),
        CheckConstraint(f"rule_type IN ({_in(RULE_TYPES)})", name="rule_type_valid"),
    )

    requirement_set_id: Mapped[UUID] = mapped_column(ForeignKey("pa_requirement_sets.id", ondelete="CASCADE"))
    requirement_code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(300))
    is_mandatory: Mapped[bool] = mapped_column(server_default=text("true"))
    rule_type: Mapped[str] = mapped_column(String(30))
    rule_params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # Exact phrase from the source document; used to locate (and verify) the supporting passage.
    source_phrase: Mapped[str] = mapped_column(String(300))
    display_order: Mapped[int]


class ToolInvocation(UUIDPrimaryKey, CreatedAt, Base):
    """Every tool request the orchestrator received, including rejected ones (doc 05 §2.23)."""

    __tablename__ = "tool_invocations"
    __table_args__ = (
        CheckConstraint(f"result_status IN ({_in(TOOL_RESULT_STATUSES)})", name="result_status_valid"),
        Index(None, "created_at", "tool_name", "result_status"),
    )

    message_id: Mapped[UUID | None] = mapped_column(ForeignKey("conversation_messages.id", ondelete="SET NULL"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tool_name: Mapped[str] = mapped_column(String(60))  # free text: unknown names are logged as received
    requested_by: Mapped[str] = mapped_column(String(20))  # "router" (deterministic) or "llm"
    arguments_redacted: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    result_status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[int]
