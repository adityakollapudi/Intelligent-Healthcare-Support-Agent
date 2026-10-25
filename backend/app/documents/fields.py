"""Document-type classification, field extraction and deterministic field validation
(doc 07 §5.2 steps 4–7, §5.3–5.4; schema version 1.0).

Extraction reads labeled lines ("Member number: SYN-M-000001") from the document's own text, so every
raw value is an exact span of a known page (grounded by construction). Instructions inside a document
are just text here: nothing in it can change which fields exist, how they validate, or anything else.

A field that isn't found is ABSENT only when every page could be read. If some page couldn't be read
(OCR missing/failed/low quality), the field is ILLEGIBLE: unreadable is never reported as missing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from app.documents.extraction import PageText

SCHEMA_VERSION = "1.0"
PIPELINE_VERSION = "6.0.0"

PATTERN, PROCEDURE, DATE, TEXT, DURATION = "pattern", "procedure", "date", "text", "duration"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    labels: tuple[str, ...]
    kind: str
    pattern: str | None = None
    max_len: int = 200
    search_whole_text: bool = False  # distinctive patterns may be found without a label


_MEMBER = FieldSpec("member_number", ("member number", "member id", "member no"), PATTERN, r"SYN-M-\d{6}",
                    search_whole_text=True)

SCHEMAS: dict[str, tuple[FieldSpec, ...]] = {
    "PA_REQUEST_FORM": (
        _MEMBER,
        FieldSpec("procedure_code", ("procedure code",), PROCEDURE, r"SYN-PROC-[A-Z0-9-]+", search_whole_text=True),
        FieldSpec("procedure_description", ("procedure description", "requested service", "service requested"),
                  TEXT, max_len=200),
        FieldSpec("requested_service_date", ("requested service date", "date of service"), DATE),
        FieldSpec("ordering_provider_name", ("ordering provider name", "ordering provider"), TEXT, max_len=120),
        FieldSpec("ordering_provider_npi", ("ordering provider npi", "provider npi", "npi"), PATTERN, r"\d{10}"),
        FieldSpec("facility_name", ("facility name", "facility"), TEXT, max_len=150),
        FieldSpec("conservative_therapy_duration", ("conservative therapy duration", "conservative therapy"),
                  DURATION),
        FieldSpec("supporting_rationale", ("supporting rationale", "rationale"), TEXT, max_len=500),
        FieldSpec("request_date", ("request date", "date of request"), DATE),
    ),
    "REFERRAL_LETTER": (
        _MEMBER,
        FieldSpec("referring_provider_name", ("referring provider name", "referring provider"), TEXT, max_len=120),
        FieldSpec("referral_date", ("referral date", "date of referral"), DATE),
        FieldSpec("referred_service", ("referred service", "referred for"), TEXT, max_len=200),
    ),
    "CLINICAL_NOTE_SUMMARY": (
        _MEMBER,
        FieldSpec("note_date", ("note date", "date of note"), DATE),
        FieldSpec("author_name", ("author name", "author"), TEXT, max_len=120),
    ),
    "CLAIM_SUPPORT_LETTER": (
        _MEMBER,
        FieldSpec("claim_number", ("claim number",), PATTERN, r"SYN-CLM-\d{4}-\d{6}", search_whole_text=True),
        FieldSpec("letter_date", ("letter date", "date of letter"), DATE),
    ),
    "UNRECOGNIZED": (),
}

_TITLES = {
    "PA_REQUEST_FORM": re.compile(r"\bprior\s+authori[sz]ation\s+request\b", re.I),
    "REFERRAL_LETTER": re.compile(r"\breferral\s+letter\b", re.I),
    "CLINICAL_NOTE_SUMMARY": re.compile(r"\bclinical\s+note\s+summary\b", re.I),
    "CLAIM_SUPPORT_LETTER": re.compile(r"\bclaim\s+support\s+letter\b", re.I),
}
_DURATION = re.compile(r"\b\d+(?:\.\d+)?\s*(?:weeks?|wks?|days?|months?)\b", re.I)
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%d %B %Y", "%d %b %Y")


@dataclass
class FieldResult:
    field_name: str
    raw_value: str | None
    normalized_value: str | None
    validation_status: str
    validation_message: str | None
    source_page: int | None
    extraction_method: str | None
    confidence: float | None


def classify(pages: list[PageText]) -> str:
    """Keyword rule on the title area (first lines of the first page with text). LLM classification
    from doc 07 §5.2 step 4 is not used in this build (D6-06)."""
    first = next((p for p in pages if p.text.strip()), None)
    if first is None:
        return "UNRECOGNIZED"
    head = "\n".join(first.text.splitlines()[:5])
    hits = [doc_type for doc_type, rx in _TITLES.items() if rx.search(head)]
    return hits[0] if len(hits) == 1 else "UNRECOGNIZED"


def _label_regex(labels: tuple[str, ...]) -> re.Pattern[str]:
    alts = "|".join(r"\s+".join(map(re.escape, label.split())) for label in sorted(labels, key=len, reverse=True))
    return re.compile(rf"^[ \t]*(?:{alts})[ \t]*(?:\([^)\n]*\))?[ \t]*[:\-–][ \t]*(?P<value>[^\n]*)$", re.I | re.M)


@dataclass
class _Hit:
    raw: str
    page: PageText


def _find(spec: FieldSpec, pages: list[PageText]) -> tuple[list[_Hit], bool]:
    """Returns the hits and whether a label was present without a value."""
    rx = _label_regex(spec.labels)
    hits: list[_Hit] = []
    empty_label = False
    for page in pages:
        for m in rx.finditer(page.text):
            value = m.group("value").strip()
            if value:
                hits.append(_Hit(value, page))
            else:
                empty_label = True
    if not hits and spec.search_whole_text and spec.pattern:
        token = re.compile(rf"(?<![A-Za-z0-9-]){spec.pattern}(?![A-Za-z0-9-])")
        for page in pages:
            hits.extend(_Hit(m.group(0), page) for m in token.finditer(page.text))
    return hits, empty_label


def _parse_date(raw: str) -> date | None:
    value = re.sub(r"\s+", " ", raw.strip().rstrip("."))
    for fmt in _DATE_FORMATS:  # numeric dates are read as MM/DD/YYYY (US convention, documented)
        try:
            parsed = datetime.strptime(value, fmt).date()  # noqa: DTZ007 - calendar date, no time zone
        except ValueError:
            continue
        return parsed if 1900 <= parsed.year <= 2100 else None
    return None


def _format_check(spec: FieldSpec, raw: str, active_codes: set[str]) -> tuple[str | None, str | None]:
    """(normalized_value, None) when the format is acceptable, else (None, message)."""
    value = raw.strip()
    if spec.kind in (PATTERN, PROCEDURE):
        token = value.upper() if spec.kind == PROCEDURE else value
        if not re.fullmatch(spec.pattern or "", token):
            return None, "Value doesn't match the expected format"
        if spec.kind == PROCEDURE and token not in active_codes:
            return None, "Not a configured procedure code"
        return token, None
    if spec.kind == DATE:
        parsed = _parse_date(value)
        return (parsed.isoformat(), None) if parsed else (None, "Not a valid date (expected e.g. 2026-11-04)")
    if spec.kind == DURATION:
        m = _DURATION.search(value)
        return (m.group(0), None) if m else (None, "No duration with a unit (days/weeks/months) was found")
    if len(value) > spec.max_len:
        return None, f"Longer than {spec.max_len} characters"
    return value, None


def _ocr_signal(raw: str, page: PageText) -> tuple[float | None, bool]:
    """(mean word confidence 0–1, any word below the illegibility threshold) for OCR'd values."""
    if page.method != "OCR":
        return None, False
    tokens = [t.lower() for t in raw.split()]
    confs = [page.word_confidence[t] for t in tokens if t in page.word_confidence]
    illegible = any(t in page.low_confidence_words for t in tokens)
    return (round(sum(confs) / len(confs) / 100, 3) if confs else None), illegible


