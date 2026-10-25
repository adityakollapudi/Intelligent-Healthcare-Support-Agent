import pytest

from app.core.config import EXAMPLE_JWT_SECRET, ConfigurationError, load_settings

GOOD_URL = "postgresql+psycopg://ihsa_app:s3cret-pw@db.internal.test:5432/ihsa"
STRONG_SECRET = "x" * 48


def _load(**overrides):
    values = {"database_url": GOOD_URL, "jwt_secret": STRONG_SECRET, "_env_file": None}
    values.update(overrides)
    return load_settings(**values)


def test_development_settings_load():
    settings = _load(app_env="development")
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.docs_enabled


def test_test_environment_settings_load():
    assert _load(app_env="test").app_env == "test"


def test_missing_database_url_is_reported_by_name(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_settings(jwt_secret=STRONG_SECRET, _env_file=None)


def test_missing_jwt_secret_is_reported(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="JWT_SECRET"):
        load_settings(database_url=GOOD_URL, _env_file=None)


@pytest.mark.parametrize("url", ["not a url at all", "mysql://u:p@h/db", "postgresql+psycopg://u:p@h"])
def test_invalid_database_url_rejected_without_echoing_it(url):
    with pytest.raises(ConfigurationError) as exc:
        _load(database_url=url)
    assert "DATABASE_URL" in str(exc.value)
    assert url not in str(exc.value)


def test_error_never_contains_password():
    with pytest.raises(ConfigurationError) as exc:
        _load(database_url="mysql://user:TopSecretPw@host/db")
    assert "TopSecretPw" not in str(exc.value)


@pytest.mark.parametrize("secret", [EXAMPLE_JWT_SECRET, "short-secret"])
def test_production_rejects_weak_or_example_secret(secret):
    with pytest.raises(ConfigurationError, match="JWT_SECRET"):
        _load(app_env="production", jwt_secret=secret)


def test_production_rejects_development_database_superuser():
    with pytest.raises(ConfigurationError, match="development PostgreSQL"):
        _load(app_env="production", database_url="postgresql+psycopg://postgres@127.0.0.1:55432/ihsa_dev")


def test_production_rejects_wildcard_cors_and_debug_logging():
    with pytest.raises(ConfigurationError, match="CORS"):
        _load(app_env="production", cors_origins="*")
    with pytest.raises(ConfigurationError, match="DEBUG"):
        _load(app_env="production", log_level="DEBUG")


def test_production_disables_interactive_docs():
    settings = _load(app_env="production")
    assert settings.docs_enabled is False


def test_cors_origins_parsed_from_comma_list():
    assert _load(cors_origins="http://a.test, http://b.test").cors_origins == ["http://a.test", "http://b.test"]


def test_secrets_are_masked_in_repr():
    text = repr(_load())
    assert "s3cret-pw" not in text and STRONG_SECRET not in text
