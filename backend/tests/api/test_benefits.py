import pytest

from app.db.session import get_db
from scripts import seed_data
from tests.conftest import AGENT_A, MEMBER_A, PROVIDER_A
from tests.helpers import assert_error, latest_audit

pytestmark = pytest.mark.postgres

ITEM_FIELDS = {"benefit_category", "service_name", "in_network_cost_share", "out_of_network_cost_share",
               "prior_auth_required", "visit_limit", "limitations", "source"}


def test_member_reads_own_plan_from_database(client, auth):  # AT-021
    response = client.get("/api/v1/benefits/SYN-PLAN-GOLD-01", headers=auth(MEMBER_A))
    assert response.status_code == 200
    body = response.json()
    assert body["plan_name"] == "Synthetic Gold Plan" and body["data_environment"] == "SYNTHETIC_PROTOTYPE"
    assert len(body["benefits"]) == len(seed_data.PLAN_BENEFITS["SYN-PLAN-GOLD-01"])
    assert all(set(item) == ITEM_FIELDS for item in body["benefits"])
    pt = next(b for b in body["benefits"] if b["benefit_category"] == "PHYSICAL_THERAPY")
    assert pt["visit_limit"] == "20 visits per plan year" and pt["prior_auth_required"] is True
    assert pt["source"] is None  # knowledge-document sources arrive in Phase 4
    assert latest_audit("BENEFITS_LOOKUP", "SYN-PLAN-GOLD-01").outcome == "SUCCESS"


def test_member_cannot_read_another_plan(client, auth):  # AT-022
    assert_error(client.get("/api/v1/benefits/SYN-PLAN-BRONZE-01", headers=auth(MEMBER_A)), 404,
                 "RESOURCE_NOT_FOUND")
    assert latest_audit("ACCESS_DENIED", "SYN-PLAN-BRONZE-01").reason_code == "NOT_OWNER"


@pytest.mark.parametrize("email", [PROVIDER_A, AGENT_A])
def test_staff_can_read_any_active_plan(client, auth, email):
    assert client.get("/api/v1/benefits/SYN-PLAN-BRONZE-01", headers=auth(email)).status_code == 200


def test_inactive_and_unknown_plans_are_not_found(client, auth):
    assert_error(client.get("/api/v1/benefits/SYN-PLAN-SILVER-25", headers=auth(PROVIDER_A)), 404,
                 "RESOURCE_NOT_FOUND")
    assert_error(client.get("/api/v1/benefits/SYN-PLAN-NOPE-99", headers=auth(PROVIDER_A)), 404,
                 "RESOURCE_NOT_FOUND")


def test_category_filter(client, auth):
    body = client.get("/api/v1/benefits/SYN-PLAN-GOLD-01?benefit_category=IMAGING", headers=auth(MEMBER_A)).json()
    assert {b["service_name"] for b in body["benefits"]} == {"MRI (outpatient)", "X-ray"}


@pytest.mark.parametrize("path", ["/api/v1/benefits/GOLD", "/api/v1/benefits/SYN-PLAN-gold-01",
                                  "/api/v1/benefits/SYN-PLAN-GOLD-01?benefit_category=imaging;drop"])
def test_invalid_identifiers(client, auth, path):
    assert_error(client.get(path, headers=auth(MEMBER_A)), 422, "VALIDATION_ERROR")


def test_database_outage(client, app, auth, broken_db):
    headers = auth(PROVIDER_A)
    app.dependency_overrides[get_db] = broken_db
    assert_error(client.get("/api/v1/benefits/SYN-PLAN-GOLD-01", headers=headers), 503, "SERVICE_UNAVAILABLE")
