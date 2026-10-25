from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import Synthetic, Timestamps, UUIDPrimaryKey


class Plan(UUIDPrimaryKey, Synthetic, Timestamps, Base):
    """Plan-level information. `source_document_id` (doc 05 §2.4) is added in Phase 4 with knowledge_documents."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("plan_code ~ '^SYN-PLAN-[A-Z0-9-]{2,20}$'", name="plan_code_format"),
        CheckConstraint("plan_year BETWEEN 2000 AND 2100", name="plan_year_range"),
        CheckConstraint("effective_end IS NULL OR effective_end >= effective_start", name="effective_dates_ordered"),
    )

    plan_code: Mapped[str] = mapped_column(String(30), unique=True)
    plan_name: Mapped[str] = mapped_column(String(150))
    plan_year: Mapped[int]
    effective_start: Mapped[date]
    effective_end: Mapped[date | None]
    summary: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    benefits: Mapped[list["PlanBenefit"]] = relationship(
        back_populates="plan", order_by="(PlanBenefit.benefit_category, PlanBenefit.service_name)"
    )


class PlanBenefit(UUIDPrimaryKey, Timestamps, Base):
    """One benefit entry. `source_chunk_id` (doc 05 §2.5) is added in Phase 4 with document_chunks."""

    __tablename__ = "plan_benefits"
    __table_args__ = (
        UniqueConstraint("plan_id", "benefit_category", "service_name"),
        CheckConstraint("benefit_category ~ '^[A-Z][A-Z_]{1,59}$'", name="benefit_category_format"),
        Index(None, "plan_id"),
    )

    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    benefit_category: Mapped[str] = mapped_column(String(60))
    service_name: Mapped[str] = mapped_column(String(150))
    in_network_cost_share: Mapped[str | None] = mapped_column(String(100))
    out_of_network_cost_share: Mapped[str | None] = mapped_column(String(100))
    prior_auth_required: Mapped[bool] = mapped_column(server_default=text("false"))
    visit_limit: Mapped[str | None] = mapped_column(String(100))
    limitations: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[Plan] = relationship(back_populates="benefits")
