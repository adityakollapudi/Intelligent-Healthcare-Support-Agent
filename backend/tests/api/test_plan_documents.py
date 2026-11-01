"""Customers can read the plan documents the assistant answers from, within the same access rules."""

import pytest
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import KnowledgeDocument
from tests.conftest import AGENT_A, MEMBER_A, MEMBER_B, PROVIDER_A

pytestmark = pytest.mark.postgres
URL = "/api/v1/knowledge/documents"


@pytest.fixture
def docs(client, auth, knowledge):
    return lambda email: client.get(URL, headers=auth(email)).json()


def _by_key(key):
    with get_session_factory()() as s:
        return s.scalars(select(KnowledgeDocument).where(KnowledgeDocument.document_key == key,
                                                         KnowledgeDocument.lifecycle_status == "ACTIVE")).first().id


def test_member_sees_general_documents_and_their_own_plan_first(docs):
    items = docs(MEMBER_A)
    titles = [d["title"] for d in items]
    assert items[0]["is_my_plan"] and "Gold" in items[0]["title"]
    assert not any("Bronze" in t for t in titles) and not any("Internal" in t for t in titles)


def test_bronze_member_sees_their_own_plan_instead(docs):
    titles = [d["title"] for d in docs(MEMBER_B)]
    assert any("Bronze" in t for t in titles) and not any("Gold" in t for t in titles)


def test_members_cant_open_another_plans_or_internal_documents(client, auth, knowledge):
    for key in ("bronze-plan-benefit-guide", "support-agent-procedures", "provider-admin-faq"):
        assert client.get(f"{URL}/{_by_key(key)}", headers=auth(MEMBER_A)).status_code == 404


def test_staff_scope_matches_their_audience(client, auth, knowledge):
    internal = _by_key("support-agent-procedures")
    assert client.get(f"{URL}/{internal}", headers=auth(PROVIDER_A)).status_code == 404
    assert client.get(f"{URL}/{internal}", headers=auth(AGENT_A)).status_code == 200


def test_replaced_versions_arent_listed(docs):
    assert sum("Imaging Prior Authorization" in d["title"] for d in docs(MEMBER_A)) == 1


def test_document_reads_as_sections_with_the_passages_cited_in_chat(client, auth, knowledge):
    doc = _by_key("gold-plan-benefit-guide")
    body = client.get(f"{URL}/{doc}", headers=auth(MEMBER_A)).json()
    assert body["is_my_plan"] and body["sections"] and all(s["text"] and s["chunk_ids"] for s in body["sections"])
    with get_session_factory()() as s:
        chunks = {str(c.id) for c in s.get(KnowledgeDocument, doc).chunks}
    assert {c for section in body["sections"] for c in section["chunk_ids"]} == chunks


def test_sign_in_is_required(client, knowledge):
    assert client.get(URL).status_code == 401
