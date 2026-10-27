"""Answer feedback (FR-034, doc 06 §3.3). A user rates an ASSISTANT message in their own session;
one rating per message per user, updated on re-rating. The comment is stored for the record but is
never audited or shown in metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.core.exceptions import NotFoundError
from app.models import ConversationMessage, ConversationSession, UserFeedback
from app.models.enums import AuditOutcome
from app.schemas.chat import FeedbackRequest, FeedbackResponse
from app.services.audit_service import AuditService


def rate(db: Session, audit: AuditService, principal: Principal, message_id: UUID,
         body: FeedbackRequest) -> FeedbackResponse:
    message = db.get(ConversationMessage, message_id)
    session = db.get(ConversationSession, message.session_id) if message else None
    if message is None or message.sender != "ASSISTANT" or session is None or session.user_id != principal.user_id:
        audit.record("ACCESS_DENIED", AuditOutcome.DENIED, actor=principal, resource_type="conversation_message",
                     resource_ref=str(message_id), reason_code="NOT_EXISTS" if message is None else "NOT_OWNER")
        raise NotFoundError()
    now = datetime.now(UTC)
    row = db.scalars(select(UserFeedback).where(UserFeedback.message_id == message_id,
                                                UserFeedback.user_id == principal.user_id)).first()
    if row is None:
        row = UserFeedback(message_id=message_id, user_id=principal.user_id, rating=body.rating, comment=body.comment,
                           updated_at=now)
        db.add(row)
    else:
        row.rating, row.comment, row.updated_at = body.rating, body.comment, now
    db.flush()
    audit.add_to_transaction(db, "FEEDBACK_SUBMITTED", AuditOutcome.SUCCESS, actor=principal,
                             resource_type="conversation_message", resource_ref=str(message_id),
                             metadata={"rating": body.rating})
    db.commit()
    return FeedbackResponse(message_id=message_id, rating=row.rating, updated_at=row.updated_at)
