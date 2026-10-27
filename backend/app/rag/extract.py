"""Text extraction for trusted knowledge sources: Markdown, plain text and text-layer PDFs.
OCR is out of scope here (Phase 6); a PDF without a text layer is rejected."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.rag.errors import IngestionError

SOURCE_TYPES = {".md": "markdown", ".txt": "text", ".pdf": "pdf"}
MAX_SOURCE_BYTES = 5 * 1024 * 1024
MIN_TEXT_CHARS = 40


@dataclass(frozen=True)
class Page:
    text: str
    number: int | None  # 1-based for PDFs, None for text formats


def source_type_for(path: Path) -> str:
    try:
        return SOURCE_TYPES[path.suffix.lower()]
    except KeyError:
        raise IngestionError("UNSUPPORTED_FILE_TYPE", path.suffix) from None


def extract(path: Path) -> list[Page]:
    kind = source_type_for(path)
    data = path.read_bytes()
    if len(data) > MAX_SOURCE_BYTES:
        raise IngestionError("FILE_TOO_LARGE")
    if kind == "pdf":
        pages = _extract_pdf(data)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise IngestionError("NOT_UTF8") from None
        pages = [Page(text=text, number=None)]
    # Whitespace is collapsed first so the threshold doesn't depend on line endings (CRLF vs LF).
    if sum(len(" ".join(p.text.split())) for p in pages) < MIN_TEXT_CHARS:
        raise IngestionError("NO_TEXT_LAYER" if kind == "pdf" else "EMPTY_DOCUMENT")
    return pages


def _extract_pdf(data: bytes) -> list[Page]:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:  # corrupt or not a PDF
        raise IngestionError("PDF_PARSE_ERROR") from None
    with doc:
        if doc.needs_pass or doc.is_encrypted:
            raise IngestionError("PDF_ENCRYPTED")
        return [Page(text=page.get_text("text"), number=i + 1) for i, page in enumerate(doc)]
