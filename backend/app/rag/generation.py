"""Answer generators behind one interface (ADR-12).

- AnthropicGenerator: Claude via the official SDK with a JSON-schema output (LLM_PROVIDER=anthropic).
- ExtractiveGenerator: no LLM. Quotes the best-matching evidence sentences with their markers
  (LLM_PROVIDER=extractive). Every answer it produces is labeled as such. It is an explicit mode,
  never a silent fallback when the LLM fails.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.core.config import Settings, get_settings
from app.rag.errors import AIServiceUnavailableError
from app.rag.prompts import OUTPUT_SCHEMA, SYSTEM_PROMPT, TOOL_RULES, EvidenceItem, build_user_message

logger = logging.getLogger(__name__)


@dataclass
class Generation:
    answer_text: str
    citations_used: list[str]
    evidence_sufficient: bool
    conflict_detected: bool = False
    conflict_markers: list[str] = field(default_factory=list)
    disclaimer: str | None = None


class Generator(Protocol):
    name: str

    def generate(self, question: str, evidence: list[EvidenceItem], history: list[tuple[str, str]]) -> Generation: ...


def parse_generation(raw: str) -> Generation:
    """Validates model JSON against the expected shape; raises ValueError when unusable."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    answer = data.get("answer_text")
    used = data.get("citations_used")
    if not isinstance(answer, str) or not isinstance(used, list) or not all(isinstance(m, str) for m in used):
        raise ValueError("bad answer_text/citations_used")
    if not isinstance(data.get("evidence_sufficient"), bool):
        raise ValueError("bad evidence_sufficient")
    markers = data.get("conflict_markers") or []
    return Generation(
        answer_text=answer.strip(),
        citations_used=used,
        evidence_sufficient=data["evidence_sufficient"],
        conflict_detected=bool(data.get("conflict_detected")),
        conflict_markers=[m for m in markers if isinstance(m, str)],
    )


class AnthropicGenerator:
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self._settings = settings

    def generate(self, question: str, evidence: list[EvidenceItem], history: list[tuple[str, str]]) -> Generation:
        messages = [{"role": "user", "content": build_user_message(question, evidence, history)}]
        return self._final(self._call(SYSTEM_PROMPT, messages, tools=None))

    def generate_with_tools(self, question: str, evidence: list[EvidenceItem], history: list[tuple[str, str]],
                            executor) -> Generation:
        """Native tool use. Each requested call is executed only through `executor` (allowlist, schema,
        permission, audit); the model sees the validated result or a safe error. The loop is bounded:
        after the executor's call budget is spent, further calls get CALL_LIMIT_REACHED results."""
        from app.tools.registry import anthropic_tool_definitions

        tools = anthropic_tool_definitions()
        messages: list[dict] = [{"role": "user", "content": build_user_message(question, evidence, history)}]
        for _ in range(executor.max_calls + 2):
            response = self._call(SYSTEM_PROMPT + TOOL_RULES, messages, tools=tools)
            if response.stop_reason != "tool_use":
                return self._final(response)
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                outcome = executor.execute(block.name, block.input)
                payload = outcome.data if outcome.data is not None else {"status": outcome.status,
                                                                          "error": outcome.error}
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps({"status": outcome.status, "result": payload}),
                                "is_error": outcome.status not in ("SUCCEEDED", "CONFIRMATION_REQUIRED")})
            messages.append({"role": "user", "content": results})
        raise AIServiceUnavailableError("llm_tool_loop_exhausted")

    def _call(self, system: str, messages: list[dict], tools: list[dict] | None):
        a = self._anthropic
        kwargs = {"tools": tools} if tools else {}
        try:
            response = self._client.messages.create(
                model=self._settings.llm_model,
                max_tokens=self._settings.llm_max_output_tokens,
                system=system,
                messages=messages,
                output_config={
                    "effort": self._settings.llm_effort,
                    "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
                },
                **kwargs,
            )
        except a.APITimeoutError:
            raise AIServiceUnavailableError("llm_timeout") from None
        except a.RateLimitError:
            raise AIServiceUnavailableError("llm_rate_limited") from None
        except a.APIConnectionError:
            raise AIServiceUnavailableError("llm_connection") from None
        except a.APIStatusError as exc:
            logger.error("llm_status_error", extra={"status": exc.status_code})
            raise AIServiceUnavailableError(f"llm_status_{exc.status_code}") from None

        if response.stop_reason == "refusal":
            raise AIServiceUnavailableError("llm_refusal")
        if response.stop_reason == "max_tokens":
            raise AIServiceUnavailableError("llm_truncated")
        return response

    @staticmethod
    def _final(response) -> Generation:
        raw = "".join(block.text for block in response.content if block.type == "text")
        try:
            return parse_generation(raw)
        except (ValueError, json.JSONDecodeError):
            raise AIServiceUnavailableError("llm_invalid_output") from None


