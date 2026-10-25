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


class UploadSizeLimitMiddleware:
    """Rejects oversized document uploads before the multipart body is read or spooled (TH-13).
    FastAPI parses form bodies before route dependencies run, so this can't live in the route.
    Uploads must declare Content-Length (browsers always do); the route re-checks the actual size."""

    MULTIPART_OVERHEAD = 64 * 1024

    def __init__(self, app, *, path: str, max_bytes: int) -> None:
        self.app, self.path, self.limit = app, path, max_bytes + self.MULTIPART_OVERHEAD

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == self.path:
            headers = dict(scope["headers"])
            length = headers.get(b"content-length")
            status, code, message = None, None, None
            if length is None or not length.isdigit():
                status, code, message = 411, "LENGTH_REQUIRED", "Uploads must include a Content-Length header."
            elif int(length) > self.limit:
                status, code, message = 413, "FILE_TOO_LARGE", "The file is larger than the upload limit."
            if status:
                # RequestContextMiddleware (outer) has set the request ID and adds the header.
                response = JSONResponse(status_code=status, content=error_body(code, message),
                                        headers={"Connection": "close"})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
