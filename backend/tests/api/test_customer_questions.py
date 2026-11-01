"""Everyday customer questions get an answer instead of a referral to a person."""

from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.rag.intent import Route, route
from tests.conftest import MEMBER_A, MEMBER_B, PROVIDER_A

pytestmark = pytest.mark.postgres


@pytest.fixture
def ask(client, app, auth, knowledge):
    overrides = {"chat_rate_limit_per_minute": 1000, "rag_min_relevance": 0.2}
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(update=overrides)

    def _ask(message, email=MEMBER_A, language="en"):
        body = {"message": message, "client_message_id": str(uuid4()), "language": language}
        response = client.post("/api/v1/chat", json=body, headers=auth(email))
        assert response.status_code == 200
        return response.json()

    return _ask


@pytest.mark.parametrize(("question", "term"), [
    ("What is a deductible?", "Deductible:"),
    ("What is coinsurance?", "Coinsurance:"),
    ("What does copay mean?", "Copay:"),
    ("What is an out-of-pocket maximum?", "Out-of-pocket maximum:"),
    ("What is the difference between in-network and out-of-network?", "Out of network:"),
])
def test_insurance_words_are_explained(ask, question, term):
    body = ask(question)
    assert term in body["answer_text"] and not body["proposed_actions"]


@pytest.mark.parametrize("question", ["What plan am I on?", "What is my member ID?", "Which plan do I have?"])
def test_a_member_can_ask_about_their_own_account(ask, question):
    body = ask(question)
    assert "Synthetic Gold Plan" in body["answer_text"] and "SYN-M-000001" in body["answer_text"]
    assert body["evidence_status"] == "VERIFIED_RECORD"


def test_each_member_sees_only_their_own_account(ask):
    body = ask("What is my member ID?", MEMBER_B)
    assert "SYN-M-000002" in body["answer_text"] and "SYN-M-000001" not in body["answer_text"]


def test_staff_have_no_member_account(ask):
    assert "isn't linked" in ask("What is my member ID?", PROVIDER_A)["answer_text"]


@pytest.mark.parametrize("question", ["What is my deductible?", "What is my annual deductible?"])
def test_the_deductible_comes_from_the_members_plan(ask, question):
    body = ask(question)
    assert "$750" in body["answer_text"] and "$3,000" not in body["answer_text"]


def test_the_deductible_differs_by_plan(ask):
    assert "$3,000" in ask("What is my deductible?", MEMBER_B)["answer_text"]


@pytest.mark.parametrize(("question", "amount"), [
    ("How much is a primary care visit?", "$20 copay"),
    ("What is the copay for a specialist visit?", "$40 copay"),
    ("Does my plan cover emergency room visits?", "$150 copay"),
])
def test_service_costs_come_from_the_plan_record_without_a_false_conflict(ask, question, amount):
    body = ask(question)
    assert amount in body["answer_text"] and body["evidence_status"] == "VERIFIED_RECORD"
    assert not body["proposed_actions"] and "disagree" not in body["answer_text"]


def test_the_real_virtual_care_conflict_is_still_reported(ask):
    assert ask("What is the copay for a virtual visit?")["evidence_status"] == "CONFLICTING"


def test_answers_keep_the_customers_language(ask):
    assert "SYN-M-000001" in ask("What is my member ID?", language="hi")["answer_text"]


@pytest.mark.parametrize(("question", "expected"), [
    ("How much of my deductible have I met?", Route.ACCOUNT_LOOKUP_UNAVAILABLE),
    ("What documents do I need for a lumbar MRI prior authorization?", Route.REQUIREMENTS),
    ("Do I need prior authorization for an MRI?", Route.RAG),
])
def test_nearby_questions_keep_their_routes(question, expected):
    assert route(question, has_history=False)[1] is expected
