"""Claim queries. Every user-facing query requires the caller's member_id (ownership predicate)."""

from datetime import date
from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Claim

_DETAIL_OPTIONS = (joinedload(Claim.member), joinedload(Claim.plan), joinedload(Claim.provider_organization))


def get_for_member(db: Session, claim_number: str, member_id: UUID) -> Claim | None:
    return db.scalars(
        select(Claim).options(*_DETAIL_OPTIONS).where(Claim.claim_number == claim_number, Claim.member_id == member_id)
    ).first()


def exists_by_number(db: Session, claim_number: str) -> bool:
    """Used only to choose the audit reason code; the caller never learns the answer."""
    return bool(db.scalar(select(exists().where(Claim.claim_number == claim_number))))


def list_for_member(
    db: Session,
    member_id: UUID,
    *,
    statuses: list[str] | None,
    limit: int,
    after: tuple[date, str] | None,
) -> list[Claim]:
    """Newest submission first; keyset pagination on (submission_date, claim_number)."""
    query = select(Claim).options(*_DETAIL_OPTIONS).where(Claim.member_id == member_id)
    if statuses:
        query = query.where(Claim.status.in_(statuses))
    if after is not None:
        after_date, after_number = after
        query = query.where(
            or_(Claim.submission_date < after_date,
                and_(Claim.submission_date == after_date, Claim.claim_number < after_number))
        )
    query = query.order_by(Claim.submission_date.desc(), Claim.claim_number.desc()).limit(limit)
    return list(db.scalars(query))
