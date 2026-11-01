"""Everyday customer questions get an answer instead of a referral to a person."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.rag.generation import EvidenceItem, ExtractiveGenerator
from app.rag.intent import Route, route
from app.rag.wording import plain_words
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


def test_everyday_wording_finds_the_deductible_not_the_yearly_maximum(ask):
    body = ask("how much do i owe before the plan starts paying")
    assert "$750" in body["answer_text"] and "$4,000" not in body["answer_text"]


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


@pytest.mark.parametrize(("question", "part"), [
    ("how much do i owe before the plan starts paying", "deductible"),
    ("is there a cap on PT sessions every year", "physical therapy"),
    ("how do i find a doctor", "primary care provider"),
    ("how do i file a claim", "reimbursement"),
    ("they rejected my claim, what's the time limit to dispute it", "appeal"),
    ("i lost my insurance card", "replacement printed member id card"),
    ("how do i get my money back", "reimbursement claim"),
    ("how do I pick a main doctor", "primary care provider"),
])
def test_everyday_words_become_the_documents_words(question, part):
    assert part in plain_words(question).lower()


def test_a_list_stays_with_its_lead_in_and_times_stay_whole():
    content = "The claim must include:\n- A form.\n- A receipt.\nOpen 8:00 a.m. to 6:00 p.m. daily."
    chunk = SimpleNamespace(content=content)
    evidence = [EvidenceItem("C1", chunk)]
    text = ExtractiveGenerator().generate("what must the claim include", evidence, []).answer_text
    assert "The claim must include: A form. A receipt." in text
    text = ExtractiveGenerator().generate("when is it open daily", evidence, []).answer_text
    assert "8:00 a.m. to 6:00 p.m. daily." in text


def test_ordinary_questions_are_left_alone():
    question = "What is my physical therapy copay?"
    assert plain_words(question) == question


def test_a_gap_offers_next_steps_and_never_guesses(ask, app):
    strict = {"chat_rate_limit_per_minute": 1000, "rag_min_relevance": 0.99}  # nothing is relevant enough
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(update=strict)
    body = ask("Is acupuncture covered?")
    assert body["evidence_status"] == "INSUFFICIENT" and "won't guess" in body["answer_text"]
    assert body["proposed_actions"]
    assert [r for r in body["records"] if r["kind"] == "suggestions"]


@pytest.mark.parametrize(("question", "expected"), [
    ("How much of my deductible have I met?", Route.ACCOUNT_LOOKUP_UNAVAILABLE),
    ("What documents do I need for a lumbar MRI prior authorization?", Route.REQUIREMENTS),
    ("Do I need prior authorization for an MRI?", Route.RAG),
])
def test_nearby_questions_keep_their_routes(question, expected):
    assert route(question, has_history=False)[1] is expected
