"""Administration (doc 06 §3.9). Read-only: there is no route that edits or deletes audit records."""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.db.session import get_db
from app.models.enums import AuditOutcome
from app.schemas.common import ErrorResponse
from app.schemas.support_case import AgentSummary
from app.services import admin_service, support_case_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/admin", tags=["administration"])
Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_ERRORS = {s: {"model": ErrorResponse} for s in (401, 403, 422)}
From = Annotated[date | None, Query(alias="from")]
To = Annotated[date | None, Query(alias="to")]


@router.get("/metrics", responses=_ERRORS, summary="Aggregate operational counts for a UTC date range (≤366 days)")
def get_metrics(
    db: Db, audit: Audit, principal: Annotated[Principal, Depends(require_any_permission(Permission.METRICS_READ))],
    date_from: From = None, date_to: To = None,
) -> dict[str, Any]:
    result = admin_service.metrics(db, date_from, date_to)
    audit.record("ADMIN_METRICS_VIEWED", AuditOutcome.SUCCESS, actor=principal, resource_type="admin_metrics")
    return result


@router.get("/knowledge-gaps", responses=_ERRORS, summary="Unanswered/conflicting question topics (aggregated)")
def get_knowledge_gaps(
    db: Db, audit: Audit,
    principal: Annotated[Principal, Depends(require_any_permission(Permission.KNOWLEDGE_GAPS_READ))],
    date_from: From = None, date_to: To = None,
) -> dict[str, Any]:
    result = admin_service.knowledge_gaps(db, date_from, date_to)
    audit.record("KNOWLEDGE_GAPS_VIEWED", AuditOutcome.SUCCESS, actor=principal, resource_type="knowledge_gaps")
    return result


@router.get("/audit-events", responses=_ERRORS, summary="Audit events, newest first (read-only)")
def get_audit_events(
    db: Db, audit: Audit, principal: Annotated[Principal, Depends(require_any_permission(Permission.AUDIT_READ))],
    date_from: Annotated[datetime | None, Query(alias="from")] = None,
    date_to: Annotated[datetime | None, Query(alias="to")] = None,
    action: Annotated[str | None, Query(pattern=r"^[A-Z_]{3,60}$")] = None,
    outcome: Annotated[Literal["SUCCESS", "DENIED", "FAILURE"] | None, Query()] = None,
    actor_user_id: UUID | None = None,
    resource_type: Annotated[str | None, Query(pattern=r"^[a-z_]{2,40}$")] = None,
    resource_ref: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    result = admin_service.audit_events(
        db, date_from=date_from, date_to=date_to, action=action, outcome=outcome, actor_user_id=actor_user_id,
        resource_type=resource_type, resource_ref=resource_ref, limit=limit, cursor=cursor,
    )
    audit.record("AUDIT_EVENTS_VIEWED", AuditOutcome.SUCCESS, actor=principal, resource_type="audit_log")
    return result


@router.get("/support-agents", response_model=list[AgentSummary], responses=_ERRORS,
            summary="Active support agents (assignment targets)")
def get_support_agents(
    db: Db, principal: Annotated[Principal, Depends(require_any_permission(Permission.CASES_ASSIGN_ANY))],
) -> list[AgentSummary]:
    return support_case_service.list_agents(db)
