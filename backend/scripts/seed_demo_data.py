"""Seeds synthetic demonstration data. Run explicitly: `python -m scripts.seed_demo_data`.

Strategy: insert-if-absent by stable natural key, in one transaction. Existing rows are never
updated or deleted, so developer changes survive re-runs and nothing unrelated is touched.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Claim, Member, Organization, Plan, PlanBenefit, User
from scripts import seed_data

MIN_SEED_PASSWORD_LENGTH = 12


class SeedSummary:
    def __init__(self) -> None:
        self.inserted: Counter[str] = Counter()
        self.skipped: Counter[str] = Counter()

    def record(self, entity: str, inserted: bool) -> None:
        (self.inserted if inserted else self.skipped)[entity] += 1

    def lines(self) -> list[str]:
        entities = sorted(set(self.inserted) | set(self.skipped))
        return [f"{name}: inserted={self.inserted[name]} skipped={self.skipped[name]}" for name in entities]


def _get_or_add(session: Session, summary: SeedSummary, entity: str, model, lookup: dict, values: dict):
    existing = session.scalars(select(model).filter_by(**lookup)).first()
    summary.record(entity, existing is None)
    if existing is not None:
        return existing
    obj = model(**lookup, **values)
    session.add(obj)
    session.flush()
    return obj


def seed(session: Session, user_password: str) -> SeedSummary:
    if len(user_password) < MIN_SEED_PASSWORD_LENGTH:
        raise ValueError(f"SEED_USER_PASSWORD must be at least {MIN_SEED_PASSWORD_LENGTH} characters")
    summary = SeedSummary()

    orgs = {
        o["name"]: _get_or_add(session, summary, "organizations", Organization, {"name": o["name"]},
                               {"org_type": o["org_type"], "is_synthetic": True})
        for o in seed_data.ORGANIZATIONS
    }

    plans = {}
    for p in seed_data.PLANS:
        values = {k: v for k, v in p.items() if k != "plan_code"}
        plans[p["plan_code"]] = _get_or_add(session, summary, "plans", Plan, {"plan_code": p["plan_code"]},
                                            {**values, "is_synthetic": True})

    for plan_code, benefits in seed_data.PLAN_BENEFITS.items():
        for b in benefits:
            key = {"plan_id": plans[plan_code].id, "benefit_category": b["benefit_category"],
                   "service_name": b["service_name"]}
            values = {k: v for k, v in b.items() if k not in ("benefit_category", "service_name")}
            _get_or_add(session, summary, "plan_benefits", PlanBenefit, key, values)

    users = {}
    for u in seed_data.USERS:
        existing = session.scalars(select(User).filter_by(email=u["email"])).first()
        summary.record("users", existing is None)
        if existing is None:
            # Hash only when inserting; argon2 is deliberately slow.
            existing = User(email=u["email"], display_name=u["display_name"], role=u["role"],
                            organization_id=orgs[u["org"]].id if u["org"] else None,
                            password_hash=hash_password(user_password), is_synthetic=True)
            session.add(existing)
            session.flush()
        users[u["email"]] = existing

    members = {}
    for m in seed_data.MEMBERS:
        members[m["member_number"]] = _get_or_add(
            session, summary, "members", Member, {"member_number": m["member_number"]},
            {"user_id": users[m["email"]].id, "plan_id": plans[m["plan_code"]].id,
             "coverage_start": m["coverage_start"], "coverage_end": m["coverage_end"], "is_synthetic": True},
        )

    provider_org_id = orgs[seed_data.PROVIDER_ORG].id
    for c in seed_data.CLAIMS:
        member = members[c["member_number"]]
        values = {k: v for k, v in c.items() if k not in ("claim_number", "member_number")}
        values["billed_amount"] = Decimal(values["billed_amount"])
        _get_or_add(session, summary, "claims", Claim, {"claim_number": c["claim_number"]},
                    {**values, "member_id": member.id, "plan_id": member.plan_id,
                     "provider_organization_id": provider_org_id, "is_synthetic": True})
    return summary


def main() -> int:
    password = os.environ.get("SEED_USER_PASSWORD")
    if not password:
        # Fall back to the value pydantic-settings would read from .env.
        from dotenv import dotenv_values

        password = dotenv_values(".env").get("SEED_USER_PASSWORD")
    if not password:
        print("SEED_USER_PASSWORD is not set (environment or .env). Nothing was seeded.", file=sys.stderr)
        return 2

    from app.core.config import ConfigurationError, get_settings
    from app.db.session import get_session_factory

    try:
        get_settings()
    except ConfigurationError as exc:  # names the bad variables, never their values
        print(exc, file=sys.stderr)
        return 2

    with get_session_factory()() as session, session.begin():
        summary = seed(session, password)
    print("Synthetic seed complete (all records are fictional demonstration data):")
    for line in summary.lines():
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
