import pytest
from sqlalchemy import select

from app.db.session import get_db
from app.models import Claim
from app.repositories import claim_repository
from app.services.audit_service import AuditService, AuditWriteError, get_audit_service
from tests.conftest import ADMIN_A, AGENT_A, MEMBER_A, MEMBER_B, PROVIDER_A
from tests.helpers import assert_error, latest_audit

pytestmark = pytest.mark.postgres

OWN = "SYN-CLM-2026-000101"            # member A
OTHER = "SYN-CLM-2026-000201"          # member B
MISSING = "SYN-CLM-2026-999999"
DETAIL_FIELDS = {"claim_number", "member_number", "plan_code", "provider_name", "service_date", "submission_date",
                 "status", "status_reason_code", "status_description", "last_status_change_at", "data_environment"}


def test_own_claim_matches_database_exactly(client, auth, db_session):  # AT-019
    response = client.get(f"/api/v1/claims/{OWN}", headers=auth(MEMBER_A))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS  # no billed_amount, ids or internal columns
    row = db_session.scalars(select(Claim).where(Claim.claim_number == OWN)).one()
    assert body["status"] == row.status == "PENDING_INFORMATION"
    assert body["submission_date"] == row.submission_date.isoformat()
    assert body["last_status_change_at"] == "2026-09-02T10:15:00Z"
    assert body["member_number"] == "SYN-M-000001"
    assert body["data_environment"] == "SYNTHETIC_PROTOTYPE"
    assert latest_audit("CLAIM_LOOKUP", OWN).outcome == "SUCCESS"


def test_other_members_claim_is_indistinguishable_from_missing(client, auth):  # AT-005, AT-020
    other = assert_error(client.get(f"/api/v1/claims/{OTHER}", headers=auth(MEMBER_A)), 404, "RESOURCE_NOT_FOUND")
    assert latest_audit("ACCESS_DENIED", OTHER).reason_code == "NOT_OWNER"
    missing = assert_error(client.get(f"/api/v1/claims/{MISSING}", headers=auth(MEMBER_A)), 404, "RESOURCE_NOT_FOUND")
    assert latest_audit("ACCESS_DENIED", MISSING).reason_code == "NOT_EXISTS"
    assert other["message"] == missing["message"]


def test_client_supplied_identity_parameters_are_ignored(client, auth):
    response = client.get(f"/api/v1/claims/{OTHER}?member_id=SYN-M-000002&user_id=x", headers=auth(MEMBER_A))
    assert response.status_code == 404
    listing = client.get("/api/v1/claims?member_number=SYN-M-000002", headers=auth(MEMBER_A)).json()
    assert {c["claim_number"] for c in listing["items"]} == {f"SYN-CLM-2026-00010{i}" for i in range(1, 6)}


@pytest.mark.parametrize("bad", ["CLM-1001", "SYN-CLM-26-1", "syn-clm-2026-000101", "SYN-CLM-2026-000101x"])
def test_invalid_claim_number_format(client, auth, bad):
    assert_error(client.get(f"/api/v1/claims/{bad}", headers=auth(MEMBER_A)), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("email", [PROVIDER_A, ADMIN_A])
def test_roles_without_claim_permission_are_forbidden(client, auth, email):  # AT-006
    assert_error(client.get(f"/api/v1/claims/{OWN}", headers=auth(email)), 403, "FORBIDDEN")
    event = latest_audit("ACCESS_DENIED")
    assert event.reason_code == "ROLE_NOT_PERMITTED" and event.outcome == "DENIED"
    assert_error(client.get("/api/v1/claims", headers=auth(email)), 403, "FORBIDDEN")


def test_support_agent_cannot_reach_claims_without_an_assigned_case(client, auth):
    assert_error(client.get(f"/api/v1/claims/{OWN}", headers=auth(AGENT_A)), 404, "RESOURCE_NOT_FOUND")
    assert latest_audit("ACCESS_DENIED", OWN).reason_code == "NOT_ASSIGNED"


def test_list_returns_only_own_claims_newest_first(client, auth):
    body = client.get("/api/v1/claims", headers=auth(MEMBER_B)).json()
    numbers = [c["claim_number"] for c in body["items"]]
    assert numbers == ["SYN-CLM-2026-000203", "SYN-CLM-2026-000201", "SYN-CLM-2026-000202"]
    assert body["next_cursor"] is None


def test_list_pagination_and_status_filter(client, auth):
    first = client.get("/api/v1/claims?limit=2", headers=auth(MEMBER_A)).json()
    second = client.get(f"/api/v1/claims?limit=2&cursor={first['next_cursor']}", headers=auth(MEMBER_A)).json()
    third = client.get(f"/api/v1/claims?limit=2&cursor={second['next_cursor']}", headers=auth(MEMBER_A)).json()
    seen = [c["claim_number"] for page in (first, second, third) for c in page["items"]]
    assert len(seen) == len(set(seen)) == 5 and third["next_cursor"] is None

    paid = client.get("/api/v1/claims?status=PROCESSED_PAID", headers=auth(MEMBER_A)).json()
    assert [c["claim_number"] for c in paid["items"]] == ["SYN-CLM-2026-000104"]
    assert_error(client.get("/api/v1/claims?status=APPROVED", headers=auth(MEMBER_A)), 422, "VALIDATION_ERROR")
    assert_error(client.get("/api/v1/claims?cursor=bogus!!", headers=auth(MEMBER_A)), 422, "VALIDATION_ERROR")


def test_database_outage_returns_503_without_details(client, app, broken_db, auth):
    headers = auth(MEMBER_A)
    app.dependency_overrides[get_db] = broken_db
    error = assert_error(client.get(f"/api/v1/claims/{OWN}", headers=headers), 503, "SERVICE_UNAVAILABLE")
    assert "psycopg" not in str(error) and "127.0.0.1" not in str(error)


def test_unexpected_error_returns_safe_500(client, auth, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("internal detail: SELECT * FROM claims; password=hunter2")

    monkeypatch.setattr(claim_repository, "get_for_member", explode)
    response = client.get(f"/api/v1/claims/{OWN}", headers=auth(MEMBER_A))
    error = assert_error(response, 500, "INTERNAL_ERROR")
    assert "hunter2" not in response.text and "Traceback" not in response.text
    assert error["message"] == "An unexpected error occurred."


def test_lookup_fails_closed_when_audit_cannot_be_written(client, app, auth):
    class FailingAudit(AuditService):
        def record(self, *args, **kwargs):
            raise AuditWriteError()

    headers = auth(MEMBER_A)
    app.dependency_overrides[get_audit_service] = FailingAudit
    response = client.get(f"/api/v1/claims/{OWN}", headers=headers)
    assert_error(response, 500, "INTERNAL_ERROR")
    assert OWN not in response.text
