"""Conversation sessions, messages and validated citations (doc 05 §2.20–2.22)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAt, UUIDPrimaryKey

ANSWER_TYPES = (
    "DOCUMENT_GROUNDED",
    "TOOL_RESULT",
    "CLARIFICATION",
    "INSUFFICIENT_EVIDENCE",
    "UNSUPPORTED_REQUEST",
    "ERROR",
)
EVIDENCE_STATUSES = ("SUPPORTED", "INSUFFICIENT", "CONFLICTING", "VERIFIED_RECORD", "NOT_APPLICABLE")
CITATION_CHECKS = ("PASSED", "PARTIALLY_REMOVED", "ALL_INVALID_DOWNGRADED", "NOT_APPLICABLE")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class ConversationSession(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (Index(None, "user_id", "last_message_at"), Index(None, "expires_at"))

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # ownership
    title: Mapped[str] = mapped_column(String(120))
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )


class ConversationMessage(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("sender IN ('USER', 'ASSISTANT')", name="sender_valid"),
        CheckConstraint(f"answer_type IS NULL OR answer_type IN ({_in(ANSWER_TYPES)})", name="answer_type_valid"),
        CheckConstraint(
            f"evidence_status IS NULL OR evidence_status IN ({_in(EVIDENCE_STATUSES)})", name="evidence_status_valid"
        ),
        CheckConstraint(
            f"citation_check IS NULL OR citation_check IN ({_in(CITATION_CHECKS)})", name="citation_check_valid"
        ),
        CheckConstraint("char_length(content) <= 8000", name="content_length"),
        # Replays of the same client_message_id in a session are answered from storage.
        Index(
            "uq_conversation_messages_client_id",
            "session_id",
            "client_message_id",
            unique=True,
            postgresql_where=text("client_message_id IS NOT NULL"),
        ),
        Index(None, "session_id", "created_at"),
        Index(None, "created_at", "evidence_status"),
    )

    session_id: Mapped[UUID] = mapped_column(ForeignKey("conversation_sessions.id", ondelete="CASCADE"))
    sender: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    client_message_id: Mapped[UUID | None]
    reply_to_id: Mapped[UUID | None] = mapped_column(ForeignKey("conversation_messages.id", ondelete="CASCADE"))
    intent: Mapped[str | None] = mapped_column(String(40))
    answer_type: Mapped[str | None] = mapped_column(String(30))
    evidence_status: Mapped[str | None] = mapped_column(String(20))
    citation_check: Mapped[str | None] = mapped_column(String(30))
    escalation_offered: Mapped[bool] = mapped_column(server_default=text("false"))
    escalation_reason: Mapped[str | None] = mapped_column(String(40))
    proposed_actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    disclaimers: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    gap_topic: Mapped[str | None] = mapped_column(String(120))
    # Phase 5: summaries of tool calls and the verified structured records shown with the answer.
    tool_executions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    records: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    latency_ms: Mapped[int | None]

    session: Mapped[ConversationSession] = relationship(back_populates="messages")
    citations: Mapped[list["MessageCitation"]] = relationship(
        cascade="all, delete-orphan", order_by="MessageCitation.marker"
    )


class MessageCitation(UUIDPrimaryKey, Base):
    """A citation shown with an answer. Display fields are snapshotted so history stays readable
    even if a document is later re-indexed (its chunks are replaced and chunk_id becomes NULL)."""

    __tablename__ = "message_citations"
    __table_args__ = (UniqueConstraint("message_id", "marker"),)

    message_id: Mapped[UUID] = mapped_column(ForeignKey("conversation_messages.id", ondelete="CASCADE"))
    chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"))
    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="RESTRICT"))
    marker: Mapped[str] = mapped_column(String(10))
    retrieval_rank: Mapped[int]
    retrieval_score: Mapped[float] = mapped_column(Numeric(6, 4))
    document_title: Mapped[str] = mapped_column(String(250))
    document_version: Mapped[str] = mapped_column(String(30))
    document_type: Mapped[str] = mapped_column(String(30))
    effective_date: Mapped[str | None] = mapped_column(String(10))
    section_heading: Mapped[str | None] = mapped_column(String(300))
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    excerpt: Mapped[str] = mapped_column(String(400))

class UserFeedback(UUIDPrimaryKey, CreatedAt, Base):
    """A user's rating of one of their own assistant messages (doc 05 §2.25, FR-034). One per
    message per user; re-rating updates the row."""

    __tablename__ = "user_feedback"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id"),
        CheckConstraint("rating IN ('HELPFUL', 'NOT_HELPFUL')", name="rating_valid"),
    )

    message_id: Mapped[UUID] = mapped_column(ForeignKey("conversation_messages.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
