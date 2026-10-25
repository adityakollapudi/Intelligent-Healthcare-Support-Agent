"""Login, logout and profile (FR-001)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.core.config import Settings
from app.core.exceptions import InvalidCredentialsError, RateLimitedError
from app.core.security import create_access_token, email_fingerprint, verify_password
from app.models import User
from app.models.enums import AccountStatus, AuditOutcome
from app.repositories import user_repository
from app.schemas.auth import LoginResponse, MemberRef, MeResponse, OrganizationRef, UserSummary
from app.services.audit_service import AuditService


def login(db: Session, settings: Settings, audit: AuditService, email: str, password: str) -> LoginResponse:
    email_hash = email_fingerprint(settings, email)
    now = datetime.now(UTC)
    window = timedelta(minutes=settings.login_failure_window_minutes)

    failures, oldest = user_repository.recent_login_failures(db, email_hash, now - window)
    if failures >= settings.login_max_failures:
        retry_after = math.ceil(((oldest or now) + window - now).total_seconds())
        raise RateLimitedError(max(retry_after, 1))

    user = user_repository.get_by_email(db, email)
    password_ok = verify_password(password, user.password_hash if user else None)
    if user is None or not password_ok or user.account_status != AccountStatus.ACTIVE:
        if user is not None:
            user.failed_login_count += 1
            db.commit()
        # Same response for unknown email, wrong password and disabled account.
        reason = "UNKNOWN_EMAIL" if user is None else ("DISABLED" if password_ok else "BAD_PASSWORD")
        audit.record("AUTH_LOGIN_FAILED", AuditOutcome.FAILURE, actor=None if user is None else _actor(user),
                     resource_type="user", reason_code=reason, metadata={"email_hash": email_hash})
        raise InvalidCredentialsError()

    user.failed_login_count = 0
    user.last_login_at = now
    db.commit()
    token = create_access_token(settings, user.id, user.role)
    audit.record("AUTH_LOGIN_SUCCEEDED", AuditOutcome.SUCCESS, actor=_actor(user), resource_type="user",
                 resource_ref=str(user.id), metadata={"email_hash": email_hash})
    return LoginResponse(
        access_token=token.token,
        expires_in=settings.jwt_access_token_minutes * 60,
        user=UserSummary(id=user.id, display_name=user.display_name, role=user.role),
    )


def logout(db: Session, audit: AuditService, principal: Principal) -> None:
    user_repository.revoke_token(db, principal.token_jti, principal.user_id, principal.token_expires_at)
    db.commit()
    audit.record("AUTH_LOGOUT", AuditOutcome.SUCCESS, actor=principal, resource_type="user",
                 resource_ref=str(principal.user_id))


def me(principal: Principal) -> MeResponse:
    return MeResponse(
        id=principal.user_id,
        display_name=principal.display_name,
        email=principal.email,
        role=principal.role,
        organization=(OrganizationRef(id=principal.organization_id, name=principal.organization_name)
                      if principal.organization_id and principal.organization_name else None),
        member=(MemberRef(member_number=principal.member_number, plan_code=principal.plan_code)
                if principal.member_number and principal.plan_code else None),
        permissions=sorted(p.value for p in principal.permissions),
    )


@dataclass(frozen=True)
class _UserActor:
    """Minimal audit actor for events that happen before a Principal exists."""

    user_id: UUID
    role: str


def _actor(user: User) -> _UserActor:
    return _UserActor(user_id=user.id, role=user.role)
