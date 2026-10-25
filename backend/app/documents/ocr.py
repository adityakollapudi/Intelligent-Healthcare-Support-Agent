"""OCR behind one interface (doc 07 §5.2 step 3).

TesseractOcr runs the Tesseract CLI as a subprocess with an argument list (no shell), a per-page
timeout and an allowlisted language string, and returns word-level confidences from its TSV output.
If the executable is missing, `available()` is False and callers report the page as unreadable: OCR
failure is never treated as evidence that a field is absent."""

from __future__ import annotations

import csv
import io
import logging
import shutil
import subprocess  # noqa: S404 - fixed executable, argument list, no shell
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class OcrUnavailableError(Exception):
    """No OCR engine is configured or installed."""


class OcrFailedError(Exception):
    """The engine ran but did not produce a result (crash, bad output)."""


class OcrTimeoutError(Exception):
    """The engine exceeded its time limit."""


@dataclass
class OcrWord:
    text: str
    confidence: float  # 0–100 as reported by the engine


@dataclass
class OcrResult:
    lines: list[list[OcrWord]] = field(default_factory=list)

    @property
    def words(self) -> list[OcrWord]:
        return [w for line in self.lines for w in line]

    @property
    def text(self) -> str:
        return "\n".join(" ".join(w.text for w in line) for line in self.lines)

    @property
    def mean_confidence(self) -> float | None:
        words = self.words
        return sum(w.confidence for w in words) / len(words) if words else None


class OcrEngine(Protocol):
    name: str

    def available(self) -> bool: ...
    def recognize(self, png: bytes, timeout: float) -> OcrResult: ...


class DisabledOcr:
    name = "disabled"

    def available(self) -> bool:
        return False

    def recognize(self, png: bytes, timeout: float) -> OcrResult:
        raise OcrUnavailableError("OCR is disabled (OCR_ENGINE=disabled)")


class TesseractOcr:
    name = "tesseract"

    def __init__(self, executable: str, languages: str) -> None:
        self._configured = executable
        self._languages = languages  # validated by Settings: ^[a-z]{3}(\+[a-z]{3})*$
        self._resolved: str | None = shutil.which(executable)

    def available(self) -> bool:
        return self._resolved is not None

    def recognize(self, png: bytes, timeout: float) -> OcrResult:
        if self._resolved is None:
            raise OcrUnavailableError(f"Tesseract executable not found: {self._configured}")
        try:
            proc = subprocess.run(  # noqa: S603 - resolved executable, constant arguments
                [self._resolved, "stdin", "stdout", "-l", self._languages, "--psm", "6", "tsv"],
                input=png,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise OcrTimeoutError() from None
        except OSError as exc:
            raise OcrFailedError(type(exc).__name__) from None
        if proc.returncode != 0:
            logger.error("ocr_failed", extra={"returncode": proc.returncode})
            raise OcrFailedError(f"exit {proc.returncode}")
        return parse_tsv(proc.stdout.decode("utf-8", errors="replace"))


def parse_tsv(tsv: str) -> OcrResult:
    """Groups Tesseract TSV word rows (level 5) into lines; rows without text are skipped."""
    lines: dict[tuple[int, int, int], list[OcrWord]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row.get("level") != "5":
            continue
        text = (row.get("text") or "").strip()
        try:
            conf = float(row.get("conf") or -1)
        except ValueError:
            continue
        if not text or conf < 0:
            continue
        key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
        lines.setdefault(key, []).append(OcrWord(text, conf))
    return OcrResult([lines[k] for k in sorted(lines)])


def build_ocr(settings: Settings) -> OcrEngine:
    if settings.ocr_engine == "disabled":
        return DisabledOcr()
    return TesseractOcr(settings.ocr_tesseract_path, settings.ocr_languages)


@lru_cache
def get_ocr_engine() -> OcrEngine:
    return build_ocr(get_settings())
