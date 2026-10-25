"""Claim lookups (FR-014). Values come only from the database; access is ownership-scoped."""

from __future__ import annotations

import base64
import binascii
from datetime import date

from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.authz.permissions import Permission
from app.core.exceptions import AppError, NotFoundError
from app.models import Claim
from app.models.enums import AuditOutcome
from app.repositories import claim_repository
from app.schemas.claim import ClaimDetail, ClaimPage, ClaimSummary
from app.services.audit_service import AuditService


class InvalidCursorError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request contains invalid data."

    def __init__(self) -> None:
        super().__init__(details=[{"field": "cursor", "issue": "invalid"}])


def get_claim(db: Session, audit: AuditService, principal: Principal, claim_number: str) -> ClaimDetail:
    claim = None
    if principal.has(Permission.CLAIMS_READ_OWN) and principal.member_id is not None:
        claim = claim_repository.get_for_member(db, claim_number, principal.member_id)
    # Support agents hold claims:read:case_linked, but support cases (and therefore case links)
    # arrive in Phase 5/7, so no claim is reachable for them yet.

    if claim is None:
        if principal.has(Permission.CLAIMS_READ_OWN):
            reason = "NOT_OWNER" if claim_repository.exists_by_number(db, claim_number) else "NOT_EXISTS"
        else:
            reason = "NOT_ASSIGNED"
        audit.record("ACCESS_DENIED", AuditOutcome.DENIED, actor=principal, resource_type="claim",
                     resource_ref=claim_number, reason_code=reason)
        raise NotFoundError()

    audit.record("CLAIM_LOOKUP", AuditOutcome.SUCCESS, actor=principal, resource_type="claim",
                 resource_ref=claim_number)
    return ClaimDetail(member_number=claim.member.member_number, status_description=claim.status_description,
                       **_summary_fields(claim))


def list_claims(
    db: Session,
    audit: AuditService,
    principal: Principal,
    *,
    statuses: list[str] | None,
    limit: int,
    cursor: str | None,
) -> ClaimPage:
    if principal.member_id is None:
        claims: list[Claim] = []
    else:
        # Fetch one extra row to know whether another page exists.
        claims = claim_repository.list_for_member(
            db, principal.member_id, statuses=statuses, limit=limit + 1, after=_decode_cursor(cursor)
        )
    next_cursor = _encode_cursor(claims[limit - 1]) if len(claims) > limit else None
    items = [ClaimSummary(**_summary_fields(c)) for c in claims[:limit]]
    audit.record("CLAIM_LOOKUP", AuditOutcome.SUCCESS, actor=principal, resource_type="claim",
                 metadata={"result_count": len(items), "status_filter": statuses or []})
    return ClaimPage(items=items, next_cursor=next_cursor)


def _summary_fields(claim: Claim) -> dict:
    return {
        "claim_number": claim.claim_number,
        "plan_code": claim.plan.plan_code,
        "provider_name": claim.provider_organization.name if claim.provider_organization else None,
        "service_date": claim.service_date,
        "submission_date": claim.submission_date,
        "status": claim.status,
        "status_reason_code": claim.status_reason_code,
        "last_status_change_at": claim.last_status_change_at,
    }


def _encode_cursor(claim: Claim) -> str:
    raw = f"{claim.submission_date.isoformat()}|{claim.claim_number}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[date, str] | None:
    if cursor is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        day, number = raw.split("|", 1)
        return date.fromisoformat(day), number
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise InvalidCursorError() from None
