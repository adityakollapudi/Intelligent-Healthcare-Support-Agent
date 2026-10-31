"""Application settings loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
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
    # Separate pool for audit/tool-log writes made inside a request (see app.db.session, D8-07).
    db_side_pool_size: int = Field(default=5, ge=1, le=50)
    db_side_max_overflow: int = Field(default=10, ge=0, le=100)
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    db_required_at_startup: bool = True

    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_minutes: int = Field(default=30, ge=5, le=240)

    login_max_failures: int = Field(default=5, ge=1, le=50)
    login_failure_window_minutes: int = Field(default=15, ge=1, le=1440)

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # --- RAG / AI (Phase 4; doc 07, ADR-12) ---------------------------------------------------
    # "anthropic" calls Claude; "extractive" composes answers from retrieved sentences without an
    # LLM (explicit, labeled mode for environments without an approved model). Never auto-switched.
    llm_provider: Literal["anthropic", "extractive"] = "extractive"
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high"] = "low"
    llm_timeout_seconds: float = Field(default=30.0, ge=1, le=300)
    llm_max_retries: int = Field(default=1, ge=0, le=3)
    llm_max_output_tokens: int = Field(default=1500, ge=256, le=16000)
    anthropic_api_key: SecretStr | None = None

    # "fastembed" runs the model locally on CPU; "hash" is a deterministic test double (tests only).
    embedding_provider: Literal["fastembed", "hash"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = Field(default=384, ge=8, le=4096)
    embedding_cache_dir: str = ".local/models"

    rag_knowledge_dir: str = "data/knowledge"
    rag_chunk_words: int = Field(default=160, ge=40, le=1000)
    rag_chunk_overlap_words: int = Field(default=30, ge=0, le=300)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_min_relevance: float = Field(default=0.70, ge=0.0, le=1.0)  # calibrated for bge-small; see eval report
    rag_context_char_budget: int = Field(default=6000, ge=1000, le=50000)

    chat_max_message_chars: int = Field(default=4000, ge=100, le=8000)
    chat_history_messages: int = Field(default=6, ge=0, le=20)
    chat_rate_limit_per_minute: int = Field(default=20, ge=1, le=600)
    chat_session_retention_days: int = Field(default=30, ge=1, le=365)
    chat_max_documents_read: int = Field(default=10, ge=1, le=50)  # newest uploads read for one question
    tool_max_calls_per_message: int = Field(default=3, ge=1, le=10)

    # --- Documents and readiness (Phase 6; doc 07 §5.1, ADR-09) ---------------------------------
    # Private local volume (never served by the frontend). Keys are opaque `uploads/{uuid}`.
    document_storage_dir: str = ".local/uploads"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    max_pdf_pages: int = Field(default=20, ge=1, le=200)
    max_image_megapixels: float = Field(default=25.0, ge=0.1, le=100.0)
    job_timeout_seconds: int = Field(default=120, ge=5, le=900)
    max_concurrent_document_jobs: int = Field(default=1, ge=1, le=4)  # single in-process worker (TH-13)
    document_uploads_per_hour: int = Field(default=20,  # NFR-020
        ge=1, le=1000)
    document_analyses_per_hour: int = Field(default=30, ge=1, le=1000)
    # Provisional default (A-07 / NFR-021); no organizational retention policy was provided.
    document_retention_days: int = Field(default=30, ge=1, le=365)
    ocr_engine: Literal["tesseract", "disabled"] = "tesseract"
    ocr_tesseract_path: str = "tesseract"  # executable name on PATH or an absolute path
    ocr_languages: str = Field(default="eng", pattern=r"^[a-z]{3}(\+[a-z]{3})*$")
    ocr_dpi: int = Field(default=300, ge=72, le=400)
    ocr_page_timeout_seconds: float = Field(default=30.0, ge=1, le=300)
    ocr_min_text_chars_per_page: int = Field(default=50, ge=0, le=5000)
    ocr_min_word_confidence: float = Field(default=60.0, ge=0, le=100)  # provisional (doc 07 §5.2)
    extraction_low_confidence: float = Field(default=0.70, ge=0, le=1)  # provisional (doc 07 §5.4)

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
    def _ai_settings(self) -> Settings:
        if self.llm_provider == "anthropic" and not (
            self.anthropic_api_key and self.anthropic_api_key.get_secret_value().strip()
        ):
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        if self.rag_chunk_overlap_words >= self.rag_chunk_words:
            raise ValueError("RAG_CHUNK_OVERLAP_WORDS must be smaller than RAG_CHUNK_WORDS")
        if self.embedding_provider == "hash" and self.app_env != "test":
            raise ValueError("EMBEDDING_PROVIDER=hash is a test double and is only allowed when APP_ENV=test")
        parts = {p.lower() for p in Path(self.document_storage_dir).resolve().parts}
        if parts & {"public", "static", "dist", "frontend"}:
            raise ValueError("DOCUMENT_STORAGE_DIR must not be inside a publicly served directory")
        return self

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
