"""Administrator reporting (doc 06 §3.9; definitions in docs/phase-7/dashboard-metrics.md).

Every number is a database aggregate over persisted records (SQL COUNT/GROUP BY/percentile), never
a constant or a frontend estimate. Periods are whole UTC days: [from 00:00, to + 1 day 00:00).
Outputs are counts only: no user identities, message text or document content."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Float, and_, cast, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import (
    AuditLog,
    AuthorizationChecklist,
    ConversationMessage,
    ConversationSession,
    DocumentProcessingJob,
    ExtractedField,
    SupportCase,
    ToolInvocation,
    User,
)
from app.models.document import JOB_STATUSES, READINESS_STATUSES
from app.models.support import CASE_CATEGORIES, CASE_STATUSES, ESCALATION_REASONS, TOOL_RESULT_STATUSES

MAX_RANGE_DAYS = 366
SMALL_GROUP = 3  # field-issue groups below this are reported as "<3" (doc 06 §3.9)
MIN_DISTINCT_USERS = 2  # knowledge-gap topics seen by fewer users are suppressed
EVIDENCE_STATUSES = ("SUPPORTED", "INSUFFICIENT", "CONFLICTING", "VERIFIED_RECORD", "NOT_APPLICABLE")
OPEN_WORK = ("OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_USER")


class InvalidPeriodError(AppError):
    status_code = 422
    code = "INVALID_PERIOD"
    message = "Choose a date range of at most 366 days with 'from' on or before 'to'."


def period(date_from: date | None, date_to: date | None, today: date | None = None) -> tuple[date, date, datetime,
                                                                                                datetime]:
    today = today or datetime.now(UTC).date()
    date_to = date_to or today
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to or (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise InvalidPeriodError()
    start = datetime.combine(date_from, time.min, tzinfo=UTC)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
    return date_from, date_to, start, end


def _zeros(keys) -> dict[str, int]:
    return dict.fromkeys(keys, 0)


def _grouped(db: Session, column, *where, keys=None) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*where).group_by(column)).all()
    out = _zeros(keys) if keys else {}
    out.update({str(k): v for k, v in rows if k is not None})
    return out


def metrics(db: Session, date_from: date | None, date_to: date | None) -> dict[str, Any]:
    d_from, d_to, start, end = period(date_from, date_to)
    in_period = lambda col: and_(col >= start, col < end)  # noqa: E731

    # --- chat (assistant messages carry intent/evidence; user messages are the questions) -----------
    assistant = and_(ConversationMessage.sender == "ASSISTANT", in_period(ConversationMessage.created_at))
    user_messages = db.scalar(select(func.count()).select_from(ConversationMessage).where(
        ConversationMessage.sender == "USER", in_period(ConversationMessage.created_at)))
    lat = db.execute(select(
        func.percentile_cont(0.5).within_group(ConversationMessage.latency_ms),
        func.percentile_cont(0.95).within_group(ConversationMessage.latency_ms),
        func.count(ConversationMessage.latency_ms),
    ).where(assistant, ConversationMessage.latency_ms.is_not(None))).one()

    # --- tools -----------------------------------------------------------------------------------------
    tools: dict[str, dict[str, int]] = {}
    for name, status, n in db.execute(
        select(ToolInvocation.tool_name, ToolInvocation.result_status, func.count())
        .where(in_period(ToolInvocation.created_at)).group_by(ToolInvocation.tool_name, ToolInvocation.result_status)
    ):
        tools.setdefault(name, _zeros(TOOL_RESULT_STATUSES))[status] = n

    # --- cases -----------------------------------------------------------------------------------------
    created = in_period(SupportCase.created_at)
    resolved_hours = db.scalar(select(func.percentile_cont(0.5).within_group(
        cast(func.extract("epoch", SupportCase.resolved_at - SupportCase.created_at), Float) / 3600.0))
        .where(SupportCase.resolved_at.is_not(None), in_period(SupportCase.resolved_at)))
    daily = db.execute(
        select(func.date_trunc("day", func.timezone("UTC", SupportCase.created_at)).label("d"), func.count())
        .where(created).group_by("d").order_by("d")
    ).all()
    resolved_daily = db.execute(
        select(func.date_trunc("day", func.timezone("UTC", SupportCase.resolved_at)).label("d"), func.count())
        .where(SupportCase.resolved_at.is_not(None), in_period(SupportCase.resolved_at)).group_by("d").order_by("d")
    ).all()
    current_status = _grouped(db, SupportCase.status, keys=CASE_STATUSES)

    # --- documents / readiness --------------------------------------------------------------------------
    field_issues = db.execute(
        select(ExtractedField.field_name, ExtractedField.validation_status, func.count())
        .join(DocumentProcessingJob, DocumentProcessingJob.id == ExtractedField.job_id)
        .where(ExtractedField.validation_status != "VALID", in_period(DocumentProcessingJob.created_at))
        .group_by(ExtractedField.field_name, ExtractedField.validation_status)
        .order_by(func.count().desc(), ExtractedField.field_name).limit(10)
    ).all()

    return {
        "data_environment": "SYNTHETIC_PROTOTYPE",
        "period": {"from": d_from.isoformat(), "to": d_to.isoformat(), "timezone": "UTC"},
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "chat": {
            "user_messages": user_messages,
            "assistant_messages": db.scalar(select(func.count()).select_from(ConversationMessage).where(assistant)),
            "by_intent": _grouped(db, ConversationMessage.intent, assistant),
            "by_evidence_status": _grouped(db, ConversationMessage.evidence_status, assistant, keys=EVIDENCE_STATUSES),
            "escalations_offered": db.scalar(select(func.count()).select_from(ConversationMessage).where(
                assistant, ConversationMessage.escalation_offered)),
            "latency_ms": {"p50": round(lat[0]) if lat[0] is not None else None,
                           "p95": round(lat[1]) if lat[1] is not None else None, "sample_size": lat[2]},
        },
        "tools": tools,
        "cases": {
            "created": db.scalar(select(func.count()).select_from(SupportCase).where(created)),
            "created_by_status": _grouped(db, SupportCase.status, created, keys=CASE_STATUSES),
            "created_by_category": _grouped(db, SupportCase.category, created, keys=CASE_CATEGORIES),
            "created_by_escalation_reason": _grouped(db, SupportCase.escalation_reason, created,
                                                     keys=ESCALATION_REASONS),
            "escalated_from_chat": db.scalar(select(func.count()).select_from(SupportCase).where(
                created, SupportCase.related_session_id.is_not(None))),
            "resolved_in_period": db.scalar(select(func.count()).select_from(SupportCase).where(
                SupportCase.resolved_at.is_not(None), in_period(SupportCase.resolved_at))),
            "median_hours_to_resolution": round(resolved_hours, 2) if resolved_hours is not None else None,
            "created_per_day": [{"date": d.date().isoformat(), "count": n} for d, n in daily],
            "resolved_per_day": [{"date": d.date().isoformat(), "count": n} for d, n in resolved_daily],
            # Snapshot (not period-bound): the current human-review workload.
            "current_by_status": current_status,
            "current_open_workload": sum(current_status[s] for s in OPEN_WORK),
            "current_unassigned_open": db.scalar(select(func.count()).select_from(SupportCase).where(
                SupportCase.status == "OPEN", SupportCase.assigned_to_user_id.is_(None))),
        },
        "documents": {
            "jobs_by_status": _grouped(db, DocumentProcessingJob.status, in_period(DocumentProcessingJob.created_at),
                                       keys=JOB_STATUSES),
            "failures_by_error_code": _grouped(db, DocumentProcessingJob.error_code,
                                               in_period(DocumentProcessingJob.created_at),
                                               DocumentProcessingJob.status == "FAILED"),
            "top_field_issues": [{"field_name": f, "status": s, "count": n if n >= SMALL_GROUP else "<3"}
                                 for f, s, n in field_issues],
        },
        "readiness": {
            "by_status": _grouped(db, AuthorizationChecklist.readiness_status,
                                  in_period(AuthorizationChecklist.created_at), keys=READINESS_STATUSES),
            "by_review_state": _grouped(db, AuthorizationChecklist.review_state,
                                        in_period(AuthorizationChecklist.created_at)),
        },
        "security": {
            "access_denied_events": db.scalar(select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "ACCESS_DENIED", in_period(AuditLog.occurred_at))),
            "rejected_case_updates": db.scalar(select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "SUPPORT_CASE_UPDATE_REJECTED", in_period(AuditLog.occurred_at))),
        },
        # Not collected by this build: no feedback endpoint/table exists yet (FR-034).
        "unavailable": ["feedback"],
    }


def knowledge_gaps(db: Session, date_from: date | None, date_to: date | None) -> dict[str, Any]:
    d_from, d_to, start, end = period(date_from, date_to)
    when = and_(ConversationMessage.created_at >= start, ConversationMessage.created_at < end)
    gap = and_(when, ConversationMessage.sender == "ASSISTANT",
               ConversationMessage.evidence_status.in_(("INSUFFICIENT", "CONFLICTING")),
               ConversationMessage.gap_topic.is_not(None))
    users = func.count(func.distinct(ConversationSession.user_id))
    rows = db.execute(
        select(ConversationMessage.gap_topic, ConversationMessage.evidence_status, func.count(), users,
               func.max(ConversationMessage.created_at), func.array_agg(func.distinct(ConversationMessage.intent)))
        .join(ConversationSession, ConversationSession.id == ConversationMessage.session_id)
        .where(gap).group_by(ConversationMessage.gap_topic, ConversationMessage.evidence_status)
        .order_by(func.count().desc(), ConversationMessage.gap_topic).limit(50)
    ).all()
    items = [
        {"gap_topic": topic, "evidence_status": status, "occurrences": n, "distinct_users": u,
         "last_seen_at": last.isoformat(timespec="seconds"), "example_intents": sorted(i for i in intents if i)}
        for topic, status, n, u, last, intents in rows if u >= MIN_DISTINCT_USERS
    ]
    suppressed = sum(1 for r in rows if r[3] < MIN_DISTINCT_USERS)
    by_intent = db.execute(
        select(ConversationMessage.intent, ConversationMessage.evidence_status, func.count())
        .where(when, ConversationMessage.sender == "ASSISTANT",
               ConversationMessage.evidence_status.in_(("INSUFFICIENT", "CONFLICTING")))
        .group_by(ConversationMessage.intent, ConversationMessage.evidence_status)
        .order_by(func.count().desc())
    ).all()
    tool_when = and_(ToolInvocation.created_at >= start, ToolInvocation.created_at < end)
    code = ToolInvocation.arguments_redacted["procedure_code"].astext.label("procedure_code")
    misses = db.execute(
        select(code, func.count())
        .where(tool_when, ToolInvocation.tool_name == "get_required_documents",
               ToolInvocation.result_status == "NOT_FOUND")
        .group_by(code.name).order_by(func.count().desc())
    ).all()
    failures = db.execute(
        select(ToolInvocation.tool_name, ToolInvocation.result_status, func.count())
        .where(tool_when, ToolInvocation.result_status == "EXECUTION_ERROR")
        .group_by(ToolInvocation.tool_name, ToolInvocation.result_status).order_by(func.count().desc())
    ).all()
    return {
        "data_environment": "SYNTHETIC_PROTOTYPE",
        "period": {"from": d_from.isoformat(), "to": d_to.isoformat(), "timezone": "UTC"},
        "items": items,
        "suppressed_topics": suppressed,
        "by_intent": [{"intent": i or "UNKNOWN", "evidence_status": s, "occurrences": n} for i, s, n in by_intent],
        "requirement_set_misses": [{"requested_procedure_code": c or "(by description)", "occurrences": n}
                                   for c, n in misses],
        "tool_failures": [{"tool_name": t, "result_status": s, "occurrences": n} for t, s, n in failures],
        "note": "Recommendations for knowledge-base review only. Nothing is added to the knowledge base "
                "automatically; AI service outages are not counted as gaps.",
    }


def audit_events(db: Session, *, date_from: datetime | None, date_to: datetime | None, action: str | None,
                 outcome: str | None, actor_user_id: UUID | None, resource_type: str | None,
                 resource_ref: str | None, limit: int, cursor: int | None) -> dict[str, Any]:
    q = select(AuditLog, User.display_name).outerjoin(User, User.id == AuditLog.actor_user_id)
    # Conditions are built only for supplied values (comparing a column with None is invalid SQL).
    filters = [
        (date_from, lambda v: AuditLog.occurred_at >= v), (date_to, lambda v: AuditLog.occurred_at < v),
        (action, lambda v: AuditLog.action == v), (outcome, lambda v: AuditLog.outcome == v),
        (actor_user_id, lambda v: AuditLog.actor_user_id == v),
        (resource_type, lambda v: AuditLog.resource_type == v), (resource_ref, lambda v: AuditLog.resource_ref == v),
        (cursor, lambda v: AuditLog.id < v),
    ]
    q = q.where(*[build(value) for value, build in filters if value is not None])
    rows = db.execute(q.order_by(AuditLog.id.desc()).limit(limit + 1)).all()
    page = rows[:limit]
    return {
        "items": [
            {"id": e.id, "occurred_at": e.occurred_at.isoformat(timespec="seconds"),
             "request_id": str(e.request_id) if e.request_id else None,
             "actor": {"id": str(e.actor_user_id), "display_name": name or "Unknown", "role": e.actor_role}
             if e.actor_user_id else None,
             "action": e.action, "resource_type": e.resource_type, "resource_ref": e.resource_ref,
             "outcome": e.outcome, "reason_code": e.reason_code, "metadata": e.event_metadata}
            for e, name in page
        ],
        "next_cursor": str(page[-1][0].id) if len(rows) > limit else None,
    }
