from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Plan


def get_by_code(db: Session, plan_code: str) -> Plan | None:
    return db.scalars(select(Plan).options(selectinload(Plan.benefits)).where(Plan.plan_code == plan_code)).first()
