"""POST/GET /support-cases and GET /authorization/requirements: confirmation-only creation,
idempotency, ownership, atomic audit, and requirement sources."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.session import get_session_factory
from app.models import AuditLog, SupportCase
from app.services.audit_service import AuditService
from tests.conftest import ADMIN_A, AGENT_A, MEMBER_A, MEMBER_B, PROVIDER_A
from tests.helpers import assert_error, latest_audit

pytestmark = pytest.mark.postgres

BODY = {"category": "CLAIM_INQUIRY", "summary": "Member needs help with claim SYN-CLM-2026-000101 pending info."}


@pytest.fixture
def create(client, auth):
    def _post(email, body=None, key=None, headers=None):
        h = {**auth(email), **({"Idempotency-Key": str(key)} if key is not False else {}), **(headers or {})}
        return client.post("/api/v1/support-cases", json=body or BODY, headers=h)

    return _post


def _count(key=None):
    with get_session_factory()() as s:
        q = select(func.count()).select_from(SupportCase)
        if key:
            q = q.where(SupportCase.idempotency_key == key)
        return s.scalar(q)


def test_create_case_is_open_and_audited_atomically(create):
    key = uuid4()
    r = create(MEMBER_A, key=key)
    assert r.status_code == 201, r.text
    case = r.json()
    assert case["status"] == "OPEN" and case["case_number"].startswith("CASE-")
    assert case["category"] == "CLAIM_INQUIRY" and case["escalation_reason"] == "USER_INITIATED"
    assert [e["event_type"] for e in case["events"]] == ["CREATED"]
    event = latest_audit("SUPPORT_CASE_CREATED", case["case_number"])
    assert event.event_metadata == {"category": "CLAIM_INQUIRY", "escalation_reason": "USER_INITIATED"}
    assert "SYN-CLM" not in str(event.event_metadata)  # summary text is never audited


def test_replay_with_same_key_returns_the_same_case(create):
    key = uuid4()
    first = create(MEMBER_A, key=key)
    second = create(MEMBER_A, key=key)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["case_id"] == second.json()["case_id"]
    assert _count(key) == 1


def test_reused_key_with_a_different_body_is_rejected(create):
    key = uuid4()
    assert create(MEMBER_A, key=key).status_code == 201
    assert_error(create(MEMBER_A, {**BODY, "category": "OTHER"}, key=key), 409, "IDEMPOTENCY_KEY_REUSED")
    assert _count(key) == 1


def test_same_key_from_another_user_is_a_separate_case(create):
    key = uuid4()
    a, b = create(MEMBER_A, key=key), create(MEMBER_B, key=key)
    assert (a.status_code, b.status_code) == (201, 201) and a.json()["case_id"] != b.json()["case_id"]


@pytest.mark.parametrize("key", [False, "not-a-uuid", ""])
def test_idempotency_key_is_required(create, key):
    assert_error(create(MEMBER_A, key=key), 400, "IDEMPOTENCY_KEY_REQUIRED")


@pytest.mark.parametrize(
    "extra",
    [{"status": "RESOLVED"}, {"created_by_user_id": str(uuid4())}, {"case_number": "CASE-2026-999999"},
     {"assigned_agent_id": str(uuid4())}],
)
def test_server_controlled_fields_are_rejected(create, extra):
    assert create(MEMBER_A, {**BODY, **extra}, key=uuid4()).status_code == 422


@pytest.mark.parametrize("email", [AGENT_A, ADMIN_A])
def test_roles_without_case_create_are_forbidden(create, email):
    assert_error(create(email, key=uuid4()), 403, "FORBIDDEN")


def test_foreign_session_and_claim_links_are_not_found(create, client, auth):
    chat = client.post("/api/v1/chat", json={"message": "hello there friend", "client_message_id": str(uuid4())},
                       headers=auth(MEMBER_B))
    assert chat.status_code == 200, chat.text
    foreign_session = chat.json()["session_id"]
    assert_error(create(MEMBER_A, {**BODY, "related_session_id": foreign_session}, key=uuid4()),
                 404, "RESOURCE_NOT_FOUND")
    assert_error(create(MEMBER_A, {**BODY, "related_claim_number": "SYN-CLM-2026-000201"}, key=uuid4()),
                 404, "RESOURCE_NOT_FOUND")
    own = create(MEMBER_A, {**BODY, "related_claim_number": "SYN-CLM-2026-000101"}, key=uuid4())
    assert own.status_code == 201 and own.json()["related_claim_number"] == "SYN-CLM-2026-000101"


def test_failed_audit_write_leaves_no_phantom_case(create, monkeypatch):
    def broken(self, session, action, outcome, **kw):
        row = AuditService.build(action, outcome, **kw)
        row.action = None  # NOT NULL violation at commit, after the case row was flushed
        session.add(row)

    monkeypatch.setattr(AuditService, "add_to_transaction", broken)
    key = uuid4()
    assert_error(create(MEMBER_A, key=key), 500, "CASE_CREATION_FAILED")
    assert _count(key) == 0


def test_cases_are_visible_only_to_their_creator(create, client, auth):
    case = create(MEMBER_A, key=uuid4()).json()
    mine = client.get("/api/v1/support-cases", headers=auth(MEMBER_A)).json()["items"]
    assert case["case_id"] in {c["case_id"] for c in mine}
    theirs = client.get("/api/v1/support-cases", headers=auth(MEMBER_B)).json()["items"]
    assert case["case_id"] not in {c["case_id"] for c in theirs}
    assert_error(client.get(f"/api/v1/support-cases/{case['case_id']}", headers=auth(MEMBER_B)),
                 404, "RESOURCE_NOT_FOUND")
    assert latest_audit("ACCESS_DENIED", case["case_id"]) is not None
    detail = client.get(f"/api/v1/support-cases/{case['case_id']}", headers=auth(MEMBER_A))
    assert detail.status_code == 200 and detail.json()["summary"] == BODY["summary"]


def test_status_filter(create, client, auth):
    create(PROVIDER_A, key=uuid4())
    assert client.get("/api/v1/support-cases?status=OPEN", headers=auth(PROVIDER_A)).json()["items"]
    assert client.get("/api/v1/support-cases?status=RESOLVED", headers=auth(PROVIDER_A)).json()["items"] == []


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/v1/support-cases").status_code == 401
    assert client.post("/api/v1/support-cases", json=BODY, headers={"Idempotency-Key": str(uuid4())}).status_code \
        == 401


# --- requirements endpoint ------------------------------------------------------------------------


def test_requirements_include_verified_sources(client, auth, knowledge):
    r = client.get("/api/v1/authorization/requirements/SYN-PROC-PT-EXTENDED", headers=auth(PROVIDER_A))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence_status"] == "SUPPORTED" and len(body["requirements"]) == 4
    assert all(req["source"]["document_title"] for req in body["requirements"])
    assert latest_audit("REQUIREMENTS_LOOKUP").outcome == "SUCCESS"


def test_unknown_or_malformed_procedure(client, auth, knowledge):
    assert_error(client.get("/api/v1/authorization/requirements/SYN-PROC-NOPE", headers=auth(MEMBER_A)),
                 404, "REQUIREMENT_SET_NOT_FOUND")  # doc 06 §3.7 error code
    assert client.get("/api/v1/authorization/requirements/DROP-TABLE", headers=auth(MEMBER_A)).status_code == 422


def test_audit_rows_are_never_written_without_a_case(db_session):
    # Every SUPPORT_CASE_CREATED audit row refers to a case that exists.
    refs = db_session.scalars(select(AuditLog.resource_ref).where(AuditLog.action == "SUPPORT_CASE_CREATED")).all()
    numbers = set(db_session.scalars(select(SupportCase.case_number)).all())
    assert refs and set(refs) <= numbers
