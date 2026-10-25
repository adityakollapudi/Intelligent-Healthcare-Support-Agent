from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.config import load_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    email_fingerprint,
    hash_password,
    verify_password,
)


@pytest.fixture
def settings():
    return load_settings(database_url="postgresql+psycopg://u@h/db_test", jwt_secret="k" * 40, _env_file=None)


def test_password_hash_is_argon2id_and_verifies():
    hashed = hash_password("correct horse battery")
    assert hashed.startswith("$argon2id$")
    assert "correct horse battery" not in hashed
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong password", hashed)


def test_verify_with_missing_or_corrupt_hash_is_false():
    assert verify_password("anything", None) is False
    assert verify_password("anything", "not-a-hash") is False


def test_token_round_trip(settings):
    user_id = uuid4()
    token = create_access_token(settings, user_id, "MEMBER")
    claims = decode_access_token(settings, token.token)
    assert claims is not None
    assert claims.user_id == user_id and claims.role == "MEMBER" and claims.jti == token.jti


def test_tampered_token_rejected(settings):
    token = create_access_token(settings, uuid4(), "MEMBER").token
    payload = jwt.decode(token, options={"verify_signature": False})
    payload["role"] = "ADMIN"
    forged = jwt.encode(payload, "attacker-key-that-is-long-enough-123456", algorithm="HS256")
    assert decode_access_token(settings, forged) is None


def test_expired_token_rejected(settings):
    past = datetime.now(UTC) - timedelta(hours=1)
    payload = {"sub": str(uuid4()), "role": "MEMBER", "jti": str(uuid4()), "iat": past, "exp": past}
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    assert decode_access_token(settings, token) is None


def test_none_algorithm_rejected(settings):
    payload = {"sub": str(uuid4()), "role": "ADMIN", "jti": str(uuid4()), "iat": 1, "exp": 4102444800}
    unsigned = jwt.encode(payload, None, algorithm="none")
    assert decode_access_token(settings, unsigned) is None


def test_email_fingerprint_is_stable_and_not_the_email(settings):
    fp = email_fingerprint(settings, "Priya.Member@example.test ")
    assert fp == email_fingerprint(settings, "priya.member@example.test")
    assert "priya" not in fp
