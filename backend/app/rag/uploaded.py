"""Answers about the caller's own uploaded documents, without an LLM (facts are quoted, never inferred).

Pages come from the read_my_documents tool (owner-only, audited, read live: no document text is stored).
Pages are split into statements ("Symptoms: ..."); a summary lists the labeled statements, and a question
quotes the best-matching ones. Document text is data: nothing in it can change what happens here."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_BOILERPLATE = re.compile(
    r"^(page \d+|field|value|use limitation)$|synthetic test data|test data only|entirely fictional|"
    r"^synthetic sample\b|^synthetic test patient packet$|document ai / readiness testing",
    re.I,
)
_LABELED = re.compile(r"^([A-Za-z][A-Za-z /'()-]{1,40}):\s*(.+)$")
_UNREADABLE_VALUE = re.compile(r"unreadable text|cannot be reliably read|obscured", re.I)
_WORD = re.compile(r"[a-z0-9]+")
_NAME_WORD = re.compile(r"\b([A-Z][a-z]{2,})(?:'s)?\b")
_FULL_NAME = re.compile(r"\b([A-Z][a-z]{2,}(?: [A-Z][a-z]{2,})+)(?:'s)?\b|\b([A-Z][a-z]{2,})'s\b")
_NOT_NAMES = set(
    """please review summarize summarise summary give show tell explain describe what who when where why how
which does did can could would the this that these those document documents file files report reports pdf
patient patients medical uploaded upload analyze analyse read check prior authorization plan gold silver
bronze physical therapy lumbar spine member provider doctor dr""".split()
)
_STOP = set(
    """a an the and or of to in on for with is are was were be it its this that what which who whom how when where
why do does did can could should would will i my me we our you your they their his her there here about from by
as at if any not no yes so please tell know need want get got have has had give show find say says said list
document documents file files report reports pdf uploaded upload patient patients medical record records case
mentioned stated written according""".split()
)
SYNONYMS = {
    "doctor": {"provider"}, "physician": {"provider"}, "dob": {"birth"}, "birthday": {"birth"}, "born": {"birth"},
    "age": {"birth"}, "diagnosis": {"assessment"}, "problem": {"assessment", "symptoms"},
    "pain": {"symptoms", "assessment"}, "condition": {"assessment"}, "treatment": {"history", "plan"},
    "therapy": {"history"}, "exam": {"examination"}, "findings": {"examination"}, "test": {"procedure"},
    "scan": {"procedure"}, "insurance": {"plan"}, "id": {"member"}, "next": {"plan"}, "complaint": {"symptoms"},
}
# (label fragment, shown in summaries in this order). The first group is identity and request, the second clinical.
_SUMMARY_LABELS = (
    "patient name", "patient", "date of birth", "dob", "member id", "member number", "plan code", "procedure",
    "procedure code", "ordering provider", "referring provider", "facility", "requested service date", "order date",
    "referral date", "referred service", "encounter date", "note date",
)
_CLINICAL_LABELS = ("symptoms", "history", "examination", "assessment", "plan")
_NO_REPEAT_ACROSS = {"patient": "patient name", "dob": "date of birth"}


@dataclass(frozen=True)
class Statement:
    document_id: str
    filename: str
    page: int
    section: str | None
    text: str
    label: str | None = None
    value: str | None = None


@dataclass
class Summary:
    filename: str
    lines: list[Statement] = field(default_factory=list)
    not_stated: list[str] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)
    conflicts: dict[str, list[Statement]] = field(default_factory=dict)


def _heading(line: str) -> bool:
    return line.isupper() and not any(ch.isdigit() for ch in line) and len(line.split()) <= 8


def _pair_table_rows(lines: list[str]) -> list[str]:
    """Two-column tables reach us as label line, value line; rejoin them as "label: value"."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line, following = lines[i], lines[i + 1] if i + 1 < len(lines) else None
        is_label = len(line.split()) <= 4 and ":" not in line and line[-1] not in ".!?" and not _heading(line)
        if is_label and following and ":" not in following and not _heading(following):
            out.append(f"{line}: {following}")
            i += 2
            continue
        out.append(line)
        i += 1
    return out


