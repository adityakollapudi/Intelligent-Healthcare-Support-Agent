"""Deterministic request routing (doc 07 §1 pre-rules). Routing only, never authorization: every
route still goes through the tool executor or retrieval filters, which apply their own checks.

Order matters: refusals first (prompt disclosure / other people's data, medical advice), then
account-specific tool routes, then document questions. A route that names a tool only *suggests*
it; the executor decides whether it may run."""

from __future__ import annotations

import re
from enum import StrEnum


class Intent(StrEnum):
    GENERAL_FAQ = "GENERAL_FAQ"  # answered from documents (RAG)
    BENEFITS_INFO = "BENEFITS_INFO"  # stored plan benefits (get_plan_benefits)
    CLAIM_STATUS = "CLAIM_STATUS"  # own claim records (get_claim_status)
    REQUIRED_DOCUMENTS = "REQUIRED_DOCUMENTS"  # configured requirement sets (get_required_documents)
    UPLOADED_DOCUMENT = "UPLOADED_DOCUMENT"  # the caller's own uploaded files (read_my_documents)
    SUPPORT_CASE_CREATE = "SUPPORT_CASE_CREATE"  # create_support_case (proposal + user confirmation)
    SUPPORT_CASE_TRACK = "SUPPORT_CASE_TRACK"
    ACCOUNT_SPECIFIC = "ACCOUNT_SPECIFIC"  # balances, accumulators, authorization decisions: no tool exists
    HUMAN_ASSISTANCE = "HUMAN_ASSISTANCE"
    UNSUPPORTED_OR_AMBIGUOUS = "UNSUPPORTED_OR_AMBIGUOUS"


class Route(StrEnum):
    RAG = "RAG"
    CLAIM_TOOL = "CLAIM_TOOL"
    BENEFITS_TOOL = "BENEFITS_TOOL"
    REQUIREMENTS = "REQUIREMENTS"  # tool if a configured procedure matches, otherwise RAG
    UPLOADED_DOCUMENT = "UPLOADED_DOCUMENT"
    CASE_CREATE = "CASE_CREATE"
    CASE_TRACK = "CASE_TRACK"
    ACCOUNT_LOOKUP_UNAVAILABLE = "ACCOUNT_LOOKUP_UNAVAILABLE"
    MEDICAL = "MEDICAL"
    PROMPT_DISCLOSURE = "PROMPT_DISCLOSURE"
    CLARIFY = "CLARIFY"


CLAIM_NUMBER = re.compile(r"\bSYN-CLM-\d{4}-\d{6}\b", re.I)
PLAN_CODE = re.compile(r"\bSYN-PLAN-[A-Z0-9-]{2,20}\b", re.I)
_CASE_NUMBER = re.compile(r"\bCASE-\d{4}-\d{6}\b", re.I)
_MY_CLAIM = re.compile(
    r"\b(status of (my|our)|my|our)\b.{0,40}\bclaims?\b|\bclaims?\b.{0,30}\b(i|we) (submitted|filed|sent)\b|"
    r"\b(check|look up|show|list) (my|our) claims?\b",
    re.I,
)
_CLAIM_STATUS_WORDS = re.compile(r"\b(status|where is|happened|paid yet|processed yet|update on|check|look up|show|list|last updated)\b", re.I)
_ACCOUNT = re.compile(
    r"\b(how much (of|have) (my|i)|my (remaining|deductible (left|remaining|met|balance))|"
    r"(have|has) (i|my) met|met my (deductible|out-of-pocket)|my (balance|spending|accumulator)|"
    r"(is|was) my (treatment|authorization|prior auth\w*|request|procedure) (approved|denied|decided)|"
    r"status of my (request|authorization)|when will (my|the) claim be paid)\b",
    re.I,
)
_HUMAN = re.compile(
    r"\b(talk|speak|chat) (to|with) (a |an )?(human|person|agent|representative|someone)\b|\b(human|real person|live agent)\b",
    re.I,
)
_CASE_CREATE = re.compile(
    r"\b(create|open|file|raise|start|submit|log|make)\b.{0,25}\b(support )?(case|ticket)\b|\bescalate (this|it|my)\b",
    re.I,
)
# Questions *about* the case process ("what happens after I open a ticket?") are document questions.
_PROCESS_QUESTION = re.compile(
    r"^\s*(what happens|what is the process|how (do|does|long|soon|quickly|can)|when (do|does|will|can|should)|why)\b",
    re.I,
)
_BENEFITS_TOOL = re.compile(
    r"\b(my|our) (plan'?s? )?benefits\b|\bplan benefits\b|\bbenefits? (summary|table|list|for (my|the|this) plan)\b|"
    r"\bwhat (are|is) (my|the) (plan'?s? )?(benefits|coverage summary)\b",
    re.I,
)
_REQUIREMENT_WORDS = re.compile(
    r"\b(documents?|documentation|paperwork|requirements?|required|checklist|forms?|must (include|contain)|"
    r"need to (submit|include|send|provide)|what (do|does) (i|we|it|a|the request) need)\b",
    re.I,
)
_MEDICAL = re.compile(
    r"\b(diagnos\w*|symptom\w*|dosage|dose|prescribe (me|for|something)|should i take|medication for|treat(ment)? for|"
    r"is it serious|side effects?|which medicine|what medicine)\b",
    re.I,
)
# "my uploaded report", "this PDF", "the patient's case"; how-to questions about uploading stay document questions.
_MY_UPLOAD = re.compile(
    r"\b(uploaded|my (document|file|report|pdf|record)s?|(this|that|the|attached|latest|last|above) "
    r"(document|file|report|pdf|packet)|medical (document|report|record)s?|patient'?s? (case|document|report|file)s?)\b|"
    r"\.pdf\b",
    re.I,
)
_READINESS = re.compile(
    r"\b(readiness|ready for|ready to submit|checklist|requirements?|required|anything missing|what('s| is) missing|"
    r"complete enough|is .{0,30}complete)\b",
    re.I,
)
_UPLOAD_HOWTO = re.compile(
    r"\b(how (do|can|should|to)|how long do i|can i|where (do|can)|(what|which) (file|format|type)s?|need to upload|"
    r"(are|is) (required|needed)|required for|must (i|include|contain))\b",
    re.I,
)
# Reading what a document says is fine; asking what to do about it is medical advice.
_ADVICE = re.compile(
    r"\b(should i|should (he|she|they|the patient)|prescribe|dosage|dose|which medicine|what medicine|"
    r"is (it|this|that) serious|side effects?|diagnose (me|him|her|them))\b",
    re.I,
)
_DISCLOSURE = re.compile(
    r"\b(system prompt|your (instructions|prompt|rules)|ignore (all |the |your )?(previous|prior|above) instructions|"
    r"api key|you are now (an? )?(admin|administrator|developer|system)|execute (a |an |the )?(database |sql )?query|"
    r"run (a |an )?(sql|shell|command|script)|drop table|select \* from)\b",
    re.I,
)
_OTHER_PEOPLE = re.compile(
    r"\b(every|all|other|another|someone else'?s?) (members?|users?|patients?|people)('s|s')?\b|\banother member'?s\b",
    re.I,
)
_STOP = set(
    """a an the and or of to in on for with is are was were be it its this that what which who how when
where why do does did can could should would will i my me we our you your they there here about from by as at
if any not no yes so please tell know need want get got have has had""".split()
)
_FOLLOW_UP = re.compile(
    r"^(and|also|what about|how about|which (document|source)|explain|why|simpler|say that|more detail)\b|\b(that|it|this|those|them)\b",
    re.I,
)
_WORD = re.compile(r"[A-Za-z0-9$]+")

