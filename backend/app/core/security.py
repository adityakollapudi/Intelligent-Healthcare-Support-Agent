"""Password hashing (argon2id) and JWT access tokens (doc 03 §4.1)."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

_hasher = PasswordHasher()  # argon2id with the library's recommended parameters

# Verifying against this when an email is unknown keeps response timing similar to a real check.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalization")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


@dataclass(frozen=True)
class AccessToken:
    token: str
    jti: UUID
    expires_at: datetime


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    role: str
    jti: UUID
    expires_at: datetime


def create_access_token(settings: Settings, user_id: UUID, role: str) -> AccessToken:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_minutes)
    jti = uuid4()
    payload = {"sub": str(user_id), "role": role, "jti": str(jti), "iat": now, "exp": expires_at}
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)
    return AccessToken(token=token, jti=jti, expires_at=expires_at)


def decode_access_token(settings: Settings, token: str) -> TokenClaims | None:
    """Returns None for any invalid, tampered or expired token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "jti", "exp", "iat"]},
        )
        return TokenClaims(
            user_id=UUID(payload["sub"]),
            role=str(payload["role"]),
            jti=UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def email_fingerprint(settings: Settings, email: str) -> str:
    """Keyed hash used in audit metadata instead of the raw email address."""
    key = settings.jwt_secret.get_secret_value().encode()
    return hmac.new(key, email.strip().lower().encode(), hashlib.sha256).hexdigest()[:32]
