"""Support cases: creation (Phase 5), queue/detail/update for human review (Phase 7, doc 02 Workflow
E–F, doc 06 §3.8).

Guarantees:
- creator, status (OPEN), case number and version are set server-side; linked session, claim,
  checklist and documents must belong to the creator;
- one Idempotency-Key per creator creates at most one case (unique constraint + replay);
- every change is validated by app.cases.workflow, applied under a row lock with an optimistic
  version check, and committed together with its history event(s) and audit row(s); a rejected
  change writes a FAILURE audit row and changes nothing;
- list scopes are enforced from the caller's permissions, never from client filters.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.authz.dependencies import Principal
from app.authz.permissions import Permission
from app.cases import workflow
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models import (
    AuthorizationChecklist,
    Claim,
    ConversationMessage,
    ConversationSession,
    SupportCase,
    SupportCaseDocument,
    SupportCaseEvent,
    UploadedDocument,
    User,
)
from app.models.enums import AuditOutcome
from app.schemas.support_case import (
    AgentSummary,
    CaseDetail,
    CaseDocument,
    CaseEvent,
    CasePage,
    CaseSummary,
    CreateCaseRequest,
    ExcerptMessage,
    Person,
    UpdateCaseRequest,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)
EXCERPT_MESSAGES = 6  # doc 06 §3.8: last 6 messages, assigned agent only
_REVIEW_STATE = {"IN_PROGRESS": "UNDER_REVIEW", "AWAITING_USER": "UNDER_REVIEW", "RESOLVED": "REVIEW_COMPLETED",
                 "CLOSED": "REVIEW_COMPLETED", "CANCELLED": "NOT_SUBMITTED"}


class CaseCreationFailedError(AppError):
    status_code = 500
    code = "CASE_CREATION_FAILED"
    message = "Your support case was not created. Please try again."


class IdempotencyKeyReusedError(AppError):
    status_code = 409
    code = "IDEMPOTENCY_KEY_REUSED"
    message = "This request key was already used for a different support case."


class InvalidStatusTransitionError(AppError):
    status_code = 409
    code = "INVALID_STATUS_TRANSITION"
    message = "That status change isn't allowed for this case."


class VersionConflictError(AppError):
    status_code = 409
    code = "VERSION_CONFLICT"
    message = "The case was changed by someone else. Reload it and try again."


class InvalidAssigneeError(AppError):
    status_code = 422
    code = "INVALID_ASSIGNEE"
    message = "Cases can only be assigned to an active support agent."


class CaseUpdateInvalidError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The update is missing required information."


class InvalidScopeError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You don't have permission to view that list of cases."


def _hash(body: CreateCaseRequest) -> str:
    return hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def _existing(db: Session, principal: Principal, key: UUID) -> SupportCase | None:
    return db.scalars(
        select(SupportCase)
        .options(selectinload(SupportCase.events))
        .where(SupportCase.created_by_user_id == principal.user_id, SupportCase.idempotency_key == key)
    ).first()


def _deny(audit: AuditService, principal: Principal, resource_type: str, ref: str, reason: str = "NOT_OWNER"):
    audit.record("ACCESS_DENIED", AuditOutcome.DENIED, actor=principal, resource_type=resource_type,
                 resource_ref=ref, reason_code=reason)
    raise NotFoundError()


# --- creation ---------------------------------------------------------------------------------------


def create_case(
    db: Session, audit: AuditService, principal: Principal, body: CreateCaseRequest, idempotency_key: UUID
) -> tuple[CaseDetail, bool]:
    """Returns (case, created). created=False means an idempotent replay of an earlier request."""
    request_hash = _hash(body)
    existing = _existing(db, principal, idempotency_key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyKeyReusedError()
        return _detail(db, existing, principal), False

    related_claim_id = None
    if body.related_session_id is not None:
        session = db.get(ConversationSession, body.related_session_id)
        if session is None or session.user_id != principal.user_id:
            _deny(audit, principal, "conversation_session", str(body.related_session_id))
    if body.related_claim_number is not None:
        claim = db.scalars(select(Claim).where(Claim.claim_number == body.related_claim_number)).first()
        if claim is None or principal.member_id is None or claim.member_id != principal.member_id:
            _deny(audit, principal, "claim", body.related_claim_number)
        related_claim_id = claim.id
    checklist = None
    if body.related_checklist_id is not None:
        checklist = db.get(AuthorizationChecklist, body.related_checklist_id)
        if checklist is None or checklist.created_by_user_id != principal.user_id:
            _deny(audit, principal, "authorization_checklist", str(body.related_checklist_id))
    now = datetime.now(UTC)
    for doc_id in dict.fromkeys(body.document_ids):
        doc = db.get(UploadedDocument, doc_id)
        if doc is None or doc.owner_user_id != principal.user_id or doc.deleted_at or doc.expires_at <= now:
            _deny(audit, principal, "uploaded_document", str(doc_id))

    try:
        number = db.scalar(text("SELECT nextval('support_case_number_seq')"))
        case = SupportCase(
            case_number=f"CASE-{now.year}-{number:06d}",
            created_by_user_id=principal.user_id,
            category=body.category,
            status="OPEN",
            escalation_reason=body.escalation_reason,
            summary=body.summary,
            related_session_id=body.related_session_id,
            related_claim_id=related_claim_id,
            related_checklist_id=body.related_checklist_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        case.events = [SupportCaseEvent(actor_user_id=principal.user_id, event_type="CREATED", to_status="OPEN")]
        case.documents = [SupportCaseDocument(uploaded_document_id=d) for d in dict.fromkeys(body.document_ids)]
        if checklist is not None and checklist.review_state == "NOT_SUBMITTED":
            checklist.review_state = "AWAITING_REVIEW"  # doc 02 §3.6
        db.add(case)
        db.flush()
        audit.add_to_transaction(
            db, "SUPPORT_CASE_CREATED", AuditOutcome.SUCCESS, actor=principal, resource_type="support_case",
            resource_ref=case.case_number,
            metadata={"category": body.category, "escalation_reason": body.escalation_reason},
        )
        db.commit()
    except IntegrityError:
        # A concurrent request with the same key won the race: return its case (or reject a different body).
        db.rollback()
        existing = _existing(db, principal, idempotency_key)
        if existing is None:
            raise CaseCreationFailedError() from None
        if existing.request_hash != request_hash:
            raise IdempotencyKeyReusedError() from None
        return _detail(db, existing, principal), False
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("case_creation_failed", extra={"error_type": type(exc).__name__})
        audit.record("SUPPORT_CASE_CREATE_FAILED", AuditOutcome.FAILURE, actor=principal,
                     resource_type="support_case", metadata={"category": body.category})
        raise CaseCreationFailedError() from None
    db.refresh(case)
    return _detail(db, case, principal), True


# --- access -----------------------------------------------------------------------------------------


def _view(case: SupportCase, p: Principal) -> str | None:
    """'full' (creator, assigned agent), 'summary' (agent on an unassigned OPEN case, admin) or None."""
    if case.created_by_user_id == p.user_id and p.has(Permission.CASES_READ_OWN):
        return "full"
    if case.assigned_to_user_id == p.user_id and p.has(Permission.CASES_READ_ASSIGNED):
        return "full"
    if p.has(Permission.CASES_READ_QUEUE) and case.status == "OPEN" and case.assigned_to_user_id is None:
        return "summary"
    if p.has(Permission.CASES_READ_METADATA_ALL):
        return "summary"
    return None


def _encode_cursor(c: SupportCase) -> str:
    raw = json.dumps([c.updated_at.isoformat(), str(c.id)]).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        ts, case_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(ts), UUID(case_id)
    except (ValueError, TypeError):
        raise CaseUpdateInvalidError("The page cursor is invalid.") from None


SCOPES = {
    "mine": Permission.CASES_READ_OWN,
    "queue": Permission.CASES_READ_QUEUE,
    "assigned": Permission.CASES_READ_ASSIGNED,
    "all": Permission.CASES_READ_METADATA_ALL,
}


def default_scope(p: Principal) -> str:
    for scope in ("mine", "assigned", "all"):
        if p.has(SCOPES[scope]):
            return scope
    raise InvalidScopeError()


def list_cases(db: Session, principal: Principal, *, scope: str | None = None, statuses: list[str] | None = None,
               category: str | None = None, case_number: str | None = None, created_from: datetime | None = None,
               created_to: datetime | None = None, limit: int = 20, cursor: str | None = None) -> CasePage:
    scope = scope or default_scope(principal)
    if scope not in SCOPES or not principal.has(SCOPES[scope]):
        raise InvalidScopeError()
    query = select(SupportCase)
    if scope == "mine":
        query = query.where(SupportCase.created_by_user_id == principal.user_id)
    elif scope == "queue":
        query = query.where(SupportCase.status == "OPEN", SupportCase.assigned_to_user_id.is_(None))
    elif scope == "assigned":
        query = query.where(SupportCase.assigned_to_user_id == principal.user_id)
    if statuses:
        query = query.where(SupportCase.status.in_(statuses))
    if category:
        query = query.where(SupportCase.category == category)
    if case_number:
        query = query.where(SupportCase.case_number == case_number.upper())
    if created_from:
        query = query.where(SupportCase.created_at >= created_from)
    if created_to:
        query = query.where(SupportCase.created_at < created_to)
    if cursor:
        ts, cid = _decode_cursor(cursor)
        query = query.where(or_(SupportCase.updated_at < ts, and_(SupportCase.updated_at == ts, SupportCase.id < cid)))
    rows = db.scalars(query.order_by(SupportCase.updated_at.desc(), SupportCase.id.desc()).limit(limit + 1)).all()
    page, more = rows[:limit], len(rows) > limit
    names = _names(db, {c.assigned_to_user_id for c in page})
    return CasePage(
        items=[
            CaseSummary(
                case_id=c.id, case_number=c.case_number, category=c.category, status=c.status,
                escalation_reason=c.escalation_reason, summary_preview=c.summary[:140],
                assigned_to=Person(id=c.assigned_to_user_id, display_name=names.get(c.assigned_to_user_id, "Unknown"))
                if c.assigned_to_user_id else None,
                created_at=c.created_at, updated_at=c.updated_at,
            )
            for c in page
        ],
        next_cursor=_encode_cursor(page[-1]) if more else None,
    )


def _load(db: Session, case_id: UUID, *, for_update: bool = False) -> SupportCase | None:
    q = select(SupportCase).options(selectinload(SupportCase.events), selectinload(SupportCase.documents)) \
        .where(SupportCase.id == case_id)
    return db.scalars(q.with_for_update(of=SupportCase) if for_update else q).first()


def get_case(db: Session, audit: AuditService, principal: Principal, case_id: UUID) -> CaseDetail:
    case = _load(db, case_id)
    if case is None or _view(case, principal) is None:
        _deny(audit, principal, "support_case", str(case_id), "NOT_EXISTS" if case is None else "NOT_ASSIGNED"
              if principal.role == "SUPPORT_AGENT" else "NOT_OWNER")
    if case.created_by_user_id != principal.user_id:
        audit.record("SUPPORT_CASE_VIEWED", AuditOutcome.SUCCESS, actor=principal, resource_type="support_case",
                     resource_ref=case.case_number)
    return _detail(db, case, principal)


def case_linked(db: Session, principal: Principal, *, checklist_id: UUID | None = None,
                document_id: UUID | None = None) -> bool:
    """True when `principal` is the assigned agent of a non-cancelled case linking the resource."""
    if principal.role != "SUPPORT_AGENT":
        return False
    q = select(func.count()).select_from(SupportCase).where(
        SupportCase.assigned_to_user_id == principal.user_id, SupportCase.status != "CANCELLED")
    if checklist_id is not None:
        q = q.where(SupportCase.related_checklist_id == checklist_id)
    if document_id is not None:
        q = q.join(SupportCaseDocument, SupportCaseDocument.case_id == SupportCase.id) \
            .where(SupportCaseDocument.uploaded_document_id == document_id)
    return bool(db.scalar(q))


# --- update -----------------------------------------------------------------------------------------


def update_case(db: Session, audit: AuditService, principal: Principal, case_id: UUID,
                body: UpdateCaseRequest) -> CaseDetail:
    case = _load(db, case_id, for_update=True)
    if case is None or _view(case, principal) is None:
        db.rollback()
        _deny(audit, principal, "support_case", str(case_id), "NOT_EXISTS" if case is None else "NOT_OWNER")

    def reject(error: AppError, reason: str) -> None:
        db.rollback()
        audit.record("SUPPORT_CASE_UPDATE_REJECTED", AuditOutcome.FAILURE, actor=principal,
                     resource_type="support_case", resource_ref=case.case_number, reason_code=reason,
                     metadata={"from_status": case.status, "to_status": body.status})
        raise error

    if body.version != case.version:
        reject(VersionConflictError(details=[{"field": "version", "issue": f"current version is {case.version}"}]),
               "VERSION_CONFLICT")
    if (body.assigned_to_user_id is not None or body.unassign) and not principal.has(Permission.CASES_ASSIGN_ANY):
        reject(ForbiddenError("Only administrators can assign cases to someone else."), "ROLE_NOT_PERMITTED")
    if body.assign_to_me and not principal.has(Permission.CASES_ASSIGN_SELF):
        reject(ForbiddenError(), "ROLE_NOT_PERMITTED")
    if principal.role == "SUPPORT_AGENT" and not principal.has(Permission.CASES_UPDATE_ASSIGNED):
        reject(ForbiddenError(), "ROLE_NOT_PERMITTED")

    assignee_ok = False
    if body.assigned_to_user_id is not None:
        target = db.get(User, body.assigned_to_user_id)
        assignee_ok = bool(target and target.role == "SUPPORT_AGENT" and target.account_status == "ACTIVE")
    change = workflow.Change(
        status=body.status, note=body.note, resolution_note=body.resolution_note, assign_to_me=body.assign_to_me,
        release=body.release, set_assignee=body.assigned_to_user_id is not None or body.unassign,
        assignee=body.assigned_to_user_id, assignee_is_active_agent=assignee_ok, reason=body.reason,
    )
    state = workflow.CaseState(case.status, case.created_by_user_id, case.assigned_to_user_id, case.resolved_at)
    try:
        outcome = workflow.apply(state, workflow.Actor(principal.user_id, principal.role), change)
    except workflow.WorkflowError as exc:
        errors = {
            "FORBIDDEN": ForbiddenError(exc.message),
            "INVALID_ASSIGNEE": InvalidAssigneeError(),
            "MISSING_FIELD": CaseUpdateInvalidError(exc.message, details=[{"field": exc.details.get("field"),
                                                                           "issue": "required"}]),
            "INVALID_STATUS_TRANSITION": InvalidStatusTransitionError(
                exc.message, details=[{"field": "status", "issue": f"{exc.details.get('frm')} -> "
                                                                   f"{exc.details.get('to')}"}]),
        }
        reject(errors.get(exc.kind, CaseUpdateInvalidError(exc.message)), exc.kind)

    now = datetime.now(UTC)
    old_status = case.status
    case.status = outcome.new_status
    case.assigned_to_user_id = outcome.new_assignee
    if outcome.resolution_note is not None:
        case.resolution_note = outcome.resolution_note
    if case.status == "RESOLVED" and old_status != "RESOLVED":
        case.resolved_at = now
    if case.status == "CLOSED":
        case.closed_at = now
    if old_status == "RESOLVED" and case.status == "IN_PROGRESS":
        case.resolved_at = None  # reopened
    case.version += 1
    case.updated_at = now
    for e in outcome.events:
        db.add(SupportCaseEvent(case_id=case.id, actor_user_id=principal.user_id, **e))
        action = {"ASSIGNED": "SUPPORT_CASE_ASSIGNED", "UNASSIGNED": "SUPPORT_CASE_UNASSIGNED",
                  "NOTE_ADDED": "SUPPORT_CASE_NOTE_ADDED"}.get(e["event_type"], "SUPPORT_CASE_STATUS_CHANGED")
        meta = {"from_status": e["from_status"], "to_status": e["to_status"]} if e["to_status"] else {}
        audit.add_to_transaction(db, action, AuditOutcome.SUCCESS, actor=principal, resource_type="support_case",
                                 resource_ref=case.case_number, metadata=meta)
    if case.related_checklist_id and case.status in _REVIEW_STATE:
        checklist = db.get(AuthorizationChecklist, case.related_checklist_id)
        if checklist is not None:
            checklist.review_state = _REVIEW_STATE[case.status]
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("case_update_failed", extra={"error_type": type(exc).__name__})
        audit.record("SUPPORT_CASE_UPDATE_REJECTED", AuditOutcome.FAILURE, actor=principal,
                     resource_type="support_case", resource_ref=str(case_id), reason_code="DATABASE_ERROR")
        raise AppError("The case could not be updated. Nothing was changed.") from None
    # Expire cached state first: otherwise the identity map returns the events collection loaded
    # before this change, and the response would omit the history row just written (found in Phase 8).
    db.expire_all()
    fresh = _load(db, case_id)
    return _detail(db, fresh, principal)


# --- agents and detail -------------------------------------------------------------------------------


def list_agents(db: Session) -> list[AgentSummary]:
    counts = dict(db.execute(
        select(SupportCase.assigned_to_user_id, func.count())
        .where(SupportCase.assigned_to_user_id.is_not(None),
               SupportCase.status.in_(("ASSIGNED", "IN_PROGRESS", "AWAITING_USER")))
        .group_by(SupportCase.assigned_to_user_id)
    ).all())
    agents = db.scalars(select(User).where(User.role == "SUPPORT_AGENT", User.account_status == "ACTIVE")
                        .order_by(User.display_name)).all()
    return [AgentSummary(id=a.id, display_name=a.display_name, open_assigned_count=counts.get(a.id, 0))
            for a in agents]


def _names(db: Session, ids) -> dict[UUID, str]:
    ids = {i for i in ids if i}
    return {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


def _detail(db: Session, case: SupportCase, principal: Principal) -> CaseDetail:
    view = _view(case, principal) or "summary"
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(
        {e.actor_user_id for e in case.events} | {case.created_by_user_id} | ({case.assigned_to_user_id} - {None}))))}
    full = view == "full"
    claim = db.get(Claim, case.related_claim_id) if case.related_claim_id and full else None
    documents: list[CaseDocument] = []
    excerpt: list[ExcerptMessage] = []
    if full:
        ids = [d.uploaded_document_id for d in case.documents]
        if ids:
            documents = [CaseDocument(document_id=d.id, original_filename=d.original_filename)
                         for d in db.scalars(select(UploadedDocument).where(UploadedDocument.id.in_(ids)))]
        if case.related_session_id and case.assigned_to_user_id == principal.user_id:
            rows = db.scalars(select(ConversationMessage)
                              .where(ConversationMessage.session_id == case.related_session_id)
                              .order_by(ConversationMessage.created_at.desc()).limit(EXCERPT_MESSAGES)).all()
            excerpt = [ExcerptMessage(sender=m.sender, content=m.content[:1000], created_at=m.created_at)
                       for m in reversed(rows)]
    creator, assignee = users.get(case.created_by_user_id), users.get(case.assigned_to_user_id)
    state = workflow.CaseState(case.status, case.created_by_user_id, case.assigned_to_user_id, case.resolved_at)
    return CaseDetail(
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        status=case.status,
        escalation_reason=case.escalation_reason,
        summary=case.summary,
        related_session_id=case.related_session_id if full else None,
        related_claim_number=claim.claim_number if claim else None,
        related_claim_status=claim.status if claim else None,
        related_checklist_id=case.related_checklist_id if full else None,
        resolution_note=case.resolution_note,
        version=case.version,
        events=[
            CaseEvent(event_type=e.event_type, from_status=e.from_status, to_status=e.to_status,
                      note=e.note if full else None,  # notes: creator and assigned agent only (doc 05 §2.18)
                      actor_display_name=users[e.actor_user_id].display_name if e.actor_user_id in users
                      else "Unknown", created_at=e.created_at)
            for e in case.events
        ],
        created_at=case.created_at,
        updated_at=case.updated_at,
        resolved_at=case.resolved_at,
        closed_at=case.closed_at,
        view=view,
        created_by=Person(display_name=creator.display_name, role=creator.role) if creator else None,
        assigned_to=Person(id=assignee.id, display_name=assignee.display_name) if assignee else None,
        documents=documents,
        conversation_excerpt=excerpt,
        allowed_actions=workflow.allowed_actions(state, workflow.Actor(principal.user_id, principal.role)),
    )
