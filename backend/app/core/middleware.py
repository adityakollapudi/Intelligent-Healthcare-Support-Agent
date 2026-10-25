"""Request ID, request logging, cache headers and last-resort error handling."""

from __future__ import annotations

import logging
import time
from uuid import UUID, uuid4

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.exceptions import error_body
from app.core.request_context import request_id_var

logger = logging.getLogger("app.request")


def _incoming_request_id(request: Request) -> UUID:
    try:
        return UUID(request.headers.get("X-Request-ID", ""))
    except ValueError:
        return uuid4()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _incoming_request_id(request)
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # Handled here (not by ServerErrorMiddleware) so the body keeps the standard format
                # and request ID. The traceback goes to server logs only.
                logger.exception("unhandled_exception", extra={"error_type": type(exc).__name__})
                response = JSONResponse(status_code=500, content=error_body(
                    "INTERNAL_ERROR", "An unexpected error occurred."))
            response.headers["X-Request-ID"] = str(request_id)
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            route = request.scope.get("route")
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "route": getattr(route, "path", request.url.path),
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "user_id": str(getattr(request.state, "user_id", "") or "") or None,
                },
            )
            return response
        finally:
            request_id_var.reset(token)
