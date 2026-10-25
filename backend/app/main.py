"""FastAPI application factory. Run locally with: uvicorn app.main:app --reload"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import build_engine, ping

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("startup", extra={"app_env": settings.app_env, "version": settings.app_version})
        engine = build_engine(settings)
        try:
            with Session(engine) as session:
                ping(session)
        except SQLAlchemyError as exc:
            logger.error("database_unavailable_at_startup", extra={"error_type": type(exc).__name__})
            if settings.db_required_at_startup:
                raise RuntimeError(
                    "Database is unavailable. Check DATABASE_URL and that PostgreSQL is running."
                ) from None
        finally:
            engine.dispose()
        yield
        logger.info("shutdown")

    app = FastAPI(
        title="IHSA API",
        description="Intelligent Healthcare Support Agent — synthetic-data prototype (not an Evernorth product).",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if settings.docs_enabled else None,
    )
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)  # outermost: wraps CORS and routing
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


def __getattr__(name: str) -> FastAPI:
    # `app.main:app` is created lazily so importing this module (e.g. in tests) does not
    # require configuration.
    if name == "app":
        globals()["app"] = application = create_app()
        return application
    raise AttributeError(name)
