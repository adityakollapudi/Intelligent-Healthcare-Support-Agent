from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ClaimStatus, sql_in
from app.models.member import Member
from app.models.mixins import Synthetic, Timestamps, UUIDPrimaryKey
from app.models.organization import Organization
from app.models.plan import Plan


class Claim(UUIDPrimaryKey, Synthetic, Timestamps, Base):
    """Synthetic claim. IHSA only reads claims; it never changes their status (doc 02 §3.9)."""

    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("claim_number ~ '^SYN-CLM-[0-9]{4}-[0-9]{6}$'", name="claim_number_format"),
        CheckConstraint(f"status IN ({sql_in(ClaimStatus)})", name="status_valid"),
        CheckConstraint("submission_date >= service_date", name="submission_after_service"),
        CheckConstraint("billed_amount IS NULL OR billed_amount >= 0", name="billed_amount_non_negative"),
        Index(None, "member_id", "submission_date"),
        Index(None, "status"),
        Index(None, "plan_id"),
        Index(None, "provider_organization_id"),
    )

    claim_number: Mapped[str] = mapped_column(String(25), unique=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id", ondelete="RESTRICT"))
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    provider_organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    service_date: Mapped[date]
    submission_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(30))
    status_reason_code: Mapped[str | None] = mapped_column(String(20))
    status_description: Mapped[str | None] = mapped_column(String(300))
    billed_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    last_status_change_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    member: Mapped[Member] = relationship()
    plan: Mapped[Plan] = relationship()
    provider_organization: Mapped[Organization | None] = relationship()