def missing_specs(doc_type: str, pages: list[PageText]) -> list[FieldSpec]:
    """Fields the deterministic extractor finds nothing for (candidates for LLM-assisted extraction)."""
    return [s for s in SCHEMAS[doc_type] if not _find(s, pages)[0]]


def extract_fields(
    doc_type: str,
    pages: list[PageText],
    active_codes: set[str],
    low_confidence: float,
    llm_spans: dict[str, tuple[str, int]] | None = None,
) -> list[FieldResult]:
    """llm_spans: grounded (value, page) pairs from llm_extraction, used only where no label matched."""
    unreadable = [p.page_number for p in pages if not p.readable]
    by_number = {p.page_number: p for p in pages}
    results: list[FieldResult] = []
    for spec in SCHEMAS[doc_type]:
        hits, empty_label = _find(spec, pages)
        if not hits and llm_spans and spec.name in llm_spans:
            raw, page_number = llm_spans[spec.name]
            if page_number in by_number:
                hits = [_Hit(raw, by_number[page_number])]
        if not hits:
            if unreadable:
                pages_txt = ", ".join(map(str, unreadable))
                results.append(FieldResult(spec.name, None, None, "ILLEGIBLE",
                                           f"Not found on readable pages; page(s) {pages_txt} could not be fully read",
                                           None, None, None))
            else:
                msg = "Label present but no value" if empty_label else "Not found in document"
                results.append(FieldResult(spec.name, None, None, "ABSENT", msg, None, None, None))
            continue

        first = hits[0]
        normalized, problem = _format_check(spec, first.raw, active_codes)
        distinct = {(_format_check(spec, h.raw, active_codes)[0] or h.raw.strip().lower()) for h in hits}
        confidence, illegible = _ocr_signal(first.raw, first.page)
        method = first.page.method
        if len(distinct) > 1:
            shown = "; ".join(sorted({h.raw.strip() for h in hits}))[:250]
            results.append(FieldResult(spec.name, first.raw, None, "INCONSISTENT",
                                       f"Conflicting values in document: {shown}", first.page.page_number, method,
                                       confidence))
        elif illegible or (problem and first.page.method == "OCR" and first.page.status != "OK"):
            results.append(FieldResult(spec.name, first.raw, None, "ILLEGIBLE",
                                       "Text was read with low OCR confidence", first.page.page_number, method,
                                       confidence))
        elif problem:
            results.append(FieldResult(spec.name, first.raw, None, "INVALID_FORMAT", problem,
                                       first.page.page_number, method, confidence))
        elif confidence is not None and confidence < low_confidence:
            results.append(FieldResult(spec.name, first.raw, normalized, "LOW_CONFIDENCE",
                                       f"OCR confidence {confidence:.2f} is below {low_confidence:.2f}; please check",
                                       first.page.page_number, method, confidence))
        else:
            results.append(FieldResult(spec.name, first.raw, normalized, "VALID", None, first.page.page_number,
                                       method, confidence))
    return results
