import re
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app
from tests.conftest import MEMBER_A

pytestmark = pytest.mark.postgres

BACKEND = Path(__file__).resolve().parents[2]


def test_request_id_is_echoed_or_generated(client):
    rid = str(uuid4())
    assert client.get("/api/v1/health", headers={"X-Request-ID": rid}).headers["X-Request-ID"] == rid
    generated = client.get("/api/v1/health", headers={"X-Request-ID": "not-a-uuid"}).headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f-]{36}", generated)


def test_api_responses_are_not_cached(client, auth):
    response = client.get("/api/v1/auth/me", headers=auth(MEMBER_A))
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_sensitive_fields_never_serialized(client, auth):
    for path in ("/api/v1/auth/me", "/api/v1/claims", "/api/v1/claims/SYN-CLM-2026-000101",
                 "/api/v1/benefits/SYN-PLAN-GOLD-01"):
        text = client.get(path, headers=auth(MEMBER_A)).text
        for forbidden in ("password", "argon2", "billed_amount", "is_synthetic", "failed_login", "member_id"):
            assert forbidden not in text, (path, forbidden)


def test_production_app_hides_docs_and_openapi():
    settings = load_settings(app_env="production", jwt_secret="p" * 48, _env_file=None, embedding_provider="fastembed",
                             database_url="postgresql+psycopg://ihsa_app@db.example.test:5432/ihsa")
    prod_client = TestClient(create_app(settings), raise_server_exceptions=False)
    assert prod_client.get("/docs").status_code == 404
    assert prod_client.get("/api/v1/openapi.json").status_code == 404


def test_env_files_are_git_ignored_and_example_has_no_secret():  # AT-061 (lightweight; not a gitleaks run)
    gitignore = (BACKEND / ".gitignore").read_text().splitlines()
    assert ".env" in gitignore and "!.env.example" in gitignore
    example = dotenv_values(BACKEND / ".env.example")
    assert example["JWT_SECRET"].startswith("replace-with")
    assert not example.get("SEED_USER_PASSWORD")


def test_local_secrets_do_not_appear_in_source_files():
    local = dotenv_values(BACKEND / ".env") if (BACKEND / ".env").exists() else {}
    secrets = [v for k, v in local.items() if k in ("JWT_SECRET", "SEED_USER_PASSWORD") and v and len(v) >= 12]
    if not secrets:
        pytest.skip("no local .env secrets to check")
    for path in BACKEND.rglob("*"):
        if path.is_dir() or any(part in (".venv", ".local", "__pycache__", ".pytest_cache", ".ruff_cache")
                                for part in path.parts) or path.name == ".env":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for secret in secrets:
            assert secret not in content, f"secret value found in {path.relative_to(BACKEND)}"
