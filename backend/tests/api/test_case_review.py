"""Phase 7: human review of support cases, audit queries, metrics and knowledge gaps (PostgreSQL)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import (
    AuditLog,
    ConversationMessage,
    ConversationSession,
    SupportCase,
    SupportCaseEvent,
    ToolInvocation,
    User,
)
from tests.conftest import ADMIN_A, AGENT_A, MEMBER_A, MEMBER_B, PROVIDER_A
from tests.helpers import assert_error, latest_audit

pytestmark = pytest.mark.postgres
AGENT_B = "taylor.agent@example.test"
BODY = {"category": "CLAIM_INQUIRY", "summary": "Member needs help understanding a pending claim (synthetic)."}


@pytest.fixture
def api(client, auth):
    class Api:
        def create(self, email=MEMBER_A, body=None):
            r = client.post("/api/v1/support-cases", json=body or BODY,
                            headers={**auth(email), "Idempotency-Key": str(uuid4())})
            assert r.status_code == 201, r.text
            return r.json()

        def get(self, email, case_id):
            return client.get(f"/api/v1/support-cases/{case_id}", headers=auth(email))

        def patch(self, email, case, **changes):
            body = {"version": case["version"], **changes}
            return client.patch(f"/api/v1/support-cases/{case['case_id']}", json=body, headers=auth(email))

        def ok(self, email, case, **changes):
            r = self.patch(email, case, **changes)
            assert r.status_code == 200, r.text
            return r.json()

        def scope(self, email, scope, **params):
            return client.get("/api/v1/support-cases", params={"scope": scope, **params}, headers=auth(email))

    return Api()


def _events(case_id):
    with get_session_factory()() as s:
        return [(e.event_type, e.from_status, e.to_status) for e in s.scalars(
            select(SupportCaseEvent).where(SupportCaseEvent.case_id == case_id).order_by(SupportCaseEvent.created_at))]


# --- lifecycle ------------------------------------------------------------------------------------


def test_full_review_lifecycle_with_history_and_audit(api):
    case = api.create()
    assert case["status"] == "OPEN" and case["assigned_to"] is None and case["allowed_actions"] == ["add_note",
                                                                                                    "cancel"]
    queue = api.scope(AGENT_A, "queue").json()["items"]
    assert case["case_id"] in {c["case_id"] for c in queue}

    preview = api.get(AGENT_A, case["case_id"]).json()
    assert preview["view"] == "summary" and preview["allowed_actions"] == ["assign_to_me"]
    case = api.ok(AGENT_A, preview, assign_to_me=True)
    assert case["status"] == "ASSIGNED" and case["assigned_to"]["display_name"] == "Sam Reviewer"
    assert case["view"] == "full" and case["version"] == 2
    assert case["case_id"] not in {c["case_id"] for c in api.scope(AGENT_A, "queue").json()["items"]}
    assert case["case_id"] in {c["case_id"] for c in api.scope(AGENT_A, "assigned").json()["items"]}

    case = api.ok(AGENT_A, case, status="IN_PROGRESS")
    case = api.ok(AGENT_A, case, status="AWAITING_USER", note="Please share the itemized bill.")
    member_view = api.get(MEMBER_A, case["case_id"]).json()
    assert member_view["status"] == "AWAITING_USER"
    assert any(e["note"] == "Please share the itemized bill." for e in member_view["events"])
    case = api.ok(MEMBER_A, member_view, note="Uploaded it today.")  # answering resumes the work
    assert case["status"] == "IN_PROGRESS"
    case = api.ok(AGENT_A, case, status="RESOLVED", resolution_note="Explained the pending status.")
    assert case["resolved_at"] and case["resolution_note"] == "Explained the pending status."
    case = api.ok(AGENT_A, case, status="CLOSED")
    assert case["closed_at"] and case["allowed_actions"] == []

    assert _events(case["case_id"]) == [
        ("CREATED", None, "OPEN"), ("ASSIGNED", "OPEN", "ASSIGNED"), ("STATUS_CHANGED", "ASSIGNED", "IN_PROGRESS"),
        ("STATUS_CHANGED", "IN_PROGRESS", "AWAITING_USER"), ("NOTE_ADDED", None, None),
        ("STATUS_CHANGED", "AWAITING_USER", "IN_PROGRESS"), ("STATUS_CHANGED", "IN_PROGRESS", "RESOLVED"),
        ("STATUS_CHANGED", "RESOLVED", "CLOSED"),
    ]
    with get_session_factory()() as s:
        actions = [a.action for a in s.scalars(select(AuditLog).where(
            AuditLog.resource_ref == case["case_number"]).order_by(AuditLog.id))]
        changed = s.scalars(select(AuditLog).where(AuditLog.resource_ref == case["case_number"],
                                                   AuditLog.action == "SUPPORT_CASE_STATUS_CHANGED")).all()
    assert actions.count("SUPPORT_CASE_ASSIGNED") == 1 and actions.count("SUPPORT_CASE_NOTE_ADDED") == 1
    assert {(a.event_metadata["from_status"], a.event_metadata["to_status"]) for a in changed} >= {
        ("RESOLVED", "CLOSED"), ("IN_PROGRESS", "RESOLVED")}
    assert all("bill" not in str(a.event_metadata) for a in changed)  # notes are never audited


def test_invalid_transition_is_rejected_and_audited_without_side_effects(api):
    case = api.ok(AGENT_A, api.get(AGENT_A, api.create()["case_id"]).json(), assign_to_me=True)
    err = assert_error(api.patch(AGENT_A, case, status="RESOLVED", resolution_note="x"), 409,
                       "INVALID_STATUS_TRANSITION")
    assert "ASSIGNED -> RESOLVED" in err["details"][0]["issue"]
    assert latest_audit("SUPPORT_CASE_UPDATE_REJECTED", case["case_number"]).outcome == "FAILURE"
    again = api.get(AGENT_A, case["case_id"]).json()
    assert again["status"] == "ASSIGNED" and again["version"] == case["version"]
    assert _events(case["case_id"])[-1] == ("ASSIGNED", "OPEN", "ASSIGNED")


def test_stale_version_and_duplicate_requests(api):
    case = api.get(AGENT_A, api.create()["case_id"]).json()
    first = api.patch(AGENT_A, case, assign_to_me=True)
    duplicate = api.patch(AGENT_A, case, assign_to_me=True)  # double click: same (now stale) version
    assert first.status_code == 200
    assert_error(duplicate, 409, "VERSION_CONFLICT")
    assert_error(api.patch(AGENT_B, case, assign_to_me=True), 404, "RESOURCE_NOT_FOUND")  # no longer visible
    assert len([e for e in _events(case["case_id"]) if e[0] == "ASSIGNED"]) == 1


def test_missing_required_fields(api):
    case = api.ok(AGENT_A, api.get(AGENT_A, api.create()["case_id"]).json(), assign_to_me=True)
    case = api.ok(AGENT_A, case, status="IN_PROGRESS")
    assert_error(api.patch(AGENT_A, case, status="RESOLVED"), 422, "VALIDATION_ERROR")
    assert_error(api.patch(AGENT_A, case, status="AWAITING_USER"), 422, "VALIDATION_ERROR")
    assert_error(api.patch(ADMIN_A, case, status="CANCELLED"), 422, "VALIDATION_ERROR")


def test_role_and_field_restrictions(api, db_session):
    case = api.create()
    assert_error(api.patch(MEMBER_A, case, assign_to_me=True), 403, "FORBIDDEN")
    agent_id = db_session.scalar(select(User.id).where(User.email == AGENT_A))
    assert_error(api.patch(MEMBER_A, case, assigned_to_user_id=str(agent_id)), 403, "FORBIDDEN")
    assert_error(api.patch(AGENT_A, case, assigned_to_user_id=str(agent_id)), 403, "FORBIDDEN")
    assert api.patch(MEMBER_A, case, status="OPEN", created_by_user_id=str(uuid4())).status_code == 422
    assert api.patch(MEMBER_A, case, version=case["version"], case_number="CASE-2026-999999").status_code == 422
    assert_error(api.patch(MEMBER_B, case, note="hello"), 404, "RESOURCE_NOT_FOUND")  # not theirs
    assert_error(api.patch(PROVIDER_A, case, note="hello"), 404, "RESOURCE_NOT_FOUND")


def test_admin_assignment_validates_the_assignee(api, db_session):
    case = api.get(ADMIN_A, api.create()["case_id"]).json()
    member_id = db_session.scalar(select(User.id).where(User.email == MEMBER_B))
    assert_error(api.patch(ADMIN_A, case, assigned_to_user_id=str(member_id)), 422, "INVALID_ASSIGNEE")
    assert_error(api.patch(ADMIN_A, case, assigned_to_user_id=str(uuid4())), 422, "INVALID_ASSIGNEE")
    taylor = db_session.scalar(select(User.id).where(User.email == AGENT_B))
    case = api.ok(ADMIN_A, case, assigned_to_user_id=str(taylor), reason="Balancing the queue")
    assert case["assigned_to"]["display_name"] == "Taylor Queue" and case["view"] == "summary"
    # The previous agent can't see it any more; the new one can.
    assert_error(api.get(AGENT_A, case["case_id"]), 404, "RESOURCE_NOT_FOUND")
    assert api.get(AGENT_B, case["case_id"]).json()["view"] == "full"
    agents = {a["display_name"]: a for a in api_get(api, ADMIN_A, "/api/v1/admin/support-agents")}
    assert set(agents) == {"Sam Reviewer", "Taylor Queue"} and agents["Taylor Queue"]["open_assigned_count"] >= 1


def api_get(api, email, path):
    from fastapi.testclient import TestClient  # noqa: F401  (client comes from the fixture closure)

    return api._client.get(path, headers=api._auth(email)).json()


@pytest.fixture(autouse=True)
def _expose(api, client, auth):
    api._client, api._auth = client, auth


def test_member_cancel_and_reopen_window(api, db_session):
    cancelled = api.ok(MEMBER_A, api.create(), status="CANCELLED")
    assert cancelled["status"] == "CANCELLED" and cancelled["allowed_actions"] == []
    case = api.ok(AGENT_A, api.get(AGENT_A, api.create()["case_id"]).json(), assign_to_me=True)
    case = api.ok(AGENT_A, api.ok(AGENT_A, case, status="IN_PROGRESS"), status="RESOLVED", resolution_note="Done")
    mine = api.get(MEMBER_A, case["case_id"]).json()
    assert "reopen" in mine["allowed_actions"]
    with get_session_factory()() as s, s.begin():
        s.get(SupportCase, case["case_id"]).resolved_at = datetime.now(UTC) - timedelta(days=15)
    assert_error(api.patch(MEMBER_A, mine, status="IN_PROGRESS", note="Not fixed"), 422, "VALIDATION_ERROR")


def test_scopes_are_enforced_server_side(api):
    for email, scope in ((MEMBER_A, "queue"), (MEMBER_A, "all"), (AGENT_A, "mine"), (AGENT_A, "all"),
                         (ADMIN_A, "queue"), (PROVIDER_A, "assigned")):
        assert_error(api.scope(email, scope), 403, "FORBIDDEN")
    mine = api.scope(MEMBER_B, "mine").json()["items"]
    assert all(c["case_id"] for c in mine)
    created = api.create(MEMBER_B)
    assert created["case_id"] not in {c["case_id"] for c in api.scope(MEMBER_A, "mine").json()["items"]}
    assert created["case_id"] in {c["case_id"] for c in api.scope(ADMIN_A, "all", limit=100).json()["items"]}


def test_pagination_and_filters(api):
    ids = {api.create(MEMBER_B, {**BODY, "category": "DOCUMENT_ISSUE"})["case_id"] for _ in range(3)}
    seen, cursor = [], None
    while True:
        params = {"category": "DOCUMENT_ISSUE", "limit": 2, **({"cursor": cursor} if cursor else {})}
        page = api.scope(MEMBER_B, "mine", **params).json()
        seen += [c["case_id"] for c in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert ids <= set(seen) and len(seen) == len(set(seen))  # every case once, none twice
    assert api.scope(MEMBER_B, "mine", cursor="not-a-cursor").status_code == 422
    one = api.scope(MEMBER_B, "mine", case_number=api.get(MEMBER_B, next(iter(ids))).json()["case_number"]).json()
    assert len(one["items"]) == 1


def test_summary_view_hides_linked_content_and_notes(api):
    case = api.ok(AGENT_A, api.get(AGENT_A, api.create(body={**BODY, "related_claim_number":
                                                             "SYN-CLM-2026-000101"})["case_id"]).json(),
                  assign_to_me=True)
    case = api.ok(AGENT_A, case, note="Internal note for the member")
    assert case["related_claim_number"] == "SYN-CLM-2026-000101" and case["related_claim_status"]
    admin_view = api.get(ADMIN_A, case["case_id"]).json()
    assert admin_view["view"] == "summary" and admin_view["related_claim_number"] is None
    assert all(e["note"] is None for e in admin_view["events"])
    assert latest_audit("SUPPORT_CASE_VIEWED", case["case_number"]).actor_role == "ADMIN"


# --- case-linked documents and checklists (Phase 6 integration) -----------------------------------


def test_assigned_agent_can_open_linked_checklist_and_documents(client, auth, api, knowledge):
    from tests.doc_helpers import PA_LINES, text_pdf

    pdf = text_pdf(PA_LINES + [str(uuid4())])
    doc = client.post("/api/v1/documents", files={"file": ("form.pdf", pdf, "application/pdf")},
                      headers=auth(PROVIDER_A)).json()
    client.post(f"/api/v1/documents/{doc['document_id']}/analyze", headers=auth(PROVIDER_A))
    checklist = client.post("/api/v1/authorization/readiness", headers=auth(PROVIDER_A), json={
        "procedure_code": "SYN-PROC-MRI-LUMBAR", "document_ids": [doc["document_id"]]}).json()
    offer = checklist["escalation_offer"]
    assert offer["category"] == "PA_READINESS_REVIEW" and offer["escalation_reason"] == "DOCUMENT_REQUIRES_REVIEW"
    assert "SYN-M-" not in offer["summary"]
    # Before any case links it, the agent can't see it.
    assert client.get(f"/api/v1/authorization/checklists/{checklist['checklist_id']}",
                      headers=auth(AGENT_A)).status_code == 404
    case = api.create(PROVIDER_A, {k: offer[k] for k in ("category", "escalation_reason", "summary",
                                                         "related_checklist_id", "document_ids")})
    reloaded = client.get(f"/api/v1/authorization/checklists/{checklist['checklist_id']}",
                          headers=auth(PROVIDER_A)).json()
    assert reloaded["review_state"] == "AWAITING_REVIEW" and reloaded["escalation_offer"] is None
    case = api.ok(AGENT_A, api.get(AGENT_A, case["case_id"]).json(), assign_to_me=True)
    assert case["documents"] == [{"document_id": doc["document_id"], "original_filename": "form.pdf"}]
    seen = client.get(f"/api/v1/authorization/checklists/{checklist['checklist_id']}", headers=auth(AGENT_A))
    assert seen.status_code == 200 and seen.json()["items"] == checklist["items"]
    fields = client.get(f"/api/v1/documents/{doc['document_id']}", headers=auth(AGENT_A))
    assert fields.status_code == 200 and fields.json()["latest_job"]["fields"]
    assert latest_audit("DOCUMENT_VIEWED", doc["document_id"]).actor_role == "SUPPORT_AGENT"
    case = api.ok(AGENT_A, case, status="IN_PROGRESS")
    assert client.get(f"/api/v1/authorization/checklists/{checklist['checklist_id']}",
                      headers=auth(PROVIDER_A)).json()["review_state"] == "UNDER_REVIEW"
    assert client.get(f"/api/v1/authorization/checklists/{checklist['checklist_id']}",
                      headers=auth(AGENT_B)).status_code == 404  # not their case
    assert client.get(f"/api/v1/documents/{doc['document_id']}", headers=auth(AGENT_B)).status_code == 404


def test_linking_someone_elses_checklist_or_document_is_refused(client, auth, api):
    for extra in ({"related_checklist_id": str(uuid4())}, {"document_ids": [str(uuid4())]}):
        r = client.post("/api/v1/support-cases", json={**BODY, **extra},
                        headers={**auth(MEMBER_A), "Idempotency-Key": str(uuid4())})
        assert_error(r, 404, "RESOURCE_NOT_FOUND")


# --- audit API ------------------------------------------------------------------------------------


def test_audit_events_are_admin_only_read_only_and_minimal(client, auth, api):
    case = api.create()
    for email in (MEMBER_A, AGENT_A, PROVIDER_A):
        assert_error(client.get("/api/v1/admin/audit-events", headers=auth(email)), 403, "FORBIDDEN")
    page = client.get("/api/v1/admin/audit-events", params={"action": "SUPPORT_CASE_CREATED", "limit": 5,
                                                             "resource_ref": case["case_number"]},
                      headers=auth(ADMIN_A)).json()
    assert [e["action"] for e in page["items"]] == ["SUPPORT_CASE_CREATED"]
    event = page["items"][0]
    assert event["actor"]["display_name"] == "Priya Synthetic" and event["outcome"] == "SUCCESS"
    assert set(event) == {"id", "occurred_at", "request_id", "actor", "action", "resource_type", "resource_ref",
                          "outcome", "reason_code", "metadata"}
    assert BODY["summary"] not in str(page)
    first = client.get("/api/v1/admin/audit-events", params={"limit": 2}, headers=auth(ADMIN_A)).json()
    second = client.get("/api/v1/admin/audit-events", params={"limit": 2, "cursor": first["next_cursor"]},
                        headers=auth(ADMIN_A)).json()
    assert first["items"][-1]["id"] > second["items"][0]["id"]
    for method in ("delete", "patch", "put", "post"):
        r = getattr(client, method)("/api/v1/admin/audit-events", headers=auth(ADMIN_A))
        assert r.status_code == 405
    assert client.get("/api/v1/admin/audit-events", params={"outcome": "MAYBE"},
                      headers=auth(ADMIN_A)).status_code == 422
    assert latest_audit("AUDIT_EVENTS_VIEWED").actor_role == "ADMIN"


# --- metrics and knowledge gaps (isolated past period, hand-computed expectations) ------------------

DAY = datetime(2020, 3, 10, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def history(database):
    """Synthetic records dated in March 2020 so no other test touches the period."""
    with get_session_factory()() as s, s.begin():
        users = {u.email: u for u in s.scalars(select(User))}
        priya, lee, robin = users[MEMBER_A], users[MEMBER_B], users["robin.member@example.test"]
        sam = users[AGENT_A]

        def add_case(n, status, category, reason, created, resolved=None, assigned=None, session=None):
            s.add(SupportCase(case_number=f"CASE-2020-9{n:05d}", created_by_user_id=priya.id, category=category,
                              status=status, escalation_reason=reason, summary="Synthetic metric test case.",
                              idempotency_key=uuid4(), request_hash="x" * 64, created_at=created, updated_at=created,
                              resolved_at=resolved, assigned_to_user_id=assigned, related_session_id=session))

        sessions = {}
        for u in (priya, lee, robin):
            sess = ConversationSession(user_id=u.id, title="metrics", expires_at=DAY + timedelta(days=30),
                                       created_at=DAY, last_message_at=DAY)
            s.add(sess)
            s.flush()
            sessions[u.email] = sess.id
        add_case(1, "OPEN", "CLAIM_INQUIRY", "USER_REQUESTED_HUMAN", DAY, session=sessions[MEMBER_A])
        add_case(2, "IN_PROGRESS", "CLAIM_INQUIRY", "NO_ADEQUATE_ANSWER", DAY + timedelta(days=1), assigned=sam.id)
        add_case(3, "RESOLVED", "KNOWLEDGE_GAP", "NO_ADEQUATE_ANSWER", DAY + timedelta(days=1),
                 resolved=DAY + timedelta(days=1, hours=4), assigned=sam.id)
        add_case(4, "CLOSED", "TECHNICAL_ISSUE", "TOOL_FAILURE", DAY, resolved=DAY + timedelta(hours=10),
                 assigned=sam.id)
        add_case(5, "OPEN", "OTHER", "USER_INITIATED", datetime(2020, 3, 31, 23, 59, tzinfo=UTC))  # last minute
        add_case(6, "OPEN", "OTHER", "USER_INITIATED", datetime(2020, 4, 1, 0, 0, tzinfo=UTC))  # outside

        def msg(email, sender, status=None, topic=None, intent="GENERAL_FAQ", latency=None):
            s.add(ConversationMessage(session_id=sessions[email], sender=sender, content="(synthetic)",
                                      intent=intent if sender == "ASSISTANT" else None, evidence_status=status,
                                      gap_topic=topic, latency_ms=latency, created_at=DAY))

        for email, status, topic, latency in (
            (MEMBER_A, "INSUFFICIENT", "acupuncture coverage", 100),
            (MEMBER_B, "INSUFFICIENT", "acupuncture coverage", 200),
            (MEMBER_B, "INSUFFICIENT", "acupuncture coverage", 300),
            ("robin.member@example.test", "CONFLICTING", "telehealth copay", 400),  # one user only: suppressed
            (MEMBER_A, "SUPPORTED", None, 500),
        ):
            msg(email, "USER")
            msg(email, "ASSISTANT", status, topic, latency=latency)
        s.add(ToolInvocation(user_id=priya.id, tool_name="get_required_documents", requested_by="router",
                             arguments_redacted={"procedure_code": "SYN-PROC-KNEE-SCOPE"}, result_status="NOT_FOUND",
                             latency_ms=5, created_at=DAY))
        s.add(ToolInvocation(user_id=priya.id, tool_name="get_plan_benefits", requested_by="router",
                             arguments_redacted={}, result_status="EXECUTION_ERROR", latency_ms=5,
                             created_at=DAY))
    return "2020-03-01", "2020-03-31"


def test_metrics_match_hand_computed_values(client, auth, history):
    m = client.get("/api/v1/admin/metrics", params={"from": history[0], "to": history[1]},
                   headers=auth(ADMIN_A)).json()
    c = m["cases"]
    assert m["period"] == {"from": "2020-03-01", "to": "2020-03-31", "timezone": "UTC"}
    assert c["created"] == 5  # case 6 starts 2020-04-01 00:00 UTC: outside
    assert {k: v for k, v in c["created_by_status"].items() if v} == {"OPEN": 2, "IN_PROGRESS": 1, "RESOLVED": 1,
                                                                    "CLOSED": 1}
    assert c["created_by_category"]["CLAIM_INQUIRY"] == 2 and c["created_by_category"]["KNOWLEDGE_GAP"] == 1
    assert c["created_by_escalation_reason"]["NO_ADEQUATE_ANSWER"] == 2
    assert c["escalated_from_chat"] == 1 and c["resolved_in_period"] == 2
    assert c["median_hours_to_resolution"] == 7.0  # median of 4 h and 10 h
    assert c["created_per_day"] == [{"date": "2020-03-10", "count": 2}, {"date": "2020-03-11", "count": 2},
                                    {"date": "2020-03-31", "count": 1}]
    chat = m["chat"]
    assert chat["user_messages"] == 5 and chat["assistant_messages"] == 5
    assert chat["by_evidence_status"] == {"SUPPORTED": 1, "INSUFFICIENT": 3, "CONFLICTING": 1, "VERIFIED_RECORD": 0,
                                          "NOT_APPLICABLE": 0}
    assert chat["latency_ms"] == {"p50": 300, "p95": 480, "sample_size": 5}
    assert m["tools"]["get_plan_benefits"]["EXECUTION_ERROR"] == 1
    assert m["documents"]["jobs_by_status"] == {"QUEUED": 0, "RUNNING": 0, "COMPLETED": 0,
                                                "COMPLETED_WITH_WARNINGS": 0, "FAILED": 0}
    assert m["unavailable"] == [] and m["feedback"] == {"HELPFUL": 0, "NOT_HELPFUL": 0}


def test_empty_period_returns_real_zeros(client, auth):
    m = client.get("/api/v1/admin/metrics", params={"from": "2019-01-01", "to": "2019-01-31"},
                   headers=auth(ADMIN_A)).json()
    assert m["cases"]["created"] == 0 and m["cases"]["median_hours_to_resolution"] is None
    assert m["chat"]["latency_ms"] == {"p50": None, "p95": None, "sample_size": 0}  # no data, not zero
    assert m["tools"] == {} and m["cases"]["created_per_day"] == []


def test_metrics_validation_and_access(client, auth):
    for params in ({"from": "2026-02-01", "to": "2026-01-01"}, {"from": "2024-01-01", "to": "2026-01-01"},
                   {"from": "not-a-date"}):
        assert client.get("/api/v1/admin/metrics", params=params, headers=auth(ADMIN_A)).status_code == 422
    for email in (MEMBER_A, AGENT_A, PROVIDER_A):
        assert_error(client.get("/api/v1/admin/metrics", headers=auth(email)), 403, "FORBIDDEN")
        assert_error(client.get("/api/v1/admin/knowledge-gaps", headers=auth(email)), 403, "FORBIDDEN")
    assert client.get("/api/v1/admin/metrics", headers=auth(ADMIN_A)).status_code == 200  # default 30 days


def test_knowledge_gaps_aggregate_and_suppress(client, auth, history):
    g = client.get("/api/v1/admin/knowledge-gaps", params={"from": history[0], "to": history[1]},
                   headers=auth(ADMIN_A)).json()
    assert g["items"] == [{"gap_topic": "acupuncture coverage", "evidence_status": "INSUFFICIENT", "occurrences": 3,
                           "distinct_users": 2, "last_seen_at": g["items"][0]["last_seen_at"],
                           "example_intents": ["GENERAL_FAQ"]}]
    assert g["suppressed_topics"] == 1  # "telehealth copay" came from a single user
    assert {"intent": "GENERAL_FAQ", "evidence_status": "CONFLICTING", "occurrences": 1} in g["by_intent"]
    assert g["requirement_set_misses"] == [{"requested_procedure_code": "SYN-PROC-KNEE-SCOPE", "occurrences": 1}]
    assert g["tool_failures"] == [{"tool_name": "get_plan_benefits", "result_status": "EXECUTION_ERROR",
                                   "occurrences": 1}]
    assert "(synthetic)" not in str(g)  # message text is never part of the report
    empty = client.get("/api/v1/admin/knowledge-gaps", params={"from": "2019-01-01", "to": "2019-01-31"},
                       headers=auth(ADMIN_A)).json()
    assert empty["items"] == [] and empty["tool_failures"] == []


def test_case_change_and_its_audit_row_commit_together(api, monkeypatch):
    from app.services.audit_service import AuditService

    case = api.get(AGENT_A, api.create()["case_id"]).json()

    def broken(self, session, action, outcome, **kw):
        row = AuditService.build(action, outcome, **kw)
        row.action = None  # NOT NULL violation at commit
        session.add(row)

    monkeypatch.setattr(AuditService, "add_to_transaction", broken)
    r = api.patch(AGENT_A, case, assign_to_me=True)
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "NotNull" not in r.text and "SQL" not in r.text
    monkeypatch.undo()
    after = api.get(AGENT_A, case["case_id"]).json()
    assert after["status"] == "OPEN" and after["version"] == case["version"]  # nothing changed
    assert [e[0] for e in _events(case["case_id"])] == ["CREATED"]


def test_patch_response_includes_the_history_row_it_just_wrote(api):
    # Regression (Phase 8, D8-06): the PATCH response used a stale events collection.
    case = api.ok(AGENT_A, api.get(AGENT_A, api.create()["case_id"]).json(), assign_to_me=True)
    assert [e["event_type"] for e in case["events"]] == ["CREATED", "ASSIGNED"]
    case = api.ok(AGENT_A, case, status="IN_PROGRESS")
    assert [e["event_type"] for e in case["events"]] == ["CREATED", "ASSIGNED", "STATUS_CHANGED"]
