"""Administrators create members, providers and support agents; nobody else can."""

from uuid import uuid4

import pytest

from tests.conftest import ADMIN_A, AGENT_A, MEMBER_A, PROVIDER_A
from tests.helpers import assert_error, latest_audit

pytestmark = pytest.mark.postgres
PASSWORD = "Synthetic-Pass-1!"
URL = "/api/v1/admin/users"


def _email(prefix="new") -> str:
    return f"{prefix}.{uuid4().hex[:10]}@example.test"


@pytest.fixture
def admin(client, auth):
    class Admin:
        def options(self):
            return client.get(f"{URL}/options", headers=auth(ADMIN_A)).json()

        def org(self, role):
            return next(o["id"] for o in self.options()["organizations"] if o["role"] == role)

        def create(self, **body):
            data = {"email": _email(), "display_name": "New Person", "password": PASSWORD, **body}
            return client.post(URL, json=data, headers=auth(ADMIN_A))

    return Admin()


def _login(client, email):
    return client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})


def test_a_new_member_gets_a_plan_and_can_sign_in(admin, client):
    email = _email("member")
    response = admin.create(email=email, role="MEMBER", plan_code="SYN-PLAN-GOLD-01")
    assert response.status_code == 201
    body = response.json()
    assert body["member_number"].startswith("SYN-M-") and body["plan_name"]
    assert "password" not in response.text.lower()

    token = _login(client, email).json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["member"]["plan_code"] == "SYN-PLAN-GOLD-01"
    assert latest_audit("USER_CREATED", body["id"]) is not None


@pytest.mark.parametrize("role", ["PROVIDER", "SUPPORT_AGENT"])
def test_providers_and_agents_join_a_matching_organization(admin, client, role):
    email = _email(role.lower())
    response = admin.create(email=email, role=role, organization_id=admin.org(role))
    assert response.status_code == 201 and response.json()["organization_name"]
    assert _login(client, email).json()["user"]["role"] == role


def test_many_members_get_their_own_numbers(admin):
    made = [admin.create(role="MEMBER", plan_code="SYN-PLAN-BRONZE-01").json() for _ in range(3)]
    assert len({m["member_number"] for m in made}) == 3


def test_new_users_appear_in_the_list_and_filter_by_role(admin, client, auth):
    email = _email("listed")
    admin.create(email=email, role="PROVIDER", organization_id=admin.org("PROVIDER"))
    rows = client.get(URL, params={"role": "PROVIDER"}, headers=auth(ADMIN_A)).json()
    assert email in {r["email"] for r in rows} and {r["role"] for r in rows} == {"PROVIDER"}


def test_a_used_email_is_refused(admin):
    response = admin.create(email=MEMBER_A, role="MEMBER", plan_code="SYN-PLAN-GOLD-01")
    assert_error(response, 409, "EMAIL_IN_USE")


def test_an_organization_of_the_wrong_type_is_refused(admin):
    response = admin.create(role="PROVIDER", organization_id=admin.org("SUPPORT_AGENT"))
    assert_error(response, 422, "INVALID_ACCOUNT_LINK")


def test_a_retired_plan_is_neither_offered_nor_accepted(admin):
    assert "SYN-PLAN-SILVER-25" not in {p["plan_code"] for p in admin.options()["plans"]}
    assert_error(admin.create(role="MEMBER", plan_code="SYN-PLAN-SILVER-25"), 422, "INVALID_ACCOUNT_LINK")


def test_an_unknown_plan_is_refused(admin):
    assert_error(admin.create(role="MEMBER", plan_code="SYN-PLAN-NONE"), 422, "INVALID_ACCOUNT_LINK")


@pytest.mark.parametrize("change", [
    {"email": "real.person@gmail.com"}, {"password": "too-short"}, {"role": "ADMIN"}, {"plan_code": None},
])
def test_invalid_requests_are_refused(admin, change):
    body = {"role": "MEMBER", "plan_code": "SYN-PLAN-GOLD-01", **change}
    assert_error(admin.create(**body), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("email", [MEMBER_A, PROVIDER_A, AGENT_A])
def test_only_administrators_can_manage_users(client, auth, email):
    assert client.get(URL, headers=auth(email)).status_code == 403
    assert client.get(f"{URL}/options", headers=auth(email)).status_code == 403
    body = {"email": _email(), "display_name": "Nope", "password": PASSWORD, "role": "MEMBER",
            "plan_code": "SYN-PLAN-GOLD-01"}
    assert client.post(URL, json=body, headers=auth(email)).status_code == 403
