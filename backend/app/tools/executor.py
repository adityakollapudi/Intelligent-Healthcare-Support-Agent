"""The only path by which a tool runs (doc 07 §4).

Order for every request: allowlist → call budget → argument validation → permission → handler
(existing services, which apply ownership and write their own lookup audit events) → output
validation → tool_invocations row + TOOL_INVOKED audit. The principal and session come from the
authenticated request, never from the model."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.core.exceptions import AppError, NotFoundError
from app.db.session import get_side_session_factory
from app.models import ToolInvocation
from app.models.enums import AuditOutcome
from app.services.audit_service import AuditService
from app.tools.registry import TOOLS, ToolInputError

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    db: Session
    audit: AuditService
    principal: Principal
    session_id: UUID | None
    message_id: UUID | None = None


@dataclass
class ToolResult:
    tool_name: str
    status: str  # doc 02 §3.8 values + CALL_LIMIT_REACHED
    data: dict[str, Any] | None = None  # validated output (only when SUCCEEDED / CONFIRMATION_REQUIRED)
    error: str | None = None  # safe, user-presentable reason for non-success
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        if self.status == "SUCCEEDED" and self.data is not None:
            if "readiness_status" in self.data:
                return f"{len(self.data['items'])} requirements checked for {self.data['procedure_code']}"
            if "documents" in self.data:
                return f"{len(self.data['documents'])} of your uploaded document(s) read"
            if "claims" in self.data:
                return f"{len(self.data['claims'])} claim record(s) retrieved"
            if "benefits" in self.data:
                return f"{len(self.data['benefits'])} benefit entr(ies) for {self.data['plan_code']}"
            if "requirements" in self.data:
                return f"{len(self.data['requirements'])} requirements for {self.data['procedure_code']}"
        if self.status == "CONFIRMATION_REQUIRED":
            return "Support case prepared; waiting for your confirmation"
        return self.error or self.status


class ToolExecutor:
    def __init__(self, ctx: ToolContext, *, max_calls: int, requested_by: str) -> None:
        self.ctx = ctx
        self.max_calls = max_calls
        self.requested_by = requested_by
        self.results: list[ToolResult] = []

    def execute(self, name: str, raw_args: Any) -> ToolResult:
        started = time.perf_counter()
        spec = TOOLS.get(name) if isinstance(name, str) else None
        safe_args: dict[str, Any] = {}
        if spec is None:
            result = ToolResult(str(name)[:60], "INVALID_ARGUMENTS", error="That operation isn't available.")
        elif len(self.results) >= self.max_calls:
            result = ToolResult(name, "CALL_LIMIT_REACHED", error="Too many operations were requested at once.")
        else:
            safe_args = (
                {k: v for k, v in (raw_args or {}).items() if k in spec.redacted_args}
                if isinstance(raw_args, dict)
                else {}
            )
            result = self._run(spec, raw_args)
        self.results.append(result)
        self._log(result, safe_args, int((time.perf_counter() - started) * 1000))
        return result

    def _run(self, spec, raw_args: Any) -> ToolResult:
        if raw_args is not None and not isinstance(raw_args, dict):  # never coerce a non-object to {}
            return ToolResult(spec.name, "INVALID_ARGUMENTS", error="Some details were missing or invalid.",
                              details={"fields": ["arguments"]})
        try:
            args = spec.input_model.model_validate(raw_args or {})
        except ValidationError as exc:
            fields = sorted({".".join(str(p) for p in e["loc"]) or "arguments" for e in exc.errors()})
            return ToolResult(
                spec.name,
                "INVALID_ARGUMENTS",
                error="Some details were missing or invalid.",
                details={"fields": fields},
            )
        principal = self.ctx.principal
        if not principal.permissions.intersection(spec.any_of_permissions):
            self.ctx.audit.record(
                "ACCESS_DENIED",
                AuditOutcome.DENIED,
                actor=principal,
                resource_type="tool",
                resource_ref=spec.name,
                reason_code="ROLE_NOT_PERMITTED",
                metadata={"tool_name": spec.name},
            )
            return ToolResult(spec.name, "PERMISSION_DENIED", error="Your account can't use this operation.")
        try:
            status, output = spec.handler(self.ctx, args)
            data = spec.output_model.model_validate(output.model_dump(mode="json")).model_dump(mode="json")
            return ToolResult(spec.name, status, data=data)
        except ToolInputError as exc:
            return ToolResult(spec.name, "INVALID_ARGUMENTS", error=str(exc).capitalize() + ".")
        except NotFoundError:
            return ToolResult(spec.name, "NOT_FOUND", error="No matching record is available to you.")
        except AppError as exc:  # e.g. ambiguous procedure, audit write failure
            if exc.code == "AMBIGUOUS_PROCEDURE":
                return ToolResult(
                    spec.name,
                    "INVALID_ARGUMENTS",
                    error=exc.message,
                    details={"candidates": getattr(exc, "candidates", [])},
                )
            logger.error("tool_app_error", extra={"tool_name": spec.name, "error_code": exc.code})
            return ToolResult(spec.name, "EXECUTION_ERROR", error="The operation failed. Please try again later.")
        except (SQLAlchemyError, ValidationError, Exception) as exc:  # noqa: BLE001 - never leak, never invent
            self.ctx.db.rollback()
            logger.error("tool_execution_error", extra={"tool_name": spec.name, "error_type": type(exc).__name__})
            return ToolResult(spec.name, "EXECUTION_ERROR", error="The operation failed. Please try again later.")

    def _log(self, result: ToolResult, safe_args: dict[str, Any], latency_ms: int) -> None:
        try:
            with get_side_session_factory()() as s, s.begin():
                s.add(
                    ToolInvocation(
                        message_id=self.ctx.message_id,
                        user_id=self.ctx.principal.user_id,
                        tool_name=result.tool_name,
                        requested_by=self.requested_by,
                        arguments_redacted=safe_args,
                        result_status=result.status,
                        latency_ms=latency_ms,
                    )
                )
        except SQLAlchemyError as exc:
            logger.error("tool_invocation_log_failed", extra={"error_type": type(exc).__name__})
        outcome = (
            AuditOutcome.SUCCESS
            if result.status in ("SUCCEEDED", "CONFIRMATION_REQUIRED")
            else (AuditOutcome.DENIED if result.status == "PERMISSION_DENIED" else AuditOutcome.FAILURE)
        )
        self.ctx.audit.record(
            "TOOL_INVOKED",
            outcome,
            actor=self.ctx.principal,
            resource_type="tool",
            resource_ref=result.tool_name,
            reason_code=None if outcome is AuditOutcome.SUCCESS else result.status,
            metadata={"tool_name": result.tool_name, "result_status": result.status, "requested_by": self.requested_by},
        )
