"""Tool allowlist and schema strictness (no database)."""

import pytest
from pydantic import ValidationError

from app.authz.permissions import Permission
from app.tools.definitions import CreateSupportCaseInput, GetClaimStatusInput, GetRequiredDocumentsInput
from app.tools.registry import TOOLS, anthropic_tool_definitions


def test_allowlist_is_exactly_the_six_tools():
    assert set(TOOLS) == {"get_claim_status", "get_plan_benefits", "get_required_documents", "read_my_documents",
                          "check_document_readiness", "create_support_case"}
    assert {n for n, s in TOOLS.items() if not s.read_only} == {"create_support_case"}
    assert TOOLS["create_support_case"].confirmation == "user"
    assert TOOLS["create_support_case"].any_of_permissions == (Permission.CASES_CREATE,)


def test_model_facing_schemas_forbid_extra_properties():
    defs = anthropic_tool_definitions()
    assert [d["name"] for d in defs] == list(TOOLS)
    for d in defs:
        assert d["input_schema"]["additionalProperties"] is False
        # No identity-bearing argument is exposed to the model: the principal comes from the token.
        assert not {"user_id", "member_id", "member_number", "role"} & set(d["input_schema"].get("properties", {}))


@pytest.mark.parametrize(
    "args",
    [
        {"claim_number": "SYN-CLM-2026-000101", "member_number": "SYN-M-000002"},  # extra field
        {"claim_number": "'; DROP TABLE claims; --"},
        {"claim_number": "CLM-1"},
    ],
)
def test_claim_input_rejects_extra_and_malformed(args):
    with pytest.raises(ValidationError):
        GetClaimStatusInput.model_validate(args)


def test_required_documents_needs_exactly_one_identifier():
    with pytest.raises(ValidationError):
        GetRequiredDocumentsInput.model_validate({})
    with pytest.raises(ValidationError):
        GetRequiredDocumentsInput.model_validate({"procedure_code": "SYN-PROC-MRI-LUMBAR", "procedure_text": "mri"})
    assert GetRequiredDocumentsInput.model_validate({"procedure_text": "lumbar MRI"}).procedure_code is None


@pytest.mark.parametrize(
    "args",
    [
        {"category": "BILLING", "summary": "Please help with my claim question."},  # not an enum value
        {"category": "CLAIM_INQUIRY", "summary": "short"},
        {"category": "CLAIM_INQUIRY", "summary": "Valid summary text here.", "status": "RESOLVED"},
        {"category": "CLAIM_INQUIRY", "summary": "Valid summary text here.", "created_by_user_id": "x"},
    ],
)
def test_support_case_input_rejects_server_controlled_and_invalid_fields(args):
    with pytest.raises(ValidationError):
        CreateSupportCaseInput.model_validate(args)
