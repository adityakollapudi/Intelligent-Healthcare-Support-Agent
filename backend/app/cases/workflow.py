"""Support-case lifecycle (doc 02 §3.1). Pure rules, no database: given a case snapshot, the actor and
a requested change, return the validated transition or raise. The service applies the result,
writes the history event and the audit row in one transaction.

Actors: CREATOR (case creator), AGENT (support agent; ASSIGNED_AGENT when it's their case), ADMIN.

| From                      | To           | Who                                   | Requires          |
|---------------------------|--------------|---------------------------------------|-------------------|
| OPEN                      | ASSIGNED     | agent (assign to me), admin (assign)  | active agent      |
| OPEN                      | CANCELLED    | creator, admin                        | admin: reason     |
| ASSIGNED                  | IN_PROGRESS  | assigned agent                        | —                 |
| ASSIGNED                  | OPEN         | assigned agent (release), admin       | —                 |
| ASSIGNED/IN_PROGRESS/     | ASSIGNED     | admin (reassign)                      | active agent      |
|   AWAITING_USER           |              |                                       |                   |
| IN_PROGRESS               | AWAITING_USER| assigned agent                        | note              |
| AWAITING_USER             | IN_PROGRESS  | assigned agent; creator's note (auto) | —                 |
| IN_PROGRESS               | RESOLVED     | assigned agent                        | resolution_note   |
| RESOLVED                  | IN_PROGRESS  | creator (≤14 days), assigned agent    | note              |
| RESOLVED                  | CLOSED       | assigned agent, admin                 | admin: reason     |
| any non-terminal          | CANCELLED    | admin                                 | reason            |
CLOSED and CANCELLED are terminal. Nothing else is permitted."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

TERMINAL = {"CLOSED", "CANCELLED"}
REOPEN_WINDOW = timedelta(days=14)
CREATOR, AGENT, ADMIN = "CREATOR", "AGENT", "ADMIN"


class WorkflowError(Exception):
    def __init__(self, kind: str, message: str, **details) -> None:
        super().__init__(message)
        self.kind, self.message, self.details = kind, message, details


def _forbidden(msg: str) -> WorkflowError:
    return WorkflowError("FORBIDDEN", msg)


def _invalid(frm: str, to: str, allowed: list[str]) -> WorkflowError:
    return WorkflowError("INVALID_STATUS_TRANSITION", f"A case can't move from {frm} to {to}.", frm=frm, to=to,
                         allowed=allowed)


def _missing(name: str) -> WorkflowError:
    return WorkflowError("MISSING_FIELD", f"{name} is required for this change.", field=name)


@dataclass(frozen=True)
class CaseState:
    status: str
    created_by: UUID
    assigned_to: UUID | None
    resolved_at: datetime | None = None


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    role: str  # MEMBER | PROVIDER | SUPPORT_AGENT | ADMIN

    def kind(self, case: CaseState) -> str | None:
        if self.role == "ADMIN":
            return ADMIN
        if self.role == "SUPPORT_AGENT":
            return AGENT
        return CREATOR if self.user_id == case.created_by else None


@dataclass(frozen=True)
class Change:
    status: str | None = None
    note: str | None = None
    resolution_note: str | None = None
    assign_to_me: bool = False
    release: bool = False
    set_assignee: bool = False  # admin assignment requested (assignee may be None = unassign)
    assignee: UUID | None = None
    assignee_is_active_agent: bool = False
    reason: str | None = None


@dataclass
class Outcome:
    new_status: str
    new_assignee: UUID | None
    events: list[dict] = field(default_factory=list)  # event_type, from/to status, from/to assignee, note
    resolution_note: str | None = None


def allowed_actions(case: CaseState, actor: Actor, now: datetime | None = None) -> list[str]:
    """Actions the UI may offer. The backend re-validates every request regardless."""
    kind = actor.kind(case)
    s, mine = case.status, case.assigned_to == actor.user_id
    if kind is None or s in TERMINAL:
        return []
    out: list[str] = []
    if kind == CREATOR:
        out.append("add_note")
        if s == "OPEN":
            out.append("cancel")
        if s == "RESOLVED" and _within_reopen(case, now):
            out.append("reopen")
    elif kind == AGENT:
        if s == "OPEN" and case.assigned_to is None:
            out.append("assign_to_me")
        if mine:
            out.append("add_note")
            out += {"ASSIGNED": ["start", "release"], "IN_PROGRESS": ["request_info", "resolve"],
                    "AWAITING_USER": ["resume"], "RESOLVED": ["reopen", "close"]}.get(s, [])
    elif kind == ADMIN:
        out += ["assign"] if s in ("OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_USER") else []
        out += ["unassign"] if s == "ASSIGNED" else []
        out += ["close"] if s == "RESOLVED" else []
        out.append("cancel")
    return out


def _within_reopen(case: CaseState, now: datetime | None) -> bool:
    return case.resolved_at is not None and (now or datetime.now(UTC)) - case.resolved_at <= REOPEN_WINDOW


def apply(case: CaseState, actor: Actor, change: Change, now: datetime | None = None) -> Outcome:
    kind = actor.kind(case)
    if kind is None:
        raise _forbidden("You can't change this case.")
    if case.status in TERMINAL:
        raise _invalid(case.status, change.status or case.status, [])
    is_assigned_agent = kind == AGENT and case.assigned_to == actor.user_id
    s = case.status
    out = Outcome(new_status=s, new_assignee=case.assigned_to)

    def move(to: str, note: str | None = None, event: str = "STATUS_CHANGED", assignee: UUID | None = ...):
        frm_assignee = out.new_assignee
        if assignee is not ...:
            out.new_assignee = assignee
        out.events.append({"event_type": event, "from_status": out.new_status, "to_status": to,
                           "from_assignee_id": frm_assignee if assignee is not ... else None,
                           "to_assignee_id": assignee if assignee is not ... else None, "note": note})
        out.new_status = to

    # --- assignment ---------------------------------------------------------------------------
    if change.assign_to_me:
        if kind != AGENT:
            raise _forbidden("Only support agents can take cases.")
        if s != "OPEN" or case.assigned_to is not None:
            raise _invalid(s, "ASSIGNED", [])
        move("ASSIGNED", event="ASSIGNED", assignee=actor.user_id)
    if change.release:
        if not is_assigned_agent:
            raise _forbidden("Only the assigned agent can release this case.")
        if s != "ASSIGNED":
            raise _invalid(s, "OPEN", ["IN_PROGRESS"])
        move("OPEN", event="UNASSIGNED", assignee=None)
    if change.set_assignee:
        if kind != ADMIN:
            raise _forbidden("Only administrators can assign cases to someone else.")
        if change.assignee is None:
            if s != "ASSIGNED":
                raise _invalid(s, "OPEN", [])
            move("OPEN", note=change.reason, event="UNASSIGNED", assignee=None)
        else:
            if not change.assignee_is_active_agent:
                raise WorkflowError("INVALID_ASSIGNEE", "Cases can only be assigned to an active support agent.")
            if s not in ("OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_USER"):
                raise _invalid(s, "ASSIGNED", [])
            if case.assigned_to == change.assignee:
                raise WorkflowError("NO_CHANGE", "The case is already assigned to that agent.")
            move("ASSIGNED", note=change.reason, event="ASSIGNED", assignee=change.assignee)

    # --- status ---------------------------------------------------------------------------------
    target = change.status
    if target is not None and target != out.new_status:
        cur = out.new_status
        if target == "CANCELLED":
            if kind == ADMIN:
                if not change.reason:
                    raise _missing("reason")
            elif not (kind == CREATOR and cur == "OPEN"):
                raise _forbidden("You can't cancel this case.") if kind != CREATOR else _invalid(cur, target, [])
            move("CANCELLED", note=change.reason or change.note)
        elif target == "IN_PROGRESS":
            if cur == "ASSIGNED" and is_assigned_agent:
                move("IN_PROGRESS")
            elif cur == "AWAITING_USER" and is_assigned_agent:
                move("IN_PROGRESS", note=change.note)
            elif cur == "RESOLVED" and (is_assigned_agent or (kind == CREATOR and _within_reopen(case, now))):
                if not change.note:
                    raise _missing("note")
                move("IN_PROGRESS", note=change.note)
            elif cur == "RESOLVED" and kind == CREATOR:
                raise WorkflowError("REOPEN_WINDOW_EXPIRED", "Resolved cases can be reopened for 14 days.")
            else:
                raise _deny_or_invalid(kind, is_assigned_agent, cur, target)
        elif target == "AWAITING_USER":
            if not (cur == "IN_PROGRESS" and is_assigned_agent):
                raise _deny_or_invalid(kind, is_assigned_agent, cur, target)
            if not change.note:
                raise _missing("note")
            move("AWAITING_USER", note=change.note)
        elif target == "RESOLVED":
            if not (cur == "IN_PROGRESS" and is_assigned_agent):
                raise _deny_or_invalid(kind, is_assigned_agent, cur, target)
            if not change.resolution_note:
                raise _missing("resolution_note")
            out.resolution_note = change.resolution_note
            move("RESOLVED", note=change.resolution_note)
        elif target == "CLOSED":
            if cur != "RESOLVED" or not (is_assigned_agent or kind == ADMIN):
                raise _deny_or_invalid(kind, is_assigned_agent or kind == ADMIN, cur, target)
            if kind == ADMIN and not change.reason:
                raise _missing("reason")
            move("CLOSED", note=change.reason)
        elif target == "OPEN":
            if not (cur == "ASSIGNED" and is_assigned_agent):
                raise _deny_or_invalid(kind, is_assigned_agent, cur, target)
            move("OPEN", event="UNASSIGNED", assignee=None)
        else:  # ASSIGNED is only reachable through assignment fields
            raise _invalid(cur, target, [])
    elif target is not None and not out.events:
        raise WorkflowError("NO_CHANGE", f"The case is already {target}.")
    # A note carried by a status event isn't repeated as a separate NOTE_ADDED event.
    note_used = bool(change.note) and any(e["note"] == change.note for e in out.events)

    # --- note -----------------------------------------------------------------------------------
    if change.note and not note_used:
        if kind == CREATOR or is_assigned_agent:
            if out.new_status in TERMINAL:
                raise _invalid(out.new_status, out.new_status, [])
            out.events.append({"event_type": "NOTE_ADDED", "from_status": None, "to_status": None,
                               "from_assignee_id": None, "to_assignee_id": None, "note": change.note})
            if kind == CREATOR and out.new_status == "AWAITING_USER":
                move("IN_PROGRESS")  # the creator answered the agent's question
        elif not out.events:
            raise _forbidden("Only the creator or the assigned agent can add notes.")

    if not out.events:
        raise WorkflowError("NO_CHANGE", "The request doesn't change anything.")
    return out


def _deny_or_invalid(kind: str, entitled: bool, cur: str, target: str) -> WorkflowError:
    if kind == AGENT and not entitled:
        return _forbidden("Only the assigned agent can do that.")
    if kind == CREATOR and target not in ("CANCELLED", "IN_PROGRESS"):
        return _forbidden("You can't make that change.")
    return _invalid(cur, target, [])
