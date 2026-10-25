"""Strict input/output contracts for the four Phase 5 tools (doc 06 §5).

Inputs never contain identity: the executor injects the authenticated principal. Every model forbids
unknown fields, so a model-supplied `user_id`, `status`, `assignee`, SQL, URL, etc. is rejected."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.benefit import BenefitsResponse
from app.schemas.claim import ClaimSummary
from app.schemas.requirements import RequirementSetResponse
from app.schemas.support_case import CaseCategory, EscalationReason

BenefitCategory = Literal["PRIMARY_CARE", "SPECIALIST", "IMAGING", "PHYSICAL_THERAPY", "EMERGENCY", "PREVENTIVE"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- inputs -----------------------------------------------------------------------------------------


class GetClaimStatusInput(_Strict):
    claim_number: str | None = Field(
        default=None,
        pattern=r"^SYN-CLM-\d{4}-\d{6}$",
        description="Claim number such as SYN-CLM-2026-000101. Omit to list the caller's most recent claims.",
    )


class GetPlanBenefitsInput(_Strict):
    plan_code: str | None = Field(
        default=None,
        pattern=r"^SYN-PLAN-[A-Z0-9-]{2,20}$",
        description="Plan code such as SYN-PLAN-GOLD-01. Members may omit it to use their own plan.",
    )
    benefit_category: BenefitCategory | None = Field(default=None, description="Optional benefit category filter.")


class GetRequiredDocumentsInput(_Strict):
    procedure_code: str | None = Field(
        default=None,
        pattern=r"^SYN-PROC-[A-Z0-9-]{2,30}$",
        description="Configured procedure code, e.g. SYN-PROC-MRI-LUMBAR.",
    )
    procedure_text: str | None = Field(
        default=None,
        min_length=3,
        max_length=200,
        description="Procedure name as the user wrote it, e.g. 'lumbar MRI'.",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> GetRequiredDocumentsInput:
        if (self.procedure_code is None) == (self.procedure_text is None):
            raise ValueError("provide exactly one of procedure_code or procedure_text")
        return self


class CreateSupportCaseInput(_Strict):
    category: CaseCategory
    summary: str = Field(min_length=10, max_length=2000, description="Short description of the issue for an agent.")
    escalation_reason: EscalationReason = "USER_REQUESTED_HUMAN"


# --- outputs ----------------------------------------------------------------------------------------


class ClaimRecord(ClaimSummary):
    status_description: str | None = None


class GetClaimStatusOutput(_Strict):
    claims: list[ClaimRecord]


class GetPlanBenefitsOutput(BenefitsResponse):
    pass


class GetRequiredDocumentsOutput(RequirementSetResponse):
    pass


class SupportCaseProposal(_Strict):
    """What the user is asked to confirm. Nothing has been created when this is returned."""

    category: CaseCategory
    summary: str
    escalation_reason: EscalationReason
    related_session_id: UUID | None
    idempotency_key: UUID  # server-issued; reused by the confirm request so retries can't duplicate
    requires_confirmation: Literal[True] = True
