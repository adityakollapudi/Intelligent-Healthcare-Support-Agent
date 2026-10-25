"""Database invariants hold regardless of which code path writes (each test rolls back)."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import AuditLog, Claim, Member, Organization, Plan, User

pytestmark = pytest.mark.postgres


@pytest.fixture
def tx(database):
    from app.db.session import get_engine

    connection = get_engine().connect()
    transaction = connection.begin()
    from sqlalchemy.orm import Session

    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def _member(session) -> Member:
    return session.scalars(select(Member).where(Member.member_number == "SYN-M-000001")).one()


def _claim(member: Member, **overrides) -> Claim:
    values = dict(claim_number="SYN-CLM-2026-000901", member_id=member.id, plan_id=member.plan_id,
                  service_date=date(2026, 1, 2), submission_date=date(2026, 1, 3), status="RECEIVED",
                  last_status_change_at=datetime(2026, 1, 3, tzinfo=UTC))
    values.update(overrides)
    return Claim(**values)


def _expect_violation(session, obj, error=IntegrityError):
    session.add(obj)
    with pytest.raises(error):
        session.flush()
    session.rollback()


def test_duplicate_claim_number_rejected(tx):
    _expect_violation(tx, _claim(_member(tx), claim_number="SYN-CLM-2026-000101"))


def test_claim_with_unknown_member_rejected(tx):
    member = _member(tx)
    _expect_violation(tx, _claim(member, member_id=uuid4()))


@pytest.mark.parametrize("overrides", [
    {"status": "APPROVED"},                                  # not in the documented status set
    {"claim_number": "CLM-1001"},                            # wrong public format
    {"service_date": date(2026, 2, 1), "submission_date": date(2026, 1, 1)},  # submitted before service
    {"billed_amount": -5},
])
def test_claim_check_constraints(tx, overrides):
    _expect_violation(tx, _claim(_member(tx), **overrides))


def test_duplicate_plan_code_rejected(tx):
    _expect_violation(tx, Plan(plan_code="SYN-PLAN-GOLD-01", plan_name="Dup", plan_year=2026,
                               effective_start=date(2026, 1, 1)))


def test_email_must_be_lowercase_and_unique(tx):
    _expect_violation(tx, User(email="Mixed@Example.test", display_name="X", role="MEMBER"))
    _expect_violation(tx, User(email="priya.member@example.test", display_name="X", role="MEMBER"))


def test_staff_roles_require_an_organization(tx):
    _expect_violation(tx, User(email="noorg.provider@example.test", display_name="X", role="PROVIDER"))


def test_invalid_role_rejected(tx):
    _expect_violation(tx, User(email="root@example.test", display_name="X", role="ROOT"))


def test_invalid_org_type_rejected(tx):
    _expect_violation(tx, Organization(name="Bad org", org_type="PAYER"))


def test_audit_logs_are_append_only(tx):
    tx.add(AuditLog(action="TEST_EVENT", outcome="SUCCESS"))
    tx.flush()
    with pytest.raises(DBAPIError, match="append-only"):
        tx.execute(text("UPDATE audit_logs SET action = 'TAMPERED' WHERE action = 'TEST_EVENT'"))
    tx.rollback()
    tx.add(AuditLog(action="TEST_EVENT", outcome="SUCCESS"))
    tx.flush()
    with pytest.raises(DBAPIError, match="append-only"):
        tx.execute(text("DELETE FROM audit_logs WHERE action = 'TEST_EVENT'"))
    tx.rollback()


def test_audit_purge_requires_explicit_opt_in(tx):
    tx.add(AuditLog(action="TEST_PURGE", outcome="SUCCESS"))
    tx.flush()
    tx.execute(text("SET LOCAL ihsa.allow_audit_purge = 'on'"))
    deleted = tx.execute(text("DELETE FROM audit_logs WHERE action = 'TEST_PURGE'")).rowcount
    assert deleted == 1


def test_get_db_rolls_back_and_closes_on_error(database):
    from app.db.session import get_db

    generator = get_db()
    session = next(generator)
    session.execute(text("SELECT 1"))
    assert session.in_transaction()
    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("boom"))
    assert not session.in_transaction()
