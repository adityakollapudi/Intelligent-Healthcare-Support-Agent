from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import Synthetic, Timestamps, UUIDPrimaryKey
from app.models.plan import Plan


class Member(UUIDPrimaryKey, Synthetic, Timestamps, Base):
    """Synthetic insured member. Deliberately holds no demographics (doc 09 §3)."""

    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint("member_number ~ '^SYN-M-[0-9]{6}$'", name="member_number_format"),
        CheckConstraint("coverage_end IS NULL OR coverage_end >= coverage_start", name="coverage_dates_ordered"),
        Index(None, "plan_id"),
    )

    member_number: Mapped[str] = mapped_column(String(20), unique=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    coverage_start: Mapped[date]
    coverage_end: Mapped[date | None]

    plan: Mapped[Plan] = relationship()
