"""Per-request context (request ID, acting user) shared with logging and audit code."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

request_id_var: ContextVar[UUID | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[UUID | None] = ContextVar("user_id", default=None)


def current_request_id() -> UUID | None:
    return request_id_var.get()
