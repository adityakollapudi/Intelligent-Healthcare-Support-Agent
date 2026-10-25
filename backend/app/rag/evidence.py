"""Evidence assessment: decides whether retrieved passages are good enough to answer from.

The similarity threshold (RAG_MIN_RELEVANCE) is a provisional engineering setting calibrated on the
synthetic evaluation set (docs/phase-4/rag-evaluation-report.md); it is not a measure of truth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.rag.retrieval import Candidate


class EvidenceState(StrEnum):
    SUPPORTED = "SUPPORTED"
    NO_MATCH = "NO_MATCH"  # nothing near the threshold
    LOW_RELEVANCE = "LOW_RELEVANCE"  # something related, but below the threshold
    OUTDATED_ONLY = "OUTDATED_ONLY"  # only a superseded version matched
    CONFLICTING = "CONFLICTING"


LOW_RELEVANCE_MARGIN = 0.08


@dataclass(frozen=True)
class Assessment:
    state: EvidenceState
    evidence: list[Candidate]  # ordered, ACTIVE only, within the context budget
    best_similarity: float


def assess(candidates: list[Candidate], *, min_relevance: float, top_k: int, char_budget: int) -> Assessment:
    active = [c for c in candidates if c.lifecycle_status == "ACTIVE"]
    best_active = max((c.similarity for c in active), default=0.0)
    best_old = max((c.similarity for c in candidates if c.lifecycle_status == "SUPERSEDED"), default=0.0)

    chosen: list[Candidate] = []
    used = 0
    for cand in active:  # already in fused-rank order
        if cand.similarity < min_relevance or len(chosen) >= top_k:
            continue
        if used + len(cand.content) > char_budget and chosen:
            break
        chosen.append(cand)
        used += len(cand.content)

    if chosen:
        return Assessment(EvidenceState.SUPPORTED, chosen, best_active)
    if best_old >= min_relevance and best_old > best_active:
        return Assessment(EvidenceState.OUTDATED_ONLY, [], best_active)
    if best_active >= min_relevance - LOW_RELEVANCE_MARGIN:
        return Assessment(EvidenceState.LOW_RELEVANCE, [], best_active)
    return Assessment(EvidenceState.NO_MATCH, [], best_active)


_MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
_WORD = re.compile(r"[a-z]{4,}")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
SAME_TOPIC_JACCARD = 0.4


def money_conflicts(passages: list[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    """Heuristic over (marker, document_key, text): pairs of sentences from *different* documents
    that are about the same thing (content-word Jaccard >= 0.4) but state different dollar amounts.
    Returns (marker_a, sentence_a, marker_b, sentence_b). Catches simple numeric contradictions only;
    an LLM-flagged conflict is also accepted when it cites two documents."""
    sentences = []
    for marker, doc, text in passages:
        for s in _SENTENCE.split(text):
            money = set(_MONEY.findall(s))
            if money:
                sentences.append((marker, doc, s.strip(" -*>\t"), money, set(_WORD.findall(s.lower()))))
    pairs = []
    for i, (m_a, doc_a, s_a, money_a, words_a) in enumerate(sentences):
        for m_b, doc_b, s_b, money_b, words_b in sentences[i + 1 :]:
            union = words_a | words_b
            if (
                doc_a != doc_b
                and money_a != money_b
                and union
                and len(words_a & words_b) / len(union) >= SAME_TOPIC_JACCARD
            ):
                pairs.append((m_a, s_a, m_b, s_b))
    return pairs


def money_conflict(passages: list[tuple[str, str]]) -> bool:
    return bool(money_conflicts([(f"C{i}", doc, text) for i, (doc, text) in enumerate(passages)]))
