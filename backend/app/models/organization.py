from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import OrgType, sql_in
from app.models.mixins import CreatedAt, Synthetic, UUIDPrimaryKey


class Organization(UUIDPrimaryKey, Synthetic, CreatedAt, Base):
    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint(f"org_type IN ({sql_in(OrgType)})", name="org_type_valid"),)

    name: Mapped[str] = mapped_column(String(200), unique=True)
    org_type: Mapped[str] = mapped_column(String(30))
