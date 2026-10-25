import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

import app.models  # noqa: F401
from app.db.base import Base
from tests.conftest import TEST_DATABASE_URL, run_migrations

pytestmark = pytest.mark.postgres

EXPECTED_TABLES = {"organizations", "users", "members", "plans", "plan_benefits", "claims", "audit_logs",
                   "revoked_tokens", "alembic_version"}


def test_fresh_migration_creates_expected_tables(database, db_session):
    tables = set(inspect(db_session.get_bind()).get_table_names())
    assert tables == EXPECTED_TABLES
    assert db_session.scalar(text("SELECT version_num FROM alembic_version")) == "0001"


def test_models_and_migrated_schema_do_not_drift(database, db_session):
    with db_session.get_bind().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def test_expected_constraints_and_indexes_exist(database, db_session):
    insp = inspect(db_session.get_bind())
    claim_checks = {c["name"] for c in insp.get_check_constraints("claims")}
    expected = {"ck_claims_status_valid", "ck_claims_submission_after_service", "ck_claims_claim_number_format"}
    assert expected <= claim_checks
    assert {u["name"] for u in insp.get_unique_constraints("claims")} == {"uq_claims_claim_number"}
    fks = {(fk["referred_table"], tuple(fk["constrained_columns"])) for fk in insp.get_foreign_keys("claims")}
    assert ("members", ("member_id",)) in fks and ("plans", ("plan_id",)) in fks
    assert "ix_claims_member_id_submission_date" in {i["name"] for i in insp.get_indexes("claims")}


@pytest.fixture
def scratch_database_url():
    """A throwaway database for the downgrade/upgrade round trip (needs CREATEDB privilege)."""
    base = make_url(TEST_DATABASE_URL)
    name = f"{base.database}_migrations"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # noqa: BLE001
        admin.dispose()
        pytest.skip(f"cannot create scratch database: {type(exc).__name__}")
    yield base.set(database=name).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def test_migrations_are_reversible(scratch_database_url):
    run_migrations(scratch_database_url)
    run_migrations(scratch_database_url, "base", downgrade=True)
    engine = create_engine(scratch_database_url)
    with engine.connect() as conn:
        remaining = set(inspect(conn).get_table_names()) - {"alembic_version"}
        functions = conn.scalar(text("SELECT count(*) FROM pg_proc WHERE proname = 'audit_logs_append_only'"))
    assert remaining == set() and functions == 0
    run_migrations(scratch_database_url)
    with engine.connect() as conn:
        assert set(inspect(conn).get_table_names()) == EXPECTED_TABLES
    engine.dispose()
