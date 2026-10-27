"""Engine and per-request session management (synchronous SQLAlchemy, see ADR-01)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.db_connect_timeout_seconds},
    )


@lru_cache
def get_engine() -> Engine:
    return build_engine(get_settings())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@lru_cache
def get_side_session_factory() -> sessionmaker[Session]:
    """Short independent writes made *while a request session is open* (audit events, tool-call log).

    They need their own small pool: if they shared the request pool, N concurrent requests each holding
    one connection and waiting for a second would exhaust it and stall until the pool timeout (found by
    the Phase 8 load test at 10 concurrent users, D8-07). Side-channel connections are held only for a
    single INSERT and never wait on the request pool, so they can't deadlock with it."""
    settings = get_settings()
    engine = create_engine(
        settings.sqlalchemy_url,
        pool_size=settings.db_side_pool_size,
        max_overflow=settings.db_side_max_overflow,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.db_connect_timeout_seconds},
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request; anything uncommitted is rolled back."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping(session: Session) -> None:
    """Lightweight read-only readiness probe."""
    session.execute(text("SELECT 1"))
