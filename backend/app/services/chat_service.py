"""Chat sessions, persistence, idempotency and audit around the chat orchestrator (FR-004, FR-007,
FR-017). The tool executor is built here from the authenticated principal and the owned session."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.authz.dependencies import Principal
from app.authz.permissions import Permission
from app.core.config import Settings
from app.core.exceptions import AppError, NotFoundError, RateLimitedError
from app.models import ConversationMessage, ConversationSession, MessageCitation
from app.models.enums import AuditOutcome
from app.rag import pipeline
from app.rag.embeddings import Embedder
from app.rag.errors import AIServiceUnavailableError
from app.rag.generation import Generator
from app.rag.retrieval import RetrievalScope
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Citation,
    Escalation,
    HistoryMessage,
    ProposedAction,
    Record,
    SessionDetail,
    SessionPage,
    SessionSummary,
    ToolExecution,
)
from app.services.audit_service import AuditService
from app.tools.executor import ToolContext, ToolExecutor

logger = logging.getLogger(__name__)


class ChatPersistenceError(AppError):
    status_code = 500
    code = "CHAT_PERSISTENCE_FAILED"
    message = "Your message couldn't be saved. Please try again."


def _owned_session(db: Session, audit: AuditService, principal: Principal, session_id: UUID) -> ConversationSession:
    row = db.get(ConversationSession, session_id)
    now = datetime.now(UTC)
    if row is None or row.user_id != principal.user_id or row.expires_at <= now:
        reason = "NOT_EXISTS" if row is None else ("NOT_OWNER" if row.user_id != principal.user_id else "EXPIRED")
        audit.record(
            "ACCESS_DENIED",
            AuditOutcome.DENIED,
            actor=principal,
            resource_type="conversation_session",
            resource_ref=str(session_id),
            reason_code=reason,
        )
        raise NotFoundError()
    return row


def _history(db: Session, session_id: UUID, limit: int, before: datetime) -> list[tuple[str, str]]:
    if limit <= 0:
        return []
    rows = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id, ConversationMessage.created_at < before)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    ).all()
    return [("user" if m.sender == "USER" else "assistant", m.content[:600]) for m in reversed(rows)]


def _citation(c: MessageCitation) -> Citation:
    return Citation(
        marker=c.marker,
        chunk_id=c.chunk_id,
        document_id=c.document_id,
        document_title=c.document_title,
        document_type=c.document_type,
        document_version=c.document_version,
        effective_date=c.effective_date,
        section_heading=c.section_heading,
        page_start=c.page_start,
        page_end=c.page_end,
        excerpt=c.excerpt,
    )


def _response(session_id: UUID, msg: ConversationMessage, intent: str) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        message_id=msg.id,
        intent=intent,
        answer_type=msg.answer_type,
        evidence_status=msg.evidence_status,
        answer_text=msg.content,
        citations=[_citation(c) for c in msg.citations],
        tool_executions=[ToolExecution(**t) for t in msg.tool_executions],
        records=[Record(**r) for r in msg.records],
        proposed_actions=[ProposedAction(**a) for a in msg.proposed_actions],
        escalation=Escalation(offered=msg.escalation_offered, reason=msg.escalation_reason),
        disclaimers=list(msg.disclaimers),
        latency_ms=msg.latency_ms or 0,
        created_at=msg.created_at,
    )


def handle_message(
    db: Session,
    settings: Settings,
    audit: AuditService,
    embedder: Embedder,
    generator: Generator,
    principal: Principal,
    body: ChatRequest,
) -> ChatResponse:
    started = time.perf_counter()
    now = datetime.now(UTC)

    if body.session_id:
        session = _owned_session(db, audit, principal, body.session_id)
    else:
        session = ConversationSession(
            user_id=principal.user_id,
            title=body.message[:60],
            expires_at=now + timedelta(days=settings.chat_session_retention_days),
        )
        db.add(session)
        db.flush()

    # Idempotent replay: the same client_message_id in this session is never processed twice.
    user_msg = db.scalars(
        select(ConversationMessage).where(
            ConversationMessage.session_id == session.id,
            ConversationMessage.client_message_id == body.client_message_id,
        )
    ).first()
    if user_msg is not None:
        reply = db.scalars(
            select(ConversationMessage)
            .options(selectinload(ConversationMessage.citations))
            .where(ConversationMessage.reply_to_id == user_msg.id)
        ).first()
        if reply is not None:
            return _response(session.id, reply, user_msg.intent or "GENERAL_FAQ")
    else:
        recent = db.scalar(
            select(func.count())
            .select_from(ConversationMessage)
            .join(ConversationSession)
            .where(
                ConversationSession.user_id == principal.user_id,
                ConversationMessage.sender == "USER",
                ConversationMessage.created_at >= now - timedelta(minutes=1),
            )
        )
        if recent >= settings.chat_rate_limit_per_minute:
            raise RateLimitedError(60)
        user_msg = ConversationMessage(
            session_id=session.id, sender="USER", content=body.message, client_message_id=body.client_message_id
        )
        db.add(user_msg)
        try:
            db.commit()  # the question is kept even if answering fails below
        except SQLAlchemyError:
            db.rollback()
            raise ChatPersistenceError() from None

    history = _history(db, session.id, settings.chat_history_messages, before=user_msg.created_at)
    executor = ToolExecutor(
        ToolContext(db=db, audit=audit, principal=principal, session_id=session.id, message_id=user_msg.id),
        max_calls=settings.tool_max_calls_per_message,
        requested_by="llm" if generator.name == "anthropic" else "router",
    )
    ctx = pipeline.TurnContext(
        question=body.message,
        history=history,
        scope=RetrievalScope.for_user(principal.role, principal.plan_id),
        executor=executor,
        session_id=session.id,
        can_view_claims=principal.has(Permission.CLAIMS_READ_OWN),
        can_create_cases=principal.has(Permission.CASES_CREATE),
        can_read_cases=principal.has(Permission.CASES_READ_OWN),
        can_check_readiness=principal.has(Permission.READINESS_CREATE),
    )
    try:
        result = pipeline.run(db, settings, embedder, generator, ctx)
    except AIServiceUnavailableError as exc:
        logger.error("chat_ai_unavailable", extra={"reason": exc.reason})
        audit.record(
            "CHAT_MESSAGE_FAILED",
            AuditOutcome.FAILURE,
            actor=principal,
            resource_type="conversation_message",
            resource_ref=str(user_msg.id),
            reason_code=exc.reason[:50],
        )
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    user_msg.intent = result.intent
    reply = ConversationMessage(
        session_id=session.id,
        sender="ASSISTANT",
        content=result.answer_text,
        reply_to_id=user_msg.id,
        intent=result.intent,
        answer_type=result.answer_type,
        evidence_status=result.evidence_status,
        citation_check=result.citation_check,
        escalation_offered=result.escalation_reason is not None,
        escalation_reason=result.escalation_reason,
        proposed_actions=[a.__dict__ for a in result.actions],
        disclaimers=result.disclaimers,
        gap_topic=result.gap_topic,
        latency_ms=latency_ms,
        tool_executions=[{"tool_name": t.tool_name, "result_status": t.status, "summary": t.summary}
                         for t in result.tool_results],
        records=result.records,
    )
    reply.citations = [
        MessageCitation(
            chunk_id=i.candidate.chunk_id,
            document_id=i.candidate.document_id,
            marker=i.marker,
            retrieval_rank=int(i.marker[1:]),
            retrieval_score=round(i.candidate.similarity, 4),
            document_title=i.candidate.title,
            document_version=i.candidate.version,
            document_type=i.candidate.document_type,
            effective_date=i.candidate.effective_date.isoformat() if i.candidate.effective_date else None,
            section_heading=i.candidate.section_heading,
            page_start=i.candidate.page_start,
            page_end=i.candidate.page_end,
            excerpt=pipeline.excerpt(i.candidate),
        )
        for i in result.cited
    ]
    session.last_message_at = datetime.now(UTC)
    db.add(reply)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise ChatPersistenceError() from None
    db.refresh(reply)

    audit.record(
        "CHAT_MESSAGE_PROCESSED",
        AuditOutcome.SUCCESS,
        actor=principal,
        resource_type="conversation_message",
        resource_ref=str(reply.id),
        metadata={
            "intent": result.intent,
            "answer_type": result.answer_type,
            "evidence_status": result.evidence_status,
            "citation_check": result.citation_check,
            "latency_ms": latency_ms,
            "document_ids": result.retrieved_document_ids,
            "chunk_count": len(result.cited),
        },
    )
    logger.info(
        "chat_answered",
        extra={
            "intent": result.intent,
            "evidence_status": result.evidence_status,
            "citations": len(result.cited),
            "retrieval_ms": result.retrieval_ms,
            "generation_ms": result.generation_ms,
            "latency_ms": latency_ms,
        },
    )
    return _response(session.id, reply, result.intent)


def list_sessions(db: Session, principal: Principal, limit: int) -> SessionPage:
    rows = db.scalars(
        select(ConversationSession)
        .where(ConversationSession.user_id == principal.user_id, ConversationSession.expires_at > datetime.now(UTC))
        .order_by(ConversationSession.last_message_at.desc())
        .limit(limit)
    ).all()
    return SessionPage(
        items=[
            SessionSummary(session_id=s.id, title=s.title, last_message_at=s.last_message_at, created_at=s.created_at)
            for s in rows
        ]
    )


def get_session(db: Session, audit: AuditService, principal: Principal, session_id: UUID) -> SessionDetail:
    session = _owned_session(db, audit, principal, session_id)
    messages = db.scalars(
        select(ConversationMessage)
        .options(selectinload(ConversationMessage.citations))
        .where(ConversationMessage.session_id == session.id)
        .order_by(ConversationMessage.created_at)
    ).all()
    return SessionDetail(
        session_id=session.id,
        title=session.title,
        messages=[
            HistoryMessage(
                message_id=m.id,
                sender=m.sender,
                content=m.content,
                intent=m.intent,
                answer_type=m.answer_type,
                evidence_status=m.evidence_status,
                citations=[_citation(c) for c in m.citations],
                tool_executions=[ToolExecution(**t) for t in m.tool_executions],
                records=[Record(**r) for r in m.records],
                proposed_actions=[ProposedAction(**a) for a in m.proposed_actions],
                disclaimers=list(m.disclaimers),
                created_at=m.created_at,
            )
            for m in messages
        ],
    )
