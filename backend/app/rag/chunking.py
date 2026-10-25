"""Heading-aware chunking that keeps paragraphs intact and records where each chunk came from.

Sizes are in words (a model-agnostic proxy for tokens; bge-small allows 512 tokens, and ~160 words
stays well inside that). Values are provisional and set via RAG_CHUNK_WORDS / RAG_CHUNK_OVERLAP_WORDS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.extract import Page

CHUNKER_VERSION = "md-sections-pages-v2"


def chunking_fingerprint(chunk_words: int, overlap_words: int) -> str:
    return f"{CHUNKER_VERSION};words={chunk_words};overlap={overlap_words}"


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_SPACES = re.compile(r"[ \t ]+")


@dataclass(frozen=True)
class Chunk:
    content: str
    section_heading: str | None
    page_start: int | None
    page_end: int | None
    char_start: int
    char_end: int
    word_count: int


@dataclass
class _Para:
    text: str
    heading: str | None
    page: int | None
    start: int
    end: int


def normalize(text: str) -> str:
    """Collapse runs of spaces and blank lines without merging paragraphs."""
    lines = [_SPACES.sub(" ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _paragraphs(pages: list[Page], markdown: bool) -> list[_Para]:
    paras: list[_Para] = []
    path: list[str] = []
    offset = 0
    for page in pages:
        text = normalize(page.text)
        for block in text.split("\n\n"):
            start = offset
            offset += len(block) + 2
            block = block.strip()
            if not block:
                continue
            match = _HEADING.match(block.split("\n", 1)[0]) if markdown else None
            if match:
                level = len(match.group(1))
                path = path[: level - 1] + [match.group(2)]
                rest = block.split("\n", 1)[1].strip() if "\n" in block else ""
                if not rest:
                    continue
                block = rest
            paras.append(_Para(block, " > ".join(path[1:] or path) or None, page.number, start, start + len(block)))
    return paras


def chunk_pages(pages: list[Page], *, markdown: bool, chunk_words: int, overlap_words: int) -> list[Chunk]:
    """Packs whole paragraphs into chunks of <= chunk_words; a new section starts a new chunk.
    Oversized paragraphs are split on sentence boundaries; overlap repeats trailing sentences."""
    chunks: list[Chunk] = []
    current: list[_Para] = []

    def words(items: list[_Para]) -> int:
        return sum(len(p.text.split()) for p in items)

    def flush() -> None:
        if not current:
            return
        text = "\n\n".join(p.text for p in current)
        pages_ = [p.page for p in current if p.page is not None]
        chunks.append(
            Chunk(
                text,
                current[0].heading,
                min(pages_) if pages_ else None,
                max(pages_) if pages_ else None,
                current[0].start,
                max(current[-1].end, current[0].start + 1),
                len(text.split()),
            )
        )

    for para in _split_long(_paragraphs(pages, markdown), chunk_words):
        # A new section or a new PDF page starts a new chunk, so citations point to one place.
        new_section = current and (para.heading != current[-1].heading or para.page != current[-1].page)
        para_words = len(para.text.split())
        if current and (new_section or words(current) + para_words > chunk_words):
            flush()
            tail = _overlap_tail(current, overlap_words) if not new_section else []
            current = tail if words(tail) + para_words <= chunk_words else []
        current.append(para)
    flush()
    return chunks


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _split_long(paras: list[_Para], limit: int) -> list[_Para]:
    out: list[_Para] = []
    for p in paras:
        if len(p.text.split()) <= limit:
            out.append(p)
            continue
        buf: list[str] = []
        for sentence in _SENTENCE.split(p.text):
            if buf and len(" ".join(buf + [sentence]).split()) > limit:
                out.append(_Para(" ".join(buf), p.heading, p.page, p.start, p.end))
                buf = []
            buf.append(sentence)
        if buf:
            out.append(_Para(" ".join(buf), p.heading, p.page, p.start, p.end))
    return out


def _overlap_tail(paras: list[_Para], overlap_words: int) -> list[_Para]:
    if overlap_words <= 0 or not paras:
        return []
    last = paras[-1]
    sentences = _SENTENCE.split(last.text)
    tail: list[str] = []
    while sentences and len(" ".join(tail).split()) < overlap_words:
        tail.insert(0, sentences.pop())
    if not tail or len(tail) == len(_SENTENCE.split(last.text)):
        return []  # the whole paragraph would repeat; skip overlap
    return [_Para(" ".join(tail), last.heading, last.page, last.end - len(" ".join(tail)), last.end)]
