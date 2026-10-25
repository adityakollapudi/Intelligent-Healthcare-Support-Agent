"""Deterministic documentation-readiness rules (doc 07 §6.3–6.4, doc 02 §3.4–3.5). Pure functions:
no database, no model. The result of every requirement is one of SATISFIED, MISSING, UNREADABLE or
NEEDS_MANUAL_REVIEW, with the evidence field IDs and a deterministic explanation.

Rule table (per field, collected across all checklist documents whose schema has that field):
  SATISFIED            ≥1 VALID value and all VALID values agree (FIELD_PATTERN: and match the regex)
  MISSING              every value ABSENT, or no document has the field
  UNREADABLE           no VALID value, ≥1 ILLEGIBLE / LOW_CONFIDENCE
  NEEDS_MANUAL_REVIEW  any INCONSISTENT / INVALID_FORMAT, VALID values disagree, or a regex mismatch
Precedence when signals mix: NEEDS_MANUAL_REVIEW > SATISFIED > UNREADABLE > MISSING.
Contradictions are never resolved automatically: both values are listed for the reviewer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

RULES_VERSION = "1.0"
SATISFIED, MISSING, UNREADABLE, MANUAL = "SATISFIED", "MISSING", "UNREADABLE", "NEEDS_MANUAL_REVIEW"
_UNREADABLE = {"ILLEGIBLE", "LOW_CONFIDENCE"}
_CONTRADICTION = {"INCONSISTENT", "INVALID_FORMAT"}


@dataclass(frozen=True)
class FieldEvidence:
    field_id: UUID
    document_id: UUID
    filename: str
    field_name: str
    validation_status: str
    normalized_value: str | None
    raw_value: str | None
    source_page: int | None


@dataclass(frozen=True)
class DocumentEvidence:
    document_id: UUID
    filename: str
    detected_type: str
    fields: dict[str, FieldEvidence]


@dataclass(frozen=True)
class Requirement:
    requirement_code: str
    rule_type: str
    rule_params: dict
    source_verified: bool = True


@dataclass
class ItemResult:
    item_status: str
    explanation: str
    evidence: list[FieldEvidence] = field(default_factory=list)

    @property
    def evidence_field_ids(self) -> list[UUID]:
        return [e.field_id for e in self.evidence]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _FieldParams(_Strict):
    field: str = Field(pattern=r"^[a-z_]{2,60}$")


class _PatternParams(_FieldParams):
    regex: str = Field(min_length=1, max_length=200)


class _DateParams(_FieldParams):
    reference_field: str = Field(pattern=r"^[a-z_]{2,60}$")
    max_days_before: int = Field(ge=0, le=3650)


class _DocTypeParams(_Strict):
    document_type: str = Field(pattern=r"^[A-Z_]{3,40}$")


_PARAMS = {"FIELD_PRESENT": _FieldParams, "FIELD_PATTERN": _PatternParams, "DATE_WITHIN_DAYS": _DateParams,
           "DOCUMENT_TYPE_PRESENT": _DocTypeParams, "MANUAL_ONLY": _Strict}


def _where(e: FieldEvidence) -> str:
    return f"{e.filename} p.{e.source_page}" if e.source_page else e.filename


@dataclass
class _Resolved:
    """One field across all documents."""

    status: str  # SATISFIED (one agreed VALID value) | MISSING | UNREADABLE | MANUAL
    value: str | None
    evidence: list[FieldEvidence]
    reason: str


def _resolve(name: str, docs: list[DocumentEvidence]) -> _Resolved:
    found = [d.fields[name] for d in docs if name in d.fields]
    if not found:
        return _Resolved(MISSING, None, [], f"No submitted document contains the field {name}")
    contradictory = [e for e in found if e.validation_status in _CONTRADICTION]
    valid = [e for e in found if e.validation_status == "VALID"]
    values = sorted({e.normalized_value for e in valid if e.normalized_value is not None})
    if contradictory:
        listed = "; ".join(f"{e.validation_status} '{(e.raw_value or '')[:60]}' in {_where(e)}" for e in contradictory)
        return _Resolved(MANUAL, None, contradictory + valid, f"{name}: {listed}")
    if len(values) > 1:
        listed = "; ".join(f"'{e.normalized_value}' in {_where(e)}" for e in valid)
        return _Resolved(MANUAL, None, valid, f"{name} values disagree across documents: {listed}")
    if valid:
        e = valid[0]
        return _Resolved(SATISFIED, values[0] if values else None, valid,
                         f"{name} = {e.normalized_value} (VALID) in {_where(e)}")
    unreadable = [e for e in found if e.validation_status in _UNREADABLE]
    if unreadable:
        listed = ", ".join(f"{e.validation_status} in {_where(e)}" for e in unreadable)
        return _Resolved(UNREADABLE, None, unreadable, f"{name} could not be read reliably ({listed})")
    return _Resolved(MISSING, None, [], f"Field {name} ABSENT in all submitted documents")


def evaluate(req: Requirement, docs: list[DocumentEvidence]) -> ItemResult:
    model = _PARAMS.get(req.rule_type)
    if model is None:
        return ItemResult(MANUAL, f"Unknown rule type {req.rule_type}: requires human verification")
    try:
        params = model.model_validate(req.rule_params)
    except ValidationError:
        return ItemResult(MANUAL, "Requirement rule configuration is invalid: requires human verification")
    result = _evaluate(req.rule_type, params, docs)
    if not req.source_verified and result.item_status != MANUAL:
        # Don't present a checklist outcome for a requirement whose source passage can't be shown.
        return ItemResult(MANUAL, "Requirement source passage could not be verified in the active source "
                                  f"document; automated result was {result.item_status}: {result.explanation}"[:500],
                          result.evidence)
    return result


def _evaluate(rule_type: str, params, docs: list[DocumentEvidence]) -> ItemResult:
    if rule_type == "MANUAL_ONLY":
        return ItemResult(MANUAL, "Rule type MANUAL_ONLY: requires human verification")

    if rule_type == "DOCUMENT_TYPE_PRESENT":
        matching = [d for d in docs if d.detected_type == params.document_type]
        if matching:
            return ItemResult(SATISFIED, f"{params.document_type} detected: {', '.join(d.filename for d in matching)}")
        unknown = [d for d in docs if d.detected_type == "UNRECOGNIZED"]
        if unknown:
            return ItemResult(MANUAL, f"No {params.document_type} detected, but {len(unknown)} document(s) could "
                                      f"not be classified: {', '.join(d.filename for d in unknown)}")
        return ItemResult(MISSING, f"No {params.document_type} among the submitted documents")

    if rule_type == "DATE_WITHIN_DAYS":
        a, b = _resolve(params.field, docs), _resolve(params.reference_field, docs)
        evidence = a.evidence + b.evidence
        if MANUAL in (a.status, b.status):
            return ItemResult(MANUAL, "; ".join(r.reason for r in (a, b) if r.status == MANUAL), evidence)
        if a.status == SATISFIED and b.status == SATISFIED:
            days = (date.fromisoformat(b.value) - date.fromisoformat(a.value)).days
            if 0 <= days <= params.max_days_before:
                return ItemResult(SATISFIED, f"{params.field} {a.value} is {days} day(s) before "
                                             f"{params.reference_field} {b.value} (limit {params.max_days_before})",
                                  evidence)
            return ItemResult(MANUAL, f"{params.field} {a.value} is {days} day(s) before {params.reference_field} "
                                      f"{b.value}; outside the {params.max_days_before}-day window", evidence)
        if UNREADABLE in (a.status, b.status):
            return ItemResult(UNREADABLE, "; ".join(r.reason for r in (a, b) if r.status == UNREADABLE), evidence)
        return ItemResult(MISSING, "; ".join(r.reason for r in (a, b) if r.status == MISSING), evidence)

    resolved = _resolve(params.field, docs)
    if rule_type == "FIELD_PATTERN" and resolved.status == SATISFIED:
        try:
            matches = re.fullmatch(params.regex, resolved.value or "") is not None
        except re.error:
            return ItemResult(MANUAL, "Requirement pattern is invalid: requires human verification", resolved.evidence)
        if not matches:
            return ItemResult(MANUAL, f"{params.field} '{resolved.value}' is present but doesn't match the required "
                                      "format", resolved.evidence)
    return ItemResult(resolved.status, resolved.reason[:500], resolved.evidence)


def overall(statuses: list[str]) -> str:
    """doc 02 §3.5."""
    if any(s in (MISSING, UNREADABLE) for s in statuses):
        return "DOCUMENTATION_INCOMPLETE"
    if any(s == MANUAL for s in statuses):
        return "MANUAL_REVIEW_REQUIRED"
    return "DOCUMENTATION_APPEARS_COMPLETE"
