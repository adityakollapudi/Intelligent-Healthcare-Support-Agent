"""Page-level text extraction (doc 07 §5.2 steps 2–3).

PDF pages use the PyMuPDF text layer. Only pages with fewer than OCR_MIN_TEXT_CHARS_PER_PAGE
characters, and images, go to OCR (rendered at OCR_DPI). Every page reports how it was read and
whether it was fully readable; extracted text is held in memory for this job only (never persisted)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import pymupdf

from app.core.config import Settings
from app.documents.ocr import OcrEngine, OcrFailedError, OcrTimeoutError, OcrUnavailableError

# Page statuses. READABLE_STATUSES are pages whose full content the pipeline could examine.
OK, EMPTY, PARTIAL, LOW_QUALITY, UNREADABLE = "OK", "EMPTY", "PARTIAL", "LOW_QUALITY", "UNREADABLE"
READABLE_STATUSES = {OK, EMPTY}
_WS = re.compile(r"[ \t ]+")


class JobTimeoutError(Exception):
    pass


class PdfParseError(Exception):
    pass


@dataclass
class PageText:
    page_number: int  # 1-based
    text: str
    method: str | None  # TEXT_LAYER | OCR | None (nothing could be read)
    status: str
    warning: str | None = None
    ocr_confidence: float | None = None
    # Words OCR read below OCR_MIN_WORD_CONFIDENCE, with their confidence (lower-cased keys).
    low_confidence_words: dict[str, float] = field(default_factory=dict)
    word_confidence: dict[str, float] = field(default_factory=dict)

    @property
    def readable(self) -> bool:
        return self.status in READABLE_STATUSES

    def detail(self) -> dict:
        """Metadata safe to persist (no document text)."""
        return {
            "page_number": self.page_number,
            "method": self.method,
            "status": self.status,
            "char_count": len(self.text),
            "ocr_confidence": round(self.ocr_confidence, 1) if self.ocr_confidence is not None else None,
            "warning": self.warning,
        }


def normalize(text: str) -> str:
    """Collapse runs of spaces and blank lines; keep line breaks (labels sit at line starts)."""
    lines = [_WS.sub(" ", line).strip() for line in text.replace("\r", "\n").split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def extract_pages(data: bytes, mime_type: str, settings: Settings, ocr: OcrEngine, deadline: float) -> list[PageText]:
    if mime_type == "application/pdf":
        return _pdf_pages(data, settings, ocr, deadline)
    return [_ocr_page(1, data, "", settings, ocr, deadline)]


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise JobTimeoutError()
    return left


def _pdf_pages(data: bytes, settings: Settings, ocr: OcrEngine, deadline: float) -> list[PageText]:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001
        raise PdfParseError() from None
    pages: list[PageText] = []
    with doc:
        for index, page in enumerate(doc, start=1):
            _remaining(deadline)
            try:
                native = normalize(page.get_text("text"))
            except Exception:  # noqa: BLE001
                pages.append(PageText(index, "", None, UNREADABLE, "PAGE_PARSE_ERROR"))
                continue
            if len(native) >= settings.ocr_min_text_chars_per_page:
                pages.append(PageText(index, native, "TEXT_LAYER", OK))
                continue
            png = page.get_pixmap(dpi=settings.ocr_dpi).tobytes("png")
            pages.append(_ocr_page(index, png, native, settings, ocr, deadline))
    return pages


def _ocr_page(number: int, image: bytes, native: str, settings: Settings, ocr: OcrEngine, deadline: float) -> PageText:
    fallback = (native, "TEXT_LAYER", PARTIAL) if native else ("", None, UNREADABLE)
    try:
        result = ocr.recognize(image, timeout=min(settings.ocr_page_timeout_seconds, _remaining(deadline)))
    except OcrUnavailableError:
        return PageText(number, *fallback, warning="OCR_UNAVAILABLE")
    except OcrTimeoutError:
        _remaining(deadline)  # the whole job ran out of time → job TIMEOUT, not a page warning
        return PageText(number, *fallback, warning="OCR_TIMEOUT")
    except OcrFailedError:
        return PageText(number, *fallback, warning="OCR_FAILED")

    text = normalize(result.text)
    if not result.words:
        if native:
            return PageText(number, native, "TEXT_LAYER", PARTIAL, warning="OCR_NO_TEXT")
        return PageText(number, "", "OCR", EMPTY, warning="PAGE_EMPTY")
    words = {w.text.lower(): w.confidence for w in result.words}
    low = {t: c for t, c in words.items() if c < settings.ocr_min_word_confidence}
    mean = result.mean_confidence or 0.0
    status = OK if mean >= settings.ocr_min_word_confidence else LOW_QUALITY
    return PageText(
        number,
        text,
        "OCR",
        status,
        warning=None if status == OK else "OCR_LOW_CONFIDENCE",
        ocr_confidence=mean,
        low_confidence_words=low,
        word_confidence=words,
    )
