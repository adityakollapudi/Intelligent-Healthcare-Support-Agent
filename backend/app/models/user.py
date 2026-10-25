from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AccountStatus, Role, sql_in
from app.models.mixins import Synthetic, Timestamps, UUIDPrimaryKey
from app.models.organization import Organization


class User(UUIDPrimaryKey, Synthetic, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN ({sql_in(Role)})", name="role_valid"),
        CheckConstraint(f"account_status IN ({sql_in(AccountStatus)})", name="account_status_valid"),
        # Emails are stored lower-cased so the plain unique index is case-insensitive.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(
            "(role IN ('PROVIDER', 'SUPPORT_AGENT') AND organization_id IS NOT NULL) "
            "OR role IN ('MEMBER', 'ADMIN')",
            name="org_required_for_staff",
        ),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_non_negative"),
        Index(None, "role"),
        Index(None, "organization_id"),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    account_status: Mapped[str] = mapped_column(String(20), server_default=text("'ACTIVE'"))
    failed_login_count: Mapped[int] = mapped_column(server_default=text("0"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization | None] = relationship(lazy="joined")