def _rejoin_wrapped(lines: list[str]) -> list[str]:
    """A sentence wrapped onto the next line continues in lower case."""
    out: list[str] = []
    for line in lines:
        if out and line[0].islower() and out[-1][-1] not in ".!?:":
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def statements(document_id: str, filename: str, page: int, text: str) -> list[Statement]:
    raw = [ln.strip() for ln in text.split("\n") if ln.strip()]
    # The title above a two-column table ("Field" / "Value") is not one of its labels.
    titles = {i for i in range(len(raw) - 1) if raw[i + 1].lower() == "field"}
    lines = [ln for i, ln in enumerate(raw) if i not in titles and not _BOILERPLATE.search(ln)]
    result: list[Statement] = []
    section: str | None = None
    for line in _pair_table_rows(_rejoin_wrapped(lines)):
        if _heading(line):
            section = line
            continue
        for part in (p.strip() for p in line.split(" | ")):
            if not part:
                continue
            m = _LABELED.match(part)
            result.append(Statement(document_id, filename, page, section, part, m.group(1).strip() if m else None,
                                    m.group(2).strip() if m else None))
    return result


def full_person_name(question: str) -> str | None:
    """A name the user clearly means as a person, e.g. "Aarav Sharma" or "Aarav's"."""
    for m in _FULL_NAME.finditer(question):
        words = (m.group(1) or m.group(2)).split()
        words = [w for w in words if w.lower() not in _NOT_NAMES]
        if words:
            return " ".join(words)
    return None


def name_tokens(question: str) -> list[str]:
    return [w for w in _NAME_WORD.findall(question) if w.lower() not in _NOT_NAMES]


def mentions(page_texts: list[str], name: str) -> bool:
    text = " ".join(page_texts)
    return all(re.search(rf"\b{re.escape(w)}\b", text, re.I) for w in name.split())


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _terms(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall(text.lower())}


def question_terms(question: str, names: list[str]) -> set[str]:
    skip = {n.lower() for n in names}
    words = [w for w in _WORD.findall(question.lower()) if w not in _STOP and w not in skip]
    terms = {_stem(w) for w in words}
    for word in words:
        terms |= SYNONYMS.get(word, set())
    return terms


def rank(items: list[Statement], terms: set[str], similarity: list[float], *, limit: int = 3) -> list[Statement]:
    """Label matches count most, then value matches; embedding similarity only breaks ties. A statement
    must share a word with the question: similarity alone returned the patient's name for "blood pressure"."""
    scored: list[tuple[float, int, Statement]] = []
    for index, (item, sim) in enumerate(zip(items, similarity, strict=True)):
        label_hits = len(terms & _terms(item.label or ""))
        text_hits = len(terms & _terms(item.text))
        if not text_hits:
            continue
        scored.append((3 * label_hits + text_hits + sim, -index, item))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    if not scored:
        return []
    best = scored[0][0]
    chosen: list[Statement] = []
    seen: set[str] = set()
    for score, _, item in scored:
        key = item.text.lower()
        if score >= 0.6 * best and key not in seen:
            seen.add(key)
            chosen.append(item)
        if len(chosen) == limit:
            break
    return chosen


def _norm(label: str) -> str:
    return " ".join(_WORD.findall(label.lower())).removeprefix("synthetic ")


def summarize(filename: str, items: list[Statement]) -> Summary:
    summary = Summary(filename)
    by_label: dict[str, list[Statement]] = {}
    for item in items:
        if item.label:
            by_label.setdefault(_norm(item.label), []).append(item)

    wanted = [*_SUMMARY_LABELS, *_CLINICAL_LABELS]
    if not any(label in by_label for label in wanted):  # free-form document: quote its opening statements
        summary.lines = items[:8]
        return summary

    for label in wanted:
        if _NO_REPEAT_ACROSS.get(label) in by_label or label not in by_label:
            continue
        distinct: dict[str, Statement] = {}
        for item in by_label[label]:
            distinct.setdefault((item.value or "").lower(), item)
        readable = [s for s in distinct.values() if not _UNREADABLE_VALUE.search(s.value or "")]
        if not readable:
            summary.unreadable.append(by_label[label][0].label or label)
            continue
        summary.lines.append(readable[0])
        if len(readable) > 1:
            summary.conflicts[readable[0].label or label] = readable

    found_clinical = [c for c in _CLINICAL_LABELS if c in by_label]
    if found_clinical:
        summary.not_stated = [c.capitalize() for c in _CLINICAL_LABELS if c not in by_label]
        if "encounter date" not in by_label:
            summary.not_stated.append("Encounter date")
    return summary
