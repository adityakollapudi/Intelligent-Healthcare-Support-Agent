from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AuditOutcome, sql_in


class AuditLog(Base):
    """Append-only audit trail (doc 05 §2.24). Metadata keys are allowlisted by the audit service."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(f"outcome IN ({sql_in(AuditOutcome)})", name="outcome_valid"),
        Index(None, "occurred_at"),
        Index(None, "action", "occurred_at"),
        Index(None, "actor_user_id", "occurred_at"),
        Index(None, "outcome"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request_id: Mapped[UUID | None]
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_role: Mapped[str | None] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(60))
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_ref: Mapped[str | None] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(10))
    reason_code: Mapped[str | None] = mapped_column(String(50))
    # "metadata" is reserved on declarative classes, so the attribute name differs from the column.
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))


class RevokedToken(Base):
    """JWT deny-list for logout; rows are purgeable once expires_at has passed."""

    __tablename__ = "revoked_tokens"
    __table_args__ = (Index(None, "expires_at"),)

    jti: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
