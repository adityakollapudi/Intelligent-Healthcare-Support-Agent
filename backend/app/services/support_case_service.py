"""Support-case creation and read access for creators (FR-025, FR-027).

Creation is the only write reachable from the assistant, and only through the confirmed
POST /support-cases request (the assistant's create_support_case tool never writes). Guarantees:
- creator, status (OPEN) and case number are set server-side;
- linked session/claim must belong to the creator;
- one Idempotency-Key per creator creates at most one case (unique constraint + replay);
- the case, its CREATED event and the SUPPORT_CASE_CREATED audit row commit in one transaction,
  so there is never a case without its audit record, or an audit record for a case that failed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.authz.dependencies import Principal
from app.core.exceptions import AppError, NotFoundError
from app.models import Claim, ConversationSession, SupportCase, SupportCaseEvent, User
from app.models.enums import AuditOutcome
from app.schemas.support_case import CaseDetail, CaseEvent, CasePage, CaseSummary, CreateCaseRequest
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class CaseCreationFailedError(AppError):
    status_code = 500
    code = "CASE_CREATION_FAILED"
    message = "Your support case was not created. Please try again."


class IdempotencyKeyReusedError(AppError):
    status_code = 409
    code = "IDEMPOTENCY_KEY_REUSED"
    message = "This request key was already used for a different support case."


def _hash(body: CreateCaseRequest) -> str:
    return hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def _existing(db: Session, principal: Principal, key: UUID) -> SupportCase | None:
    return db.scalars(
        select(SupportCase)
        .options(selectinload(SupportCase.events))
        .where(SupportCase.created_by_user_id == principal.user_id, SupportCase.idempotency_key == key)
    ).first()


def create_case(
    db: Session, audit: AuditService, principal: Principal, body: CreateCaseRequest, idempotency_key: UUID
) -> tuple[CaseDetail, bool]:
    """Returns (case, created). created=False means an idempotent replay of an earlier request."""
    request_hash = _hash(body)
    existing = _existing(db, principal, idempotency_key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyKeyReusedError()
        return _detail(db, existing), False

    related_claim_id = None
    if body.related_session_id is not None:
        session = db.get(ConversationSession, body.related_session_id)
        if session is None or session.user_id != principal.user_id:
            audit.record(
                "ACCESS_DENIED",
                AuditOutcome.DENIED,
                actor=principal,
                resource_type="conversation_session",
                resource_ref=str(body.related_session_id),
                reason_code="NOT_OWNER",
            )
            raise NotFoundError()
    if body.related_claim_number is not None:
        claim = db.scalars(select(Claim).where(Claim.claim_number == body.related_claim_number)).first()
        if claim is None or principal.member_id is None or claim.member_id != principal.member_id:
            audit.record(
                "ACCESS_DENIED",
                AuditOutcome.DENIED,
                actor=principal,
                resource_type="claim",
                resource_ref=body.related_claim_number,
                reason_code="NOT_OWNER",
            )
            raise NotFoundError()
        related_claim_id = claim.id

    try:
        number = db.scalar(text("SELECT nextval('support_case_number_seq')"))
        case = SupportCase(
            case_number=f"CASE-{datetime.now(UTC).year}-{number:06d}",
            created_by_user_id=principal.user_id,
            category=body.category,
            status="OPEN",
            escalation_reason=body.escalation_reason,
            summary=body.summary,
            related_session_id=body.related_session_id,
            related_claim_id=related_claim_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        case.events = [SupportCaseEvent(actor_user_id=principal.user_id, event_type="CREATED", to_status="OPEN")]
        db.add(case)
        db.flush()
        audit.add_to_transaction(
            db,
            "SUPPORT_CASE_CREATED",
            AuditOutcome.SUCCESS,
            actor=principal,
            resource_type="support_case",
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
        return _detail(db, existing), False
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("case_creation_failed", extra={"error_type": type(exc).__name__})
        audit.record(
            "SUPPORT_CASE_CREATE_FAILED",
            AuditOutcome.FAILURE,
            actor=principal,
            resource_type="support_case",
            metadata={"category": body.category},
        )
        raise CaseCreationFailedError() from None
    db.refresh(case)
    return _detail(db, case), True


def list_cases(db: Session, principal: Principal, *, statuses: list[str] | None, limit: int) -> CasePage:
    query = select(SupportCase).where(SupportCase.created_by_user_id == principal.user_id)
    if statuses:
        query = query.where(SupportCase.status.in_(statuses))
    rows = db.scalars(query.order_by(SupportCase.updated_at.desc()).limit(limit)).all()
    return CasePage(
        items=[
            CaseSummary(
                case_id=c.id,
                case_number=c.case_number,
                category=c.category,
                status=c.status,
                escalation_reason=c.escalation_reason,
                summary_preview=c.summary[:140],
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in rows
        ]
    )


def get_case(db: Session, audit: AuditService, principal: Principal, case_id: UUID) -> CaseDetail:
    case = db.scalars(
        select(SupportCase).options(selectinload(SupportCase.events)).where(SupportCase.id == case_id)
    ).first()
    if case is None or case.created_by_user_id != principal.user_id:
        audit.record(
            "ACCESS_DENIED",
            AuditOutcome.DENIED,
            actor=principal,
            resource_type="support_case",
            resource_ref=str(case_id),
            reason_code="NOT_EXISTS" if case is None else "NOT_OWNER",
        )
        raise NotFoundError()
    return _detail(db, case)


def _detail(db: Session, case: SupportCase) -> CaseDetail:
    names = {
        u.id: u.display_name
        for u in db.scalars(select(User).where(User.id.in_({e.actor_user_id for e in case.events})))
    }
    claim_number = (
        db.scalar(select(Claim.claim_number).where(Claim.id == case.related_claim_id))
        if case.related_claim_id
        else None
    )
    return CaseDetail(
        case_id=case.id,
        case_number=case.case_number,
        category=case.category,
        status=case.status,
        escalation_reason=case.escalation_reason,
        summary=case.summary,
        related_session_id=case.related_session_id,
        related_claim_number=claim_number,
        resolution_note=case.resolution_note,
        version=case.version,
        events=[
            CaseEvent(
                event_type=e.event_type,
                from_status=e.from_status,
                to_status=e.to_status,
                note=e.note,
                actor_display_name=names.get(e.actor_user_id, "Unknown"),
                created_at=e.created_at,
            )
            for e in case.events
        ],
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
