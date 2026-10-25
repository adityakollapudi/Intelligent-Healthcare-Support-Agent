import pytest

from app.db.session import get_db

pytestmark = pytest.mark.postgres


def test_health_ok_when_database_reachable(client):  # AT-058
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"api": "ok", "database": "ok"}
    assert body["time"].endswith("Z")


def test_health_is_public_and_minimal(client):
    body = client.get("/api/v1/health").json()
    assert set(body) == {"status", "checks", "time"}  # no version, host or configuration details


def test_health_degraded_when_database_unavailable(client, app, broken_db):
    app.dependency_overrides[get_db] = broken_db
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"] == {"api": "ok", "database": "unavailable"}
    assert "127.0.0.1" not in response.text and "nobody" not in response.text
