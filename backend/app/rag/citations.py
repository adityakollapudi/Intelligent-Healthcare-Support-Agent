"""Citation validation (FR-011): only markers that were supplied with this request survive."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MARKER = re.compile(r"\[(C\d{1,2})\]")


@dataclass(frozen=True)
class CitationCheck:
    text: str
    valid_markers: list[str]  # in order of first appearance
    status: str  # PASSED | PARTIALLY_REMOVED | ALL_INVALID_DOWNGRADED


def validate(answer_text: str, citations_used: list[str], supplied: set[str]) -> CitationCheck:
    in_text = _MARKER.findall(answer_text)
    invalid = {m for m in in_text if m not in supplied} | {m for m in citations_used if m not in supplied}
    cleaned = _MARKER.sub(lambda m: m.group(0) if m.group(1) in supplied else "", answer_text)
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", cleaned)).strip()
    valid: list[str] = []
    for marker in _MARKER.findall(cleaned):
        if marker not in valid:
            valid.append(marker)
    if not valid:
        return CitationCheck(cleaned, [], "ALL_INVALID_DOWNGRADED")
    return CitationCheck(cleaned, valid, "PARTIALLY_REMOVED" if invalid else "PASSED")
