"""Audit event recording (FR-031, doc 09 §5).

Events are written in their own short transaction so that a denial is recorded even though the
request itself fails. Audit is mandatory: if an event cannot be stored, the request fails with a
500 instead of returning data without a trace (fail closed).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import AppError
from app.core.request_context import current_request_id
from app.db.session import get_session_factory
from app.models import AuditLog
from app.models.enums import AuditOutcome

logger = logging.getLogger(__name__)

# Only these metadata keys may be stored; content fields (messages, documents, values) never are.
ALLOWED_METADATA_KEYS = frozenset({
    "email_hash", "route", "required_permissions", "result_count", "status_filter", "benefit_category",
})


class AuditActor(Protocol):
    user_id: UUID
    role: str


class AuditWriteError(AppError):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "An unexpected error occurred."


class AuditService:
    def record(
        self,
        action: str,
        outcome: AuditOutcome,
        *,
        actor: AuditActor | None = None,
        resource_type: str | None = None,
        resource_ref: str | None = None,
        reason_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = metadata or {}
        unknown = set(metadata) - ALLOWED_METADATA_KEYS
        if unknown:
            raise ValueError(f"audit metadata keys not allowlisted: {sorted(unknown)}")
        event = AuditLog(
            request_id=current_request_id(),
            actor_user_id=actor.user_id if actor else None,
            actor_role=actor.role if actor else None,
            action=action,
            resource_type=resource_type,
            resource_ref=resource_ref[:80] if resource_ref else None,
            outcome=outcome.value,
            reason_code=reason_code,
            event_metadata=metadata,
        )
        try:
            with get_session_factory()() as session, session.begin():
                session.add(event)
        except SQLAlchemyError as exc:
            logger.error("audit_write_failed", extra={"action": action, "error_type": type(exc).__name__})
            raise AuditWriteError() from None


def get_audit_service() -> AuditService:
    return AuditService()
