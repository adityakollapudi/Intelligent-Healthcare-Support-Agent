"""Application errors and the handlers that render the standard error format (doc 06 §4)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import current_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An expected failure with a stable error code and a safe, user-readable message."""

    status_code = 500
    code = "INTERNAL_ERROR"
    message = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or []
        self.headers = headers or {}


class UnauthenticatedError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"
    message = "Authentication is required."


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    message = "Email or password is incorrect."


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You don't have permission to do this."


class NotFoundError(AppError):
    """Used both for nonexistent and for not-permitted records, so the two are indistinguishable."""

    status_code = 404
    code = "RESOURCE_NOT_FOUND"
    message = "The requested item was not found."


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many attempts. Please try again later."

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(headers={"Retry-After": str(retry_after_seconds)})


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "The service is temporarily unavailable. Please try again shortly."


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    request_id = current_request_id()
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": str(request_id) if request_id else None,
        }
    }


def _response(status: int, code: str, message: str, details=None, headers=None) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(code, message, details), headers=headers)


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    details = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path", "header")]
        # Only the field path and the error type are returned; submitted values are not echoed.
        details.append({"field": ".".join(loc) or None, "issue": err.get("type", "invalid")})
    return details


_HTTP_CODES = {404: ("RESOURCE_NOT_FOUND", "The requested item was not found."),
               405: ("METHOD_NOT_ALLOWED", "This method is not allowed for this resource.")}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        extra = any(err.get("type") == "extra_forbidden" for err in exc.errors())
        code = "FIELD_NOT_ALLOWED" if extra else "VALIDATION_ERROR"
        return _response(422, code, "The request contains invalid data.", _validation_details(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(exc.status_code, ("HTTP_ERROR", "The request could not be completed."))
        return _response(exc.status_code, code, message, headers=getattr(exc, "headers", None))

    @app.exception_handler(OperationalError)
    async def _db_unavailable(_: Request, exc: OperationalError) -> JSONResponse:
        # str(exc) can include host names and SQL; log the type only, never return it.
        logger.error("database_unavailable", extra={"error_type": type(exc.orig).__name__})
        return _response(503, ServiceUnavailableError.code, ServiceUnavailableError.message)

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database_error", extra={"error_type": type(exc).__name__})
        return _response(500, AppError.code, AppError.message)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"error_type": type(exc).__name__})
        return _response(500, AppError.code, AppError.message)
