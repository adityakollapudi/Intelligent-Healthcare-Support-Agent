import pytest

from tests.conftest import ADMIN_A, MEMBER_A, PROVIDER_A, TEST_PASSWORD
from tests.helpers import assert_error, latest_audit

pytestmark = pytest.mark.postgres

PROTECTED = [("POST", "/api/v1/auth/logout"), ("GET", "/api/v1/auth/me"), ("GET", "/api/v1/claims"),
             ("GET", "/api/v1/claims/SYN-CLM-2026-000101"), ("GET", "/api/v1/benefits/SYN-PLAN-GOLD-01")]


def test_login_and_me(client):  # AT-001
    response = client.post("/api/v1/auth/login", json={"email": MEMBER_A.upper(), "password": TEST_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 1800
    assert body["user"]["role"] == "MEMBER"
    assert "password" not in response.text.lower()

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert me["role"] == "MEMBER"
    assert me["member"] == {"member_number": "SYN-M-000001", "plan_code": "SYN-PLAN-GOLD-01"}
    assert "claims:read:own" in me["permissions"]
    assert latest_audit("AUTH_LOGIN_SUCCEEDED").actor_role == "MEMBER"


def test_me_for_provider_includes_organization(client, auth):
    me = client.get("/api/v1/auth/me", headers=auth(PROVIDER_A)).json()
    assert me["member"] is None
    assert me["organization"]["name"] == "Maplestone Family Clinic (fictional)"


def test_wrong_password_and_unknown_email_look_identical(client):  # AT-002
    wrong = client.post("/api/v1/auth/login", json={"email": ADMIN_A, "password": "not-the-password"})
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.test", "password": "whatever-123"})
    e1 = assert_error(wrong, 401, "INVALID_CREDENTIALS")
    e2 = assert_error(unknown, 401, "INVALID_CREDENTIALS")
    assert e1["message"] == e2["message"]
    event = latest_audit("AUTH_LOGIN_FAILED")
    assert event.reason_code == "UNKNOWN_EMAIL" and "email_hash" in event.event_metadata
    assert "nobody" not in str(event.event_metadata)


def test_repeated_failures_are_rate_limited(client):  # AT-002 / NFR-020
    payload = {"email": "ratelimit.probe@example.test", "password": "wrong-password-1"}
    statuses = [client.post("/api/v1/auth/login", json=payload).status_code for _ in range(6)]
    assert statuses == [401] * 5 + [429]
    response = client.post("/api/v1/auth/login", json=payload)
    assert_error(response, 429, "RATE_LIMITED")
    assert int(response.headers["Retry-After"]) > 0


def test_login_rejects_unknown_fields(client):
    response = client.post("/api/v1/auth/login",
                           json={"email": MEMBER_A, "password": TEST_PASSWORD, "role": "ADMIN"})
    assert_error(response, 422, "FIELD_NOT_ALLOWED")


@pytest.mark.parametrize("body", [{}, {"email": "not-an-email", "password": "long-enough"},
                                  {"email": MEMBER_A, "password": "short"}])
def test_login_validation(client, body):
    error = assert_error(client.post("/api/v1/auth/login", json=body), 422, "VALIDATION_ERROR")
    assert "long-enough" not in str(error)  # submitted values are not echoed


@pytest.mark.parametrize(("method", "path"), PROTECTED)
@pytest.mark.parametrize("header", [None, "Bearer", "Bearer not.a.jwt", "Basic dXNlcjpwYXNz"])
def test_protected_routes_reject_missing_or_invalid_tokens(client, method, path, header):  # AT-003
    headers = {"Authorization": header} if header else {}
    assert_error(client.request(method, path, headers=headers), 401, "UNAUTHENTICATED")


def test_logout_revokes_the_token(client, token_for):
    token = token_for(MEMBER_A, fresh=True)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert_error(client.get("/api/v1/auth/me", headers=headers), 401, "UNAUTHENTICATED")
    token_for(MEMBER_A, fresh=True)  # refresh the shared cache for later tests
