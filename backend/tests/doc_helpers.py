"""Builders for in-memory test files and an explicitly fake OCR engine. The fake proves how the
pipeline handles OCR output; it says nothing about real OCR quality (see the evaluation report)."""

from __future__ import annotations

import io

import pymupdf
from PIL import Image

from app.documents.ocr import OcrFailedError, OcrResult, OcrTimeoutError, OcrUnavailableError, OcrWord

BANNER = "SYNTHETIC SAMPLE - fictional data for the IHSA prototype"
PA_LINES = [
    BANNER,
    "Prior Authorization Request (synthetic form)",
    "Member number: SYN-M-000001",
    "Procedure code: SYN-PROC-MRI-LUMBAR",
    "Procedure description: Lumbar spine MRI without contrast",
    "Requested service date: 2026-11-04",
    "Ordering provider name: Dr. Jordan Example (fictional)",
    "Ordering provider NPI: 1234567890",
    "Facility name: Maplestone Imaging Center (fictional)",
    "Conservative therapy duration: 8 weeks of supervised physical therapy",
    "Supporting rationale: Persistent low back pain after conservative therapy (synthetic text).",
    "Request date: 2026-10-20",
]
REFERRAL_LINES = [
    BANNER,
    "Referral Letter (synthetic)",
    "Member number: SYN-M-000001",
    "Referring provider: Dr. Robin Example (fictional)",
    "Referral date: 2026-10-10",
    "Referred service: Lumbar spine MRI",
]


def text_pdf(*pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page(width=612, height=792)
        for i, line in enumerate(lines):
            page.insert_text((60, 72 + 20 * i), line, fontsize=11)
    return doc.tobytes(deflate=True)


def blank_pdf(pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=612, height=792)
    return doc.tobytes()


def image_pdf(png: bytes) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=png)
    return doc.tobytes(deflate=True, garbage=3)


def encrypted_pdf() -> bytes:
    doc = pymupdf.open(stream=text_pdf(PA_LINES), filetype="pdf")
    return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner-pw", user_pw="user-pw")


def png(width: int = 200, height: int = 100, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format=fmt)
    return buf.getvalue()


class FakeOcr:
    """Returns scripted text per call ("lines" with one confidence), or raises a scripted error."""

    name = "fake"

    def __init__(self, lines: list[str] | None = None, confidence: float = 92.0, error: str | None = None,
                 low_words: dict[str, float] | None = None) -> None:
        self.lines, self.confidence, self.error, self.low_words = lines or [], confidence, error, low_words or {}
        self.calls = 0

    def available(self) -> bool:
        return self.error != "unavailable"

    def recognize(self, image: bytes, timeout: float) -> OcrResult:
        self.calls += 1
        if self.error == "unavailable":
            raise OcrUnavailableError()
        if self.error == "timeout":
            raise OcrTimeoutError()
        if self.error == "failed":
            raise OcrFailedError()
        return OcrResult([
            [OcrWord(w, self.low_words.get(w, self.confidence)) for w in line.split()] for line in self.lines
        ])
