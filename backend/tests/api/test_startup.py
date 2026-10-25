import pytest
from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app
from tests.conftest import TEST_DATABASE_URL, TEST_JWT_SECRET

UNREACHABLE = "postgresql+psycopg://nobody@127.0.0.1:1/ihsa_test"


def _settings(url: str, required: bool):
    return load_settings(database_url=url, jwt_secret=TEST_JWT_SECRET, db_required_at_startup=required,
                         db_connect_timeout_seconds=1, _env_file=None)


def test_startup_fails_clearly_when_required_database_is_unreachable():
    app = create_app(_settings(UNREACHABLE, required=True))
    with pytest.raises(RuntimeError, match="Database is unavailable") as exc:
        with TestClient(app):
            pass
    assert "nobody" not in str(exc.value)  # the connection string is not echoed


def test_startup_continues_in_degraded_mode_when_database_is_optional():
    with TestClient(create_app(_settings(UNREACHABLE, required=False))):
        pass


@pytest.mark.postgres
def test_startup_succeeds_with_reachable_database(database):
    with TestClient(create_app(_settings(TEST_DATABASE_URL, required=True))) as client:
        assert client.get("/api/v1/health").status_code == 200
