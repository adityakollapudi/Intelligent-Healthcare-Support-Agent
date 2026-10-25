from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import AuditLog, Member, RevokedToken, User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.strip().lower())).first()


def get_with_member(db: Session, user_id: UUID) -> tuple[User, Member | None] | None:
    user = db.get(User, user_id)
    if user is None:
        return None
    member = db.scalars(select(Member).options(joinedload(Member.plan)).where(Member.user_id == user_id)).first()
    return user, member


def is_token_revoked(db: Session, jti: UUID) -> bool:
    return db.get(RevokedToken, jti) is not None


def revoke_token(db: Session, jti: UUID, user_id: UUID, expires_at: datetime) -> None:
    if db.get(RevokedToken, jti) is None:
        db.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))


def recent_login_failures(db: Session, email_hash: str, since: datetime) -> tuple[int, datetime | None]:
    """Count and oldest timestamp of failed logins for an email fingerprint since `since`."""
    row = db.execute(
        select(func.count(), func.min(AuditLog.occurred_at)).where(
            AuditLog.action == "AUTH_LOGIN_FAILED",
            AuditLog.occurred_at >= since,
            AuditLog.event_metadata["email_hash"].astext == email_hash,
        )
    ).one()
    return int(row[0]), row[1]
