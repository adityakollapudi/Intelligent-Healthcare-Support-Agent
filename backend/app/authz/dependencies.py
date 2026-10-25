"""Authentication and authorization dependencies (doc 03 §4).

Identity always comes from a verified bearer token and a fresh database read of the user;
nothing the client sends in a path, query or body is treated as proof of identity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.authz.permissions import Permission, permissions_for
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthenticatedError
from app.core.request_context import user_id_var
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import AccountStatus, AuditOutcome
from app.repositories import user_repository
from app.services.audit_service import AuditService, get_audit_service


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    role: str
    email: str
    display_name: str
    organization_id: UUID | None
    organization_name: str | None
    member_id: UUID | None
    member_number: str | None
    plan_id: UUID | None
    plan_code: str | None
    token_jti: UUID
    token_expires_at: datetime

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.role)

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_principal(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    token = _bearer_token(request)
    claims = decode_access_token(settings, token) if token else None
    if claims is None or user_repository.is_token_revoked(db, claims.jti):
        raise UnauthenticatedError()
    loaded = user_repository.get_with_member(db, claims.user_id)
    if loaded is None:
        raise UnauthenticatedError()
    user, member = loaded
    if user.account_status != AccountStatus.ACTIVE:
        raise UnauthenticatedError()
    principal = Principal(
        user_id=user.id,
        role=user.role,  # the database role wins over the token claim
        email=user.email,
        display_name=user.display_name,
        organization_id=user.organization_id,
        organization_name=user.organization.name if user.organization else None,
        member_id=member.id if member else None,
        member_number=member.member_number if member else None,
        plan_id=member.plan_id if member else None,
        plan_code=member.plan.plan_code if member else None,
        token_jti=claims.jti,
        token_expires_at=claims.expires_at,
    )
    user_id_var.set(user.id)
    request.state.user_id = user.id
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_any_permission(*required: Permission) -> Callable[..., Principal]:
    """Dependency factory: the caller's role must hold at least one of `required`."""

    def dependency(
        request: Request,
        principal: CurrentPrincipal,
        audit: Annotated[AuditService, Depends(get_audit_service)],
    ) -> Principal:
        if not principal.permissions.intersection(required):
            audit.record(
                "ACCESS_DENIED",
                AuditOutcome.DENIED,
                actor=principal,
                reason_code="ROLE_NOT_PERMITTED",
                metadata={"route": request.url.path, "required_permissions": sorted(required)},
            )
            raise ForbiddenError()
        return principal

    dependency.required_permissions = frozenset(required)  # type: ignore[attr-defined]  # route inventory test
    return dependency
