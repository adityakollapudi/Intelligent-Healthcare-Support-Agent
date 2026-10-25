"""The tool allowlist. Only tools listed in TOOLS can ever run; a model-supplied name is looked up in
this dict and nothing else (no getattr/eval/dynamic import).

To add a tool: define strict input/output models in definitions.py, write a handler that calls an
existing service with the injected principal, register a ToolSpec here with its permission, read/write
classification and confirmation policy, then add allowlist/authorization/failure tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel

from app.authz.permissions import Permission
from app.services import benefit_service, claim_service, requirements_service
from app.tools.definitions import (
    CreateSupportCaseInput,
    GetClaimStatusInput,
    GetClaimStatusOutput,
    GetPlanBenefitsInput,
    GetPlanBenefitsOutput,
    GetRequiredDocumentsInput,
    GetRequiredDocumentsOutput,
    SupportCaseProposal,
)

if TYPE_CHECKING:
    from app.tools.executor import ToolContext


class ToolInputError(Exception):
    """The arguments are valid JSON but unusable for this caller (e.g. a provider must name a plan)."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    any_of_permissions: tuple[Permission, ...]
    read_only: bool
    # "never": runs immediately. "user": returns a proposal; the write needs explicit user confirmation.
    confirmation: str
    handler: Callable[[ToolContext, Any], tuple[str, BaseModel]]
    redacted_args: tuple[str, ...]  # argument names safe to store in tool_invocations / audit


def _claim_status(ctx: ToolContext, args: GetClaimStatusInput):
    if args.claim_number:
        claim = claim_service.get_claim(ctx.db, ctx.audit, ctx.principal, args.claim_number)  # NotFound → 404
        record = claim.model_dump(exclude={"member_number", "data_environment"})
        return "SUCCEEDED", GetClaimStatusOutput(claims=[record])
    if not ctx.principal.has(Permission.CLAIMS_READ_OWN):
        raise ToolInputError("a claim number is required")
    page = claim_service.list_claims(ctx.db, ctx.audit, ctx.principal, statuses=None, limit=5, cursor=None)
    return "SUCCEEDED", GetClaimStatusOutput(claims=[c.model_dump() for c in page.items])


def _plan_benefits(ctx: ToolContext, args: GetPlanBenefitsInput):
    plan_code = args.plan_code or ctx.principal.plan_code
    if plan_code is None:
        raise ToolInputError("a plan code is required")
    result = benefit_service.get_benefits(ctx.db, ctx.audit, ctx.principal, plan_code, args.benefit_category)
    return "SUCCEEDED", GetPlanBenefitsOutput(**result.model_dump())


def _required_documents(ctx: ToolContext, args: GetRequiredDocumentsInput):
    result = requirements_service.get_requirements(
        ctx.db, ctx.audit, ctx.principal, procedure_code=args.procedure_code, procedure_text=args.procedure_text
    )
    return "SUCCEEDED", GetRequiredDocumentsOutput(**result.model_dump())


def _support_case(ctx: ToolContext, args: CreateSupportCaseInput):
    # Deliberately no write: the case is created only by the user's confirmed POST /support-cases.
    proposal = SupportCaseProposal(
        category=args.category,
        summary=args.summary,
        escalation_reason=args.escalation_reason,
        related_session_id=ctx.session_id,
        idempotency_key=uuid4(),
    )
    return "CONFIRMATION_REQUIRED", proposal


TOOLS: dict[str, ToolSpec] = {
    "get_claim_status": ToolSpec(
        name="get_claim_status",
        description="Look up the caller's own synthetic claim by claim number, or list their recent claims. "
        "Returns stored status and dates only.",
        input_model=GetClaimStatusInput,
        output_model=GetClaimStatusOutput,
        any_of_permissions=(Permission.CLAIMS_READ_OWN, Permission.CLAIMS_READ_CASE_LINKED),
        read_only=True,
        confirmation="never",
        handler=_claim_status,
        redacted_args=("claim_number",),
    ),
    "get_plan_benefits": ToolSpec(
        name="get_plan_benefits",
        description="Return stored plan-level benefit entries (cost sharing, visit limits, prior-authorization "
        "flags) for a synthetic plan. Members can only read their own plan.",
        input_model=GetPlanBenefitsInput,
        output_model=GetPlanBenefitsOutput,
        any_of_permissions=(Permission.BENEFITS_READ_OWN, Permission.BENEFITS_READ_ANY),
        read_only=True,
        confirmation="never",
        handler=_plan_benefits,
        redacted_args=("plan_code", "benefit_category"),
    ),
    "get_required_documents": ToolSpec(
        name="get_required_documents",
        description="Return the configured documentation requirements for a fictional procedure, each with the "
        "source passage that states it. Not an approval or coverage decision.",
        input_model=GetRequiredDocumentsInput,
        output_model=GetRequiredDocumentsOutput,
        any_of_permissions=(Permission.REQUIREMENTS_READ,),
        read_only=True,
        confirmation="never",
        handler=_required_documents,
        redacted_args=("procedure_code",),
    ),
    "create_support_case": ToolSpec(
        name="create_support_case",
        description="Prepare a support case for a human agent. It is NOT created until the user confirms it in "
        "the interface; never tell the user it was created.",
        input_model=CreateSupportCaseInput,
        output_model=SupportCaseProposal,
        any_of_permissions=(Permission.CASES_CREATE,),
        read_only=False,
        confirmation="user",
        handler=_support_case,
        redacted_args=("category", "escalation_reason"),
    ),
}


def anthropic_tool_definitions() -> list[dict[str, Any]]:
    """Tool definitions for the Messages API (strict JSON schemas generated from the input models)."""
    defs = []
    for spec in TOOLS.values():
        schema = spec.input_model.model_json_schema()
        schema["additionalProperties"] = False
        defs.append({"name": spec.name, "description": spec.description, "input_schema": schema})
    return defs