_STOP = set(
    """a an the and or of to in on for with is are was were be been it its this that these those
what which who how when where why do does did can could should would will i my me we our you your they
their there here about from by as at if any all not no yes much many more most than then so get got have
has had please tell know need want plan""".split()
)
_WORDS = re.compile(r"[a-z0-9$]+")
_QUANTITY = re.compile(
    r"\bhow (many|much|long|soon|fast|quickly|early|far)\b|\bwhat is the (deadline|limit|copay)\b", re.I
)
_DIGIT = re.compile(r"\d")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _content_words(text: str) -> set[str]:
    words = set()
    for w in _WORDS.findall(text.lower()):
        if w in _STOP or len(w) < 3:
            continue
        words.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)  # crude plural folding
    return words


class ExtractiveGenerator:
    """Deterministic, LLM-free answers: quotes the evidence sentences most similar to the question.

    Safety rule (there is no model to judge relevance): if no evidence sentence is similar enough
    to the question it reports insufficient evidence instead of quoting loosely related text. The
    cutoff is calibrated on the evaluation set; lexical/semantic similarity cannot always tell a
    related passage from an answering one, which is the main limitation of this mode."""

    name = "extractive"
    DISCLAIMER = (
        "This answer quotes the source documents directly; it was not written by an AI language model "
        "(LLM_PROVIDER=extractive)."
    )
    MIN_SENTENCE_SIMILARITY = 0.70  # trade-off chosen from measured distributions (eval report §4)
    KEEP_WITHIN = 0.10
    NUMBER_BONUS = 0.04

    def __init__(self, embedder=None) -> None:
        self._embedder = embedder  # optional: without it, sentences are ranked by word overlap

    def generate(self, question: str, evidence: list[EvidenceItem], history: list[tuple[str, str]]) -> Generation:
        no = Generation("", [], evidence_sufficient=False, disclaimer=self.DISCLAIMER)
        q_words = _content_words(question)

        sentences: list[tuple[int, int, str, str]] = []
        for rank, item in enumerate(evidence):
            for pos, sentence in enumerate(_SENTENCE.split(item.candidate.content)):
                sentence = sentence.strip(" -*>\t")
                if len(sentence) >= 15 and not sentence.upper().startswith("SYNTHETIC DEMONSTRATION"):
                    sentences.append((rank, pos, sentence, item.marker))
        if not sentences:
            return no

        overlaps = [len(q_words & _content_words(s)) for _, _, s, _ in sentences]
        if self._embedder is not None:
            q = self._embedder.embed_query(question)
            vecs = self._embedder.embed_documents([s for _, _, s, _ in sentences])
            sims = [sum(a * b for a, b in zip(q, v, strict=True)) for v in vecs]
            # "How many/much/long/soon..." questions are answered by sentences that state a number.
            wants_number = bool(_QUANTITY.search(question))
            scores = [
                sim + 0.02 * ov + (self.NUMBER_BONUS if wants_number and _DIGIT.search(s) else 0.0)
                for sim, ov, (_, _, s, _) in zip(sims, overlaps, sentences, strict=True)
            ]
            best = max(sims)
            if best < self.MIN_SENTENCE_SIMILARITY:
                return no
            ranked = sorted(range(len(sentences)), key=lambda i: -scores[i])
            floor = best - self.KEEP_WITHIN
            chosen = [i for i in ranked[:3] if sims[i] >= floor and sims[i] >= self.MIN_SENTENCE_SIMILARITY]
        else:
            ranked = sorted(range(len(sentences)), key=lambda i: -(overlaps[i] - 0.15 * sentences[i][0]))
            chosen = [i for i in ranked[:3] if overlaps[i] > 0]
        if not chosen:
            return no

        picked = sorted((sentences[i] for i in chosen), key=lambda s: (s[0], s[1]))
        lines = [f"- {sentence} [{marker}]" for _, _, sentence, marker in picked]
        text = "Here is what the available documents say:\n" + "\n".join(lines)
        used = sorted({marker for *_, marker in picked}, key=lambda m: int(m[1:]))
        return Generation(text, used, evidence_sufficient=True, disclaimer=self.DISCLAIMER)


def build_generator(settings: Settings) -> Generator:
    if settings.llm_provider == "anthropic":
        return AnthropicGenerator(settings)
    from app.rag.embeddings import get_embedder

    # The sentence-similarity cutoff is calibrated for the real model; the hash test double is not
    # semantic, so with it sentences are ranked by word overlap instead.
    return ExtractiveGenerator(get_embedder() if settings.embedding_provider == "fastembed" else None)


@lru_cache
def get_generator() -> Generator:
    return build_generator(get_settings())
