"""ToolExecutor against the real test database: allowlist, validation, authorization, ownership,
failure handling and the tool_invocations/audit trail. The principal is built the same way the API
builds it, from the seeded user, never from tool arguments."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.authz.dependencies import Principal
from app.models import SupportCase, ToolInvocation
from app.repositories import user_repository
from app.services import claim_service
from app.services.audit_service import AuditService
from app.tools.executor import ToolContext, ToolExecutor
from tests.conftest import ADMIN_A, AGENT_A, MEMBER_A, MEMBER_B, PROVIDER_A
from tests.helpers import latest_audit

pytestmark = pytest.mark.postgres


def principal_for(db, email: str) -> Principal:
    user, member = user_repository.get_with_member(db, user_repository.get_by_email(db, email).id)
    return Principal(
        user_id=user.id, role=user.role, email=user.email, display_name=user.display_name,
        organization_id=user.organization_id, organization_name=None,
        member_id=member.id if member else None, member_number=member.member_number if member else None,
        plan_id=member.plan_id if member else None, plan_code=member.plan.plan_code if member else None,
        token_jti=uuid4(), token_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


@pytest.fixture
def executor(db_session, knowledge):
    def _make(email: str, max_calls: int = 3) -> ToolExecutor:
        ctx = ToolContext(db_session, AuditService(), principal_for(db_session, email), session_id=None)
        return ToolExecutor(ctx, max_calls=max_calls, requested_by="llm")

    return _make


def _invocations(db, user_id):
    return db.scalars(
        select(ToolInvocation).where(ToolInvocation.user_id == user_id).order_by(ToolInvocation.created_at)
    ).all()


def test_unknown_tool_is_rejected_and_logged(executor, db_session):
    ex = executor(MEMBER_A)
    for name in ("delete_claim", "__import__", "get_claim_status; drop table claims", 42):
        result = ex.execute(name, {})
        assert result.status == "INVALID_ARGUMENTS" and result.data is None
    assert _invocations(db_session, ex.ctx.principal.user_id)[-1].result_status == "INVALID_ARGUMENTS"


def test_malformed_arguments_never_reach_the_service(executor, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("service must not be called")

    monkeypatch.setattr(claim_service, "get_claim", boom)
    ex = executor(MEMBER_A, max_calls=10)  # rejected calls also count against the budget
    for args in ({"claim_number": "SYN-CLM-2026-000101", "member_number": "SYN-M-000002"},
                 {"claim_number": "1 OR 1=1"}, "not-an-object", ["SYN-CLM-2026-000101"]):
        assert ex.execute("get_claim_status", args).status == "INVALID_ARGUMENTS", args


def test_member_reads_own_claim(executor, db_session):
    ex = executor(MEMBER_A)
    result = ex.execute("get_claim_status", {"claim_number": "SYN-CLM-2026-000101"})
    assert result.status == "SUCCEEDED"
    assert [c["claim_number"] for c in result.data["claims"]] == ["SYN-CLM-2026-000101"]
    assert result.data["claims"][0]["status"] == "PENDING_INFORMATION"
    row = _invocations(db_session, ex.ctx.principal.user_id)[-1]
    assert (row.tool_name, row.result_status, row.requested_by) == ("get_claim_status", "SUCCEEDED", "llm")
    assert row.arguments_redacted == {"claim_number": "SYN-CLM-2026-000101"}
    event = latest_audit("TOOL_INVOKED")
    assert event.event_metadata == {"tool_name": "get_claim_status", "result_status": "SUCCEEDED",
                                    "requested_by": "llm"}


def test_cross_member_claim_is_not_found_and_audited(executor):
    result = executor(MEMBER_A).execute("get_claim_status", {"claim_number": "SYN-CLM-2026-000201"})
    assert result.status == "NOT_FOUND" and result.data is None
    assert "UNDER_PROCESSING" not in (result.error or "")
    denied = latest_audit("ACCESS_DENIED", "SYN-CLM-2026-000201")
    assert denied.reason_code == "NOT_OWNER"


def test_list_own_claims_only(executor):
    result = executor(MEMBER_B).execute("get_claim_status", {})
    numbers = {c["claim_number"] for c in result.data["claims"]}
    assert result.status == "SUCCEEDED" and numbers and all(n.startswith("SYN-CLM-2026-0002") for n in numbers)


@pytest.mark.parametrize("email", [ADMIN_A, PROVIDER_A])
def test_roles_without_claim_permission_are_denied(executor, email):
    result = executor(email).execute("get_claim_status", {"claim_number": "SYN-CLM-2026-000101"})
    assert result.status == "PERMISSION_DENIED"
    assert latest_audit("ACCESS_DENIED", "get_claim_status").reason_code == "ROLE_NOT_PERMITTED"


def test_member_benefits_default_to_own_plan_and_cannot_read_others(executor):
    ex = executor(MEMBER_A)
    own = ex.execute("get_plan_benefits", {"benefit_category": "PHYSICAL_THERAPY"})
    assert own.status == "SUCCEEDED" and own.data["plan_code"] == "SYN-PLAN-GOLD-01"
    assert {b["benefit_category"] for b in own.data["benefits"]} == {"PHYSICAL_THERAPY"}
    other = ex.execute("get_plan_benefits", {"plan_code": "SYN-PLAN-BRONZE-01"})
    assert other.status in ("NOT_FOUND", "PERMISSION_DENIED") and other.data is None


def test_provider_must_name_a_plan(executor):
    ex = executor(PROVIDER_A)
    assert ex.execute("get_plan_benefits", {}).status == "INVALID_ARGUMENTS"
    assert ex.execute("get_plan_benefits", {"plan_code": "SYN-PLAN-BRONZE-01"}).status == "SUCCEEDED"


def test_required_documents_are_sourced_from_the_active_document(executor):
    result = executor(PROVIDER_A).execute("get_required_documents", {"procedure_text": "lumbar MRI"})
    assert result.status == "SUCCEEDED", result.error
    data = result.data
    assert data["procedure_code"] == "SYN-PROC-MRI-LUMBAR" and len(data["requirements"]) == 6
    assert data["evidence_status"] == "SUPPORTED"
    for req in data["requirements"]:
        assert req["source"] and req["source"]["chunk_id"]
    assert "not an authorization approval" in data["disclaimer"]


def test_heart_surgery_requirements_are_sourced_from_the_active_document(executor):
    result = executor(PROVIDER_A).execute("get_required_documents", {"procedure_text": "heart bypass surgery"})
    assert result.status == "SUCCEEDED", result.error
    data = result.data
    assert data["procedure_code"] == "SYN-PROC-CARDIAC-CABG" and len(data["requirements"]) == 7
    assert data["evidence_status"] == "SUPPORTED"
    assert all(req["source"] and req["source"]["chunk_id"] for req in data["requirements"])


def test_unknown_procedure_is_not_found(executor):
    result = executor(MEMBER_A).execute("get_required_documents", {"procedure_code": "SYN-PROC-HEART-TRANSPLANT"})
    assert result.status == "NOT_FOUND"


def test_support_case_tool_only_proposes(executor, db_session):
    ex = executor(MEMBER_A)
    before = db_session.query(SupportCase).count()
    result = ex.execute("create_support_case", {"category": "CLAIM_INQUIRY",
                                                "summary": "Member asks for help with a pending claim."})
    assert result.status == "CONFIRMATION_REQUIRED"
    assert result.data["requires_confirmation"] is True and result.data["idempotency_key"]
    assert db_session.query(SupportCase).count() == before  # nothing written


@pytest.mark.parametrize("email", [AGENT_A, ADMIN_A])
def test_roles_without_case_create_cannot_propose(executor, email):
    result = executor(email).execute("create_support_case", {"category": "OTHER",
                                                             "summary": "Please create a case for me."})
    assert result.status == "PERMISSION_DENIED"


def test_call_budget_is_enforced(executor):
    ex = executor(MEMBER_A, max_calls=2)
    statuses = [ex.execute("get_claim_status", {}).status for _ in range(4)]
    assert statuses == ["SUCCEEDED", "SUCCEEDED", "CALL_LIMIT_REACHED", "CALL_LIMIT_REACHED"]


def test_database_failure_is_an_execution_error_not_a_fabricated_result(executor, monkeypatch):
    def down(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("connection lost"))

    monkeypatch.setattr(claim_service.claim_repository, "get_for_member", down)
    result = executor(MEMBER_A).execute("get_claim_status", {"claim_number": "SYN-CLM-2026-000101"})
    assert result.status == "EXECUTION_ERROR" and result.data is None
    assert "connection" not in result.error.lower()
