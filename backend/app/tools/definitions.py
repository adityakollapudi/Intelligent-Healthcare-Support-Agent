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


class ReadMyDocumentsInput(_Strict):
    filename_contains: str | None = Field(
        default=None, max_length=120, description="Optional part of a file name, to read one uploaded document."
    )


class CheckDocumentReadinessInput(_Strict):
    procedure_code: str = Field(pattern=r"^SYN-PROC-[A-Z0-9-]{2,30}$", description="Configured procedure code.")
    document_ids: list[UUID] = Field(min_length=1, max_length=10, description="The caller's own uploaded documents.")


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


class DocumentPage(_Strict):
    page_number: int
    readable: bool
    text: str


class UploadedDocumentText(_Strict):
    document_id: UUID
    filename: str
    pages: list[DocumentPage]


class ReadMyDocumentsOutput(_Strict):
    """Untrusted file content held for this request only. It's never stored in tool_invocations."""

    documents: list[UploadedDocumentText]


class ReadinessPreviewItem(_Strict):
    requirement_code: str
    description: str
    status: Literal["SATISFIED", "MISSING", "UNREADABLE", "NEEDS_MANUAL_REVIEW"]
    found: str | None = None
    document_id: UUID | None = None
    filename: str | None = None
    page: int | None = None


class CheckDocumentReadinessOutput(_Strict):
    """A read-only preview for chat. Nothing is saved; the PA readiness screen creates checklists."""

    procedure_code: str
    display_name: str
    readiness_status: str
    items: list[ReadinessPreviewItem]
    document_names: list[str]
    warnings: list[str]
    disclaimer: str


class SupportCaseProposal(_Strict):
    """What the user is asked to confirm. Nothing has been created when this is returned."""

    category: CaseCategory
    summary: str
    escalation_reason: EscalationReason
    related_session_id: UUID | None
    idempotency_key: UUID  # server-issued; reused by the confirm request so retries can't duplicate
    requires_confirmation: Literal[True] = True
