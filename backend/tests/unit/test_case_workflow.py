"""Case lifecycle rules (doc 02 §3.1) and the escalation policy, without a database."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.cases import escalation
from app.cases.workflow import Actor, CaseState, Change, WorkflowError, allowed_actions, apply

CREATOR, AGENT, OTHER_AGENT, ADMIN, STRANGER = (uuid4() for _ in range(5))
member = Actor(CREATOR, "MEMBER")
agent = Actor(AGENT, "SUPPORT_AGENT")
other = Actor(OTHER_AGENT, "SUPPORT_AGENT")
admin = Actor(ADMIN, "ADMIN")
stranger = Actor(STRANGER, "MEMBER")


def case(status="OPEN", assigned=None, resolved_at=None):
    return CaseState(status, CREATOR, assigned, resolved_at)


def kind_of(fn, *args):
    with pytest.raises(WorkflowError) as exc:
        fn(*args)
    return exc.value.kind


# --- the permitted transitions --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "actor", "change", "status", "assignee", "events"),
    [
        (case(), agent, Change(assign_to_me=True), "ASSIGNED", AGENT, ["ASSIGNED"]),
        (case(), admin, Change(set_assignee=True, assignee=AGENT, assignee_is_active_agent=True),
         "ASSIGNED", AGENT, ["ASSIGNED"]),
        (case(), member, Change(status="CANCELLED"), "CANCELLED", None, ["STATUS_CHANGED"]),
        (case("ASSIGNED", AGENT), agent, Change(status="IN_PROGRESS"), "IN_PROGRESS", AGENT, ["STATUS_CHANGED"]),
        (case("ASSIGNED", AGENT), agent, Change(release=True), "OPEN", None, ["UNASSIGNED"]),
        (case("ASSIGNED", AGENT), agent, Change(status="OPEN"), "OPEN", None, ["UNASSIGNED"]),
        (case("ASSIGNED", AGENT), admin, Change(set_assignee=True, assignee=None), "OPEN", None, ["UNASSIGNED"]),
        (case("IN_PROGRESS", AGENT), admin, Change(set_assignee=True, assignee=OTHER_AGENT,
                                                   assignee_is_active_agent=True), "ASSIGNED", OTHER_AGENT,
         ["ASSIGNED"]),
        (case("IN_PROGRESS", AGENT), agent, Change(status="AWAITING_USER", note="Please send the bill"),
         "AWAITING_USER", AGENT, ["STATUS_CHANGED"]),
        (case("AWAITING_USER", AGENT), agent, Change(status="IN_PROGRESS"), "IN_PROGRESS", AGENT, ["STATUS_CHANGED"]),
        (case("AWAITING_USER", AGENT), member, Change(note="Here it is"), "IN_PROGRESS", AGENT,
         ["NOTE_ADDED", "STATUS_CHANGED"]),
        (case("IN_PROGRESS", AGENT), agent, Change(status="RESOLVED", resolution_note="Explained the status"),
         "RESOLVED", AGENT, ["STATUS_CHANGED"]),
        (case("RESOLVED", AGENT, datetime.now(UTC) - timedelta(days=2)), member,
         Change(status="IN_PROGRESS", note="Still not fixed"), "IN_PROGRESS", AGENT, ["STATUS_CHANGED"]),
        (case("RESOLVED", AGENT, datetime.now(UTC)), agent, Change(status="IN_PROGRESS", note="More work"),
         "IN_PROGRESS", AGENT, ["STATUS_CHANGED"]),
        (case("RESOLVED", AGENT), agent, Change(status="CLOSED"), "CLOSED", AGENT, ["STATUS_CHANGED"]),
        (case("RESOLVED", AGENT), admin, Change(status="CLOSED", reason="Done"), "CLOSED", AGENT, ["STATUS_CHANGED"]),
        (case("AWAITING_USER", AGENT), admin, Change(status="CANCELLED", reason="Duplicate"), "CANCELLED", AGENT,
         ["STATUS_CHANGED"]),
        (case("IN_PROGRESS", AGENT), agent, Change(note="Called the clinic"), "IN_PROGRESS", AGENT, ["NOTE_ADDED"]),
        (case("ASSIGNED", AGENT), agent, Change(status="IN_PROGRESS", note="Starting"), "IN_PROGRESS", AGENT,
         ["STATUS_CHANGED", "NOTE_ADDED"]),
    ],
)
def test_allowed_transitions(state, actor, change, status, assignee, events):
    out = apply(state, actor, change)
    assert (out.new_status, out.new_assignee) == (status, assignee)
    assert [e["event_type"] for e in out.events] == events


def test_resolution_note_is_kept_and_history_records_from_and_to():
    out = apply(case("IN_PROGRESS", AGENT), agent, Change(status="RESOLVED", resolution_note="Fixed"))
    assert out.resolution_note == "Fixed"
    assert out.events[0] | {} == {"event_type": "STATUS_CHANGED", "from_status": "IN_PROGRESS",
                                  "to_status": "RESOLVED", "from_assignee_id": None, "to_assignee_id": None,
                                  "note": "Fixed"}


# --- the rejected ones ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "actor", "change", "kind"),
    [
        (case(), member, Change(status="RESOLVED"), "FORBIDDEN"),
        (case(), member, Change(assign_to_me=True), "FORBIDDEN"),
        (case(), member, Change(set_assignee=True, assignee=AGENT, assignee_is_active_agent=True), "FORBIDDEN"),
        (case(), stranger, Change(note="hi"), "FORBIDDEN"),
        (case(), agent, Change(status="RESOLVED", resolution_note="x"), "FORBIDDEN"),  # not assigned
        (case("ASSIGNED", AGENT), other, Change(status="IN_PROGRESS"), "FORBIDDEN"),
        (case("ASSIGNED", AGENT), other, Change(assign_to_me=True), "INVALID_STATUS_TRANSITION"),
        (case("ASSIGNED", AGENT), agent, Change(status="RESOLVED", resolution_note="x"), "INVALID_STATUS_TRANSITION"),
        (case("OPEN"), admin, Change(status="IN_PROGRESS"), "INVALID_STATUS_TRANSITION"),
        (case("IN_PROGRESS", AGENT), agent, Change(status="RESOLVED"), "MISSING_FIELD"),
        (case("IN_PROGRESS", AGENT), agent, Change(status="AWAITING_USER"), "MISSING_FIELD"),
        (case("IN_PROGRESS", AGENT), admin, Change(status="CANCELLED"), "MISSING_FIELD"),
        (case("RESOLVED", AGENT), admin, Change(status="CLOSED"), "MISSING_FIELD"),
        (case("RESOLVED", AGENT, datetime.now(UTC)), member, Change(status="IN_PROGRESS"), "MISSING_FIELD"),
        (case("RESOLVED", AGENT, datetime.now(UTC) - timedelta(days=15)), member,
         Change(status="IN_PROGRESS", note="again"), "REOPEN_WINDOW_EXPIRED"),
        (case("IN_PROGRESS", AGENT), member, Change(status="CANCELLED"), "INVALID_STATUS_TRANSITION"),
        (case("CLOSED", AGENT), admin, Change(status="IN_PROGRESS"), "INVALID_STATUS_TRANSITION"),
        (case("CANCELLED"), member, Change(note="hello?"), "INVALID_STATUS_TRANSITION"),
        (case(), admin, Change(set_assignee=True, assignee=ADMIN, assignee_is_active_agent=False), "INVALID_ASSIGNEE"),
        (case("ASSIGNED", AGENT), admin, Change(set_assignee=True, assignee=AGENT, assignee_is_active_agent=True),
         "NO_CHANGE"),
        (case("RESOLVED", AGENT), admin, Change(set_assignee=True, assignee=OTHER_AGENT,
                                                assignee_is_active_agent=True), "INVALID_STATUS_TRANSITION"),
        (case("OPEN"), agent, Change(), "NO_CHANGE"),
        (case("OPEN"), member, Change(status="OPEN"), "NO_CHANGE"),
        (case(), member, Change(status="ASSIGNED"), "INVALID_STATUS_TRANSITION"),
    ],
)
def test_rejected_changes(state, actor, change, kind):
    assert kind_of(apply, state, actor, change) == kind


def test_allowed_actions_per_role():
    assert allowed_actions(case(), agent) == ["assign_to_me"]
    assert allowed_actions(case("ASSIGNED", AGENT), agent) == ["add_note", "start", "release"]
    assert allowed_actions(case("ASSIGNED", AGENT), other) == []
    assert allowed_actions(case("IN_PROGRESS", AGENT), agent) == ["add_note", "request_info", "resolve"]
    assert allowed_actions(case(), member) == ["add_note", "cancel"]
    assert allowed_actions(case("RESOLVED", AGENT, datetime.now(UTC)), member) == ["add_note", "reopen"]
    assert allowed_actions(case("RESOLVED", AGENT, datetime.now(UTC) - timedelta(days=20)), member) == ["add_note"]
    assert allowed_actions(case("ASSIGNED", AGENT), admin) == ["assign", "unassign", "cancel"]
    assert allowed_actions(case("CLOSED"), admin) == [] and allowed_actions(case(), stranger) == []


def test_escalation_policy():
    assert escalation.decide("NO_ADEQUATE_ANSWER").category == "KNOWLEDGE_GAP"
    assert escalation.decide("TOOL_FAILURE").category == "TECHNICAL_ISSUE"
    assert escalation.decide("USER_REQUESTED_HUMAN", "CLAIM_INQUIRY").category == "CLAIM_INQUIRY"
    assert all(escalation.decide(c).requires_confirmation for c in ("NO_ADEQUATE_ANSWER", "OUT_OF_SCOPE"))
    with pytest.raises(ValueError):
        escalation.decide("MAKE_IT_URGENT")
    assert escalation.readiness_decision("DOCUMENTATION_APPEARS_COMPLETE") is None
    d = escalation.readiness_decision("MANUAL_REVIEW_REQUIRED")
    assert (d.category, d.escalation_reason) == ("PA_READINESS_REVIEW", "DOCUMENT_REQUIRES_REVIEW")
    summary = escalation.readiness_summary("SYN-PROC-MRI-LUMBAR", "DOCUMENTATION_INCOMPLETE",
                                           {"SATISFIED": 3, "MISSING": 2}, ["REQ-MRI-02 MISSING"])
    assert "3 satisfied, 2 missing" in summary and "SYN-M-" not in summary
