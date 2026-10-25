"""Central escalation policy (doc 02 §3.7, Workflow E). Every place that can offer human help asks
this module which category/reason applies; nothing creates a case on its own. Policy for every
condition: the case is only *offered*; it is created by the user's confirmed POST /support-cases.

| Condition               | Escalation reason        | Category              | Answer still given?          |
|-------------------------|--------------------------|-----------------------|------------------------------|
| NO_ADEQUATE_ANSWER      | NO_ADEQUATE_ANSWER       | KNOWLEDGE_GAP         | Insufficient-evidence reply  |
| CONFLICTING_INFORMATION | CONFLICTING_INFORMATION  | KNOWLEDGE_GAP         | Both sources shown           |
| TOOL_FAILURE            | TOOL_FAILURE             | TECHNICAL_ISSUE       | Honest failure, no data      |
| USER_REQUESTED_HUMAN    | USER_REQUESTED_HUMAN     | from the request      | Case proposal                |
| DOCUMENT_REQUIRES_REVIEW| DOCUMENT_REQUIRES_REVIEW | PA_READINESS_REVIEW   | Checklist shown              |
| APPROVAL_REQUIRED       | APPROVAL_REQUIRED        | PA_READINESS_REVIEW   | "Not an approval" reply      |
| OUT_OF_SCOPE            | OUT_OF_SCOPE             | OTHER                 | Refusal (e.g. medical)       |

No priority or response-time promise is attached: Phase 1 defines none."""

from __future__ import annotations

from dataclasses import dataclass

_POLICY = {
    "NO_ADEQUATE_ANSWER": "KNOWLEDGE_GAP",
    "CONFLICTING_INFORMATION": "KNOWLEDGE_GAP",
    "TOOL_FAILURE": "TECHNICAL_ISSUE",
    "USER_REQUESTED_HUMAN": "OTHER",
    "DOCUMENT_REQUIRES_REVIEW": "PA_READINESS_REVIEW",
    "APPROVAL_REQUIRED": "PA_READINESS_REVIEW",
    "OUT_OF_SCOPE": "OTHER",
    "USER_INITIATED": "OTHER",
}


@dataclass(frozen=True)
class Decision:
    offer: bool
    escalation_reason: str
    category: str
    requires_confirmation: bool = True  # always: no automatic case creation exists


def decide(condition: str, category: str | None = None) -> Decision:
    if condition not in _POLICY:
        raise ValueError(f"unknown escalation condition {condition}")
    return Decision(True, condition, category or _POLICY[condition])


def readiness_decision(readiness_status: str) -> Decision | None:
    """A checklist with missing/unreadable items or manual-review items can be sent to an agent;
    a complete one isn't offered (nothing for a reviewer to resolve beyond normal submission)."""
    if readiness_status == "DOCUMENTATION_APPEARS_COMPLETE":
        return None
    return decide("DOCUMENT_REQUIRES_REVIEW")


def readiness_summary(procedure_code: str, readiness_status: str, counts: dict[str, int],
                      attention: list[str]) -> str:
    """Minimal case summary: codes and counts only, no document contents or member data."""
    items = "; ".join(attention[:8]) or "none"
    return (f"Documentation readiness review requested for {procedure_code}: {readiness_status} "
            f"({counts.get('SATISFIED', 0)} satisfied, {counts.get('MISSING', 0)} missing, "
            f"{counts.get('UNREADABLE', 0)} unreadable, {counts.get('NEEDS_MANUAL_REVIEW', 0)} need manual "
            f"review). Items needing attention: {items}.")[:2000]