_CATEGORY_WORDS = {
    "IMAGING": ("mri", "x-ray", "xray", "imaging", "scan"),
    "PHYSICAL_THERAPY": ("physical therapy", "pt visit", "pt session", "physiotherapy"),
    "PRIMARY_CARE": ("primary care", "family doctor", "office visit", "pcp"),
    "SPECIALIST": ("specialist",),
    "EMERGENCY": ("emergency", " er ", "er visit"),
    "PREVENTIVE": ("preventive", "check-up", "checkup", "annual visit"),
}


def route(question: str, *, has_history: bool) -> tuple[Intent, Route]:
    q = question.strip()
    if _DISCLOSURE.search(q) or _OTHER_PEOPLE.search(q):
        return Intent.UNSUPPORTED_OR_AMBIGUOUS, Route.PROMPT_DISCLOSURE
    howto = _UPLOAD_HOWTO.search(q) and not (wants_readiness(q) and re.search(r"\b(uploaded|my|this|\w+'s)\b", q))
    if _MY_UPLOAD.search(q) and not howto and not _ADVICE.search(q):
        return Intent.UPLOADED_DOCUMENT, Route.UPLOADED_DOCUMENT
    if _MEDICAL.search(q):
        return Intent.UNSUPPORTED_OR_AMBIGUOUS, Route.MEDICAL
    if _CASE_NUMBER.search(q):
        return Intent.SUPPORT_CASE_TRACK, Route.CASE_TRACK
    if _CASE_CREATE.search(q) and not _PROCESS_QUESTION.search(q):
        return Intent.SUPPORT_CASE_CREATE, Route.CASE_CREATE
    if _HUMAN.search(q):
        return Intent.HUMAN_ASSISTANCE, Route.CASE_CREATE
    if _ACCOUNT.search(q):
        return Intent.ACCOUNT_SPECIFIC, Route.ACCOUNT_LOOKUP_UNAVAILABLE
    if CLAIM_NUMBER.search(q) or (_MY_CLAIM.search(q) and _CLAIM_STATUS_WORDS.search(q)):
        return Intent.CLAIM_STATUS, Route.CLAIM_TOOL
    if PLAN_CODE.search(q) or _BENEFITS_TOOL.search(q):
        return Intent.BENEFITS_INFO, Route.BENEFITS_TOOL
    content = [w for w in _WORD.findall(q.lower()) if w not in _STOP]
    if len(content) < 2 and not (has_history and is_follow_up(q)):
        return Intent.UNSUPPORTED_OR_AMBIGUOUS, Route.CLARIFY  # e.g. "the form": too little to route on
    if _REQUIREMENT_WORDS.search(q):
        return Intent.REQUIRED_DOCUMENTS, Route.REQUIREMENTS
    return Intent.GENERAL_FAQ, Route.RAG


def wants_readiness(question: str) -> bool:
    return bool(_READINESS.search(question))


def wants_advice(question: str) -> bool:
    return bool(_ADVICE.search(question))


def wants_summary(question: str) -> bool:
    return bool(re.search(r"\b(summar\w+|overview|review|brief|describe|tell me about|what does .{0,40} say|"
                          r"explain (this|the|my)|analy[sz]e)\b", question, re.I))


def is_follow_up(question: str) -> bool:
    return len(_WORD.findall(question)) <= 10 and bool(_FOLLOW_UP.search(question.strip()))


def benefit_category(question: str) -> str | None:
    lowered = f" {question.lower()} "
    hits = [cat for cat, words in _CATEGORY_WORDS.items() if any(w in lowered for w in words)]
    return hits[0] if len(hits) == 1 else None
