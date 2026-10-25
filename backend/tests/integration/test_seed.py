import pytest
from sqlalchemy import func, select

from app.models import Claim, Member, Organization, Plan, PlanBenefit, User
from app.models.enums import ClaimStatus
from scripts import seed_data
from scripts.seed_demo_data import seed
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.postgres

MODELS = (Organization, Plan, PlanBenefit, User, Member, Claim)


def _counts(session):
    return {model.__tablename__: session.scalar(select(func.count()).select_from(model)) for model in MODELS}


def test_seed_is_repeatable_without_duplicates(db_session):
    before = _counts(db_session)
    summary = seed(db_session, TEST_PASSWORD)
    db_session.commit()
    assert sum(summary.inserted.values()) == 0
    assert _counts(db_session) == before


def test_seed_counts_match_the_seed_definition(db_session):
    counts = _counts(db_session)
    assert counts["claims"] == len(seed_data.CLAIMS)
    assert counts["plans"] == len(seed_data.PLANS) >= 2
    assert counts["users"] == len(seed_data.USERS)


def test_all_seed_records_are_marked_synthetic(db_session):
    for model in (Organization, Plan, User, Member, Claim):
        assert db_session.scalar(select(func.count()).select_from(model).where(model.is_synthetic.is_(False))) == 0


def test_seed_users_use_reserved_test_domain(db_session):
    emails = db_session.scalars(select(User.email)).all()
    assert emails and all(e.endswith("@example.test") for e in emails)


def test_claims_cover_every_status_and_are_consistent(db_session):
    claims = db_session.scalars(select(Claim)).all()
    assert {c.status for c in claims} == set(ClaimStatus)
    for c in claims:
        assert c.service_date <= c.submission_date <= c.last_status_change_at.date()
        member = db_session.get(Member, c.member_id)
        assert c.plan_id == member.plan_id


def test_negative_test_claim_number_is_absent(db_session):
    assert db_session.scalar(select(Claim).where(Claim.claim_number == seed_data.NONEXISTENT_CLAIM_NUMBER)) is None


def test_short_seed_password_refused(db_session):
    with pytest.raises(ValueError, match="at least"):
        seed(db_session, "short")
