"""Application settings loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

# Value shipped in .env.example; refusing it in production prevents copy-paste deployments.
EXAMPLE_JWT_SECRET = "replace-with-a-long-random-string-of-at-least-32-chars"  # noqa: S105 - known-bad placeholder
MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "intelligent-healthcare-support-agent"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: SecretStr
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    db_required_at_startup: bool = True

    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_minutes: int = Field(default=30, ge=5, le=240)

    login_max_failures: int = Field(default=5, ge=1, le=50)
    login_failure_window_minutes: int = Field(default=15, ge=1, le=1440)

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("api_v1_prefix")
    @classmethod
    def _prefix_shape(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/' and not end with '/'")
        return value

    @field_validator("database_url")
    @classmethod
    def _valid_database_url(cls, value: SecretStr) -> SecretStr:
        # Error messages deliberately never echo the URL (it may contain a password).
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("DATABASE_URL could not be parsed") from None
        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use the 'postgresql+psycopg' driver")
        if not url.database:
            raise ValueError("DATABASE_URL must name a database")
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.app_env != "production":
            return self
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < MIN_PRODUCTION_SECRET_LENGTH or secret == EXAMPLE_JWT_SECRET:
            raise ValueError("JWT_SECRET must be a unique value of at least 32 characters in production")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS may not contain '*' in production")
        if self.log_level == "DEBUG":
            raise ValueError("LOG_LEVEL=DEBUG is not allowed in production")
        if self.sqlalchemy_url.host in (None, "127.0.0.1", "localhost") and self.sqlalchemy_url.username == "postgres":
            # The local trust-auth cluster (scripts/local_postgres.ps1) is development-only.
            raise ValueError("The development PostgreSQL superuser connection is not allowed in production")
        return self

    @property
    def sqlalchemy_url(self) -> URL:
        return make_url(self.database_url.get_secret_value())

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"


class ConfigurationError(RuntimeError):
    """Invalid or missing settings. The message names fields but never includes their values."""


def load_settings(**overrides: object) -> Settings:
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']).upper() or 'SETTINGS'}: {err['msg']}"
            for err in exc.errors(include_input=False, include_url=False)
        )
        raise ConfigurationError(f"Invalid configuration: {problems}") from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
