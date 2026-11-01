"""Turns a pipeline result into a customer-friendly message in each supported language.

Runs after the pipeline, so routing, tools, permissions and evidence checks are unchanged. Every value comes
from the result (tool records, cited passages); this module only chooses wording. Text that exists only in
English, such as a quoted passage, stays in English and is marked `partial`: it is never rewritten or
guessed here. A configured translator can then translate it (see app.services.translation)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.rag.friendly_text import CLAIM_STATUS, DISCLAIMERS, FIXED, GLOSSARY, REQUIREMENTS, WORDS
from app.rag.language import SUPPORTED
from app.rag.pipeline import PipelineResult

_REQUIREMENT_DISCLAIMER = {
    "te": "ఇవి డాక్యుమెంట్ అవసరాలు మాత్రమే. ఇవి ఉన్నంత మాత్రాన ఆమోదం లేదా కవరేజ్ హామీ కాదు.",
    "hi": "ये सिर्फ़ दस्तावेज़ों की ज़रूरतें हैं। इनके पूरा होने से मंज़ूरी या कवरेज की गारंटी नहीं मिलती।",
}
_FIXED = tuple((re.compile(pattern, re.S), texts) for pattern, texts in FIXED)


@dataclass
class Presented:
    text: dict[str, str]
    partial: bool = False  # True when the Telugu and Hindi versions still contain English passages
    disclaimers: dict[str, list[str]] = field(default_factory=dict)
    suggestions: list[dict[str, Any]] = field(default_factory=list)


def _w(key: str, lang: str, **values: Any) -> str:
    return WORDS[key][lang].format(**values)


def _each(render) -> dict[str, str]:
    return {lang: render(lang) for lang in SUPPORTED}


def _terms(text: str, lang: str, limit: int = 3) -> list[str]:
    return [means[lang] for pattern, means in GLOSSARY if re.search(pattern, text, re.I)][:limit]


def _term_block(text: str, lang: str) -> str:
    lines = _terms(text, lang)
    return f"{_w('terms_heading', lang)}:\n" + "\n".join(f"- {t}" for t in lines) if lines else ""


def _join(*blocks: str) -> str:
    return "\n\n".join(b for b in blocks if b)


def _claims(result: PipelineResult, data: dict) -> Presented:
    claims = data["claims"]
    cited = re.findall(r"\[C\d+\]", " ".join(f"[{i.marker}]" for i in result.cited))

    def one(lang: str) -> str:
        c = claims[0]
        label, meaning, action = CLAIM_STATUS[c["status"]][lang]
        facts = [f"{_w('status', lang)}: {label}", f"{_w('submitted', lang)}: {c['submission_date']}",
                 f"{_w('updated', lang)}: {c['last_status_change_at'][:10]}"]
        if c.get("status_description"):
            facts.append(f"{_w('note', lang)}: {c['status_description']}")
        more = f"{_w('more', lang)} {' '.join(cited)}" if cited else ""
        return _join(_w("claim_heading", lang, number=c["claim_number"]), "\n".join(facts),
                     f"{_w('means', lang)}: {meaning}", f"{_w('next', lang)}: {action}", more)

    def many(lang: str) -> str:
        lines = []
        for c in claims:
            label, meaning, _ = CLAIM_STATUS[c["status"]][lang]
            lines.append(f"- {c['claim_number']}: {label}. {meaning}")
        return _join(_w("claims_heading", lang, count=len(claims)), "\n".join(lines))

    # One claim asked by number shows the full explanation; a list stays short.
    return Presented(_each(one if len(claims) == 1 else many),
                     partial=any(c.get("status_description") for c in claims) and len(claims) == 1)


def _benefits(data: dict, for_member: bool = True) -> Presented:
    plan = data["plan_name"]

    def render(lang: str) -> str:
        if not data["benefits"]:
            return _w("no_benefits", lang, plan=plan)
        missing = _w("not_listed", lang)
        blocks = []
        for b in data["benefits"]:
            lines = [b["service_name"],
                     f"- {_w('in_network', lang)}: {b['in_network_cost_share'] or missing}",
                     f"- {_w('out_network', lang)}: {b['out_of_network_cost_share'] or missing}"]
            if b["visit_limit"]:
                lines.append(f"- {_w('limit', lang)}: {b['visit_limit']}")
            if b["prior_auth_required"]:
                lines.append(f"- {_w('needs_approval', lang)}")
            blocks.append("\n".join(lines))
        values = " ".join(f"{b['in_network_cost_share']} {b['out_of_network_cost_share']}" for b in data["benefits"])
        heading = "benefits_heading" if for_member else "benefits_heading_staff"
        return _join(_w(heading, lang, plan=plan), *blocks, _w("benefits_note", lang),
                     _term_block(values, lang))

    return Presented(_each(render))


def _plain(description: str, lang: str) -> str:
    return REQUIREMENTS.get(description, {}).get(lang, description)


def _requirements(result: PipelineResult, data: dict) -> Presented:
    marker = {r["requirement_code"]: re.search(rf"{r['requirement_code']}:.*?\[(C\d+)\]", result.answer_text)
              for r in data["requirements"]}
    name = data["display_name"].replace(" (fictional requirement set)", "")

    def render(lang: str) -> str:
        lines = []
        for r in data["requirements"]:
            m = marker[r["requirement_code"]]
            lines.append(f"- {_plain(r['description'], lang)}" + (f" [{m.group(1)}]" if m else ""))
        return _join(_w("requirements_heading", lang, name=name), "\n".join(lines), _w("requirements_why", lang),
                     f"{_w('next', lang)}: {_w('requirements_next', lang)}", _w("not_approval", lang))

    return Presented(_each(render))


def _readiness(result: PipelineResult, data: dict) -> Presented:
    sources = next((r["data"]["sources"] for r in result.records if r["kind"] == "document_sources"), [])
    marker = {(s["filename"], s["page"]): s["marker"] for s in sources}
    name = data["display_name"].replace(" (fictional requirement set)", "")
    headline = {"DOCUMENTATION_INCOMPLETE": "readiness_incomplete", "MANUAL_REVIEW_REQUIRED": "readiness_manual",
                "DOCUMENTATION_APPEARS_COMPLETE": "readiness_complete"}[data["readiness_status"]]
    incomplete = data["readiness_status"] == "DOCUMENTATION_INCOMPLETE"

    def render(lang: str) -> str:
        groups = []
        for status in ("SATISFIED", "MISSING", "UNREADABLE", "NEEDS_MANUAL_REVIEW"):
            lines = []
            for i in (x for x in data["items"] if x["status"] == status):
                value = f": {i['found']}" if i["found"] else ""
                tag = marker.get((i["filename"], i["page"]))
                lines.append(f"- {_plain(i['description'], lang)}{value}" + (f" [{tag}]" if tag else ""))
            if lines:
                groups.append(f"{_w(status, lang)}:\n" + "\n".join(lines))
        steps = ""
        if incomplete:
            steps = (f"{_w('readiness_next_heading', lang)}\n- {_w('readiness_next_1', lang)}\n"
                     f"- {_w('readiness_next_2', lang)}")
        closing = _w("readiness_not_rejected", lang) if incomplete else _w("not_approval", lang)
        checked = _w("readiness_checked", lang, files=", ".join(data["document_names"]), name=name)
        return _join(_w(headline, lang), checked, *groups, steps, closing, *data["warnings"])

    return Presented(_each(render))


def _quoted(result: PipelineResult) -> Presented:
    body = result.answer_text
    uploaded = any(r["kind"] == "document_sources" for r in result.records)
    if body.startswith("Here is what the available documents say:"):
        body = body.split("\n", 1)[-1]

    def render(lang: str) -> str:
        note = _w("english_note", lang)
        if uploaded:
            return _join(_w("doc_heading", lang), body, note)
        coverage = _w("coverage_note", lang) if re.search(r"\bcover", result.source_text or "", re.I) else ""
        heading = _w("found_heading" if result.for_member else "found_heading_staff", lang)
        return _join(heading, body, note, coverage, _term_block(body, lang), _w("found_next", lang))

    return Presented(_each(render), partial=True)


def _fixed(result: PipelineResult) -> Presented | None:
    for pattern, texts in _FIXED:
        match = pattern.search(result.answer_text)
        if match:
            values = match.groupdict()
            return Presented({lang: (texts[lang] or result.answer_text).format(**values) for lang in SUPPORTED})
    return None


def _options(result: PipelineResult) -> list[dict[str, Any]]:
    out = []
    for label, message in result.options:
        labels = WORDS[label] if label in WORDS else dict.fromkeys(SUPPORTED, label)
        out.append({"label": labels, "message": message})
    return out


def _guide(result: PipelineResult) -> Presented:
    terms = _each(lambda lang: _term_block(result.source_text or "", lang))
    if result.guide in ("simplify", "define") and terms["en"]:
        return Presented(_each(lambda lang: _join(_w("simplify_heading", lang), terms[lang])))
    key = {"simplify": "simplify_short", "procedures": "guide_procedures",
           "authorization": "guide_authorization", "general_provider": "guide_provider",
           "general_agent": "guide_agent", "general_admin": "guide_admin"}.get(result.guide or "", "guide_general")
    return Presented(_each(lambda lang: _w(key, lang)), suggestions=_options(result))


def _disclaimers(result: PipelineResult) -> dict[str, list[str]]:
    table = {**DISCLAIMERS, "Documentation requirements only": _REQUIREMENT_DISCLAIMER}
    out: dict[str, list[str]] = {}
    for lang in SUPPORTED:
        out[lang] = []
        for text in result.disclaimers:
            match = next((v for prefix, v in table.items() if text.startswith(prefix)), None)
            out[lang].append(match.get(lang, text) if match else text)
    return out


def _body(result: PipelineResult) -> Presented:
    if result.guide:
        return _guide(result)
    if result.answer_text.startswith("I can't confirm"):  # the false-claim guard fired: never restyle its warning
        return Presented(_each(lambda lang: _join(result.answer_text, _w("english_note", lang))), partial=True)
    readiness = next((t.data for t in result.tool_results
                      if t.tool_name == "check_document_readiness" and t.status == "SUCCEEDED"), None)
    if readiness:
        return _readiness(result, readiness)
    for record in result.records:
        if record["kind"] == "claims" and record["data"]["claims"]:
            return _claims(result, record["data"])
        if record["kind"] == "plan_benefits":
            return _benefits(record["data"], result.for_member)
        if record["kind"] == "requirements":
            return _requirements(result, record["data"])
    fixed = _fixed(result)
    if fixed:
        fixed.suggestions = _options(result)
        return fixed
    if result.answer_type == "DOCUMENT_GROUNDED":
        return _quoted(result)
    return Presented(_each(lambda lang: _join(result.answer_text, _w("english_note", lang))), partial=True)


def present(result: PipelineResult) -> Presented:
    presented = _body(result)
    presented.disclaimers = _disclaimers(result)
    return presented
