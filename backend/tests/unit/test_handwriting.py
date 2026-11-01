"""Handwriting OCR without the 600 MB model: routing, confidence and the checks that protect users."""

from __future__ import annotations

import io
import time

import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.documents.extraction import LOW_QUALITY, OK, extract_pages
from app.documents.handwriting import LocalOcr, _reading_order, _words
from app.documents.ocr import OcrResult, OcrTimeoutError, OcrUnavailableError, OcrWord
from app.rag.uploaded import mark_unclear


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (400, 200), "white").save(out, "PNG")
    return out.getvalue()


BOX = np.array([[10, 10], [300, 10], [300, 50], [10, 50]], dtype=np.float32)


class _Found:
    def __init__(self, texts, scores) -> None:
        self.txts, self.scores = texts, scores
        self.boxes = np.array([BOX + [0, 60 * i] for i in range(len(texts))]) if texts else None


def _engine(found, monkeypatch, tokens=(("Ġmetformin", 0.9), ("Ġ500", 0.4))) -> LocalOcr:
    engine = LocalOcr("missing", 0.97)
    monkeypatch.setattr(engine, "_models", lambda: (lambda _image: found, None, None, None))
    monkeypatch.setattr(LocalOcr, "_read_line", staticmethod(lambda *_args: list(tokens)))
    return engine


def test_a_word_is_as_trustworthy_as_its_least_likely_token():
    words = _words([("Ġmet", 0.99), ("form", 0.2), ("in", 0.9), ("Ġ500", 0.8)])
    assert [w.text for w in words] == ["metformin", "500"]
    assert words[0].confidence == pytest.approx(20) and words[1].confidence == pytest.approx(80)


def test_clear_lines_stay_printed_and_unsure_lines_go_to_the_handwriting_model(monkeypatch):
    texts = ["Patient: Test", "Plan: Gold", "Date: today", "Doctor: Rao", "scrawl"]
    result = _engine(_Found(texts, [0.99, 0.99, 0.99, 0.99, 0.5]), monkeypatch).recognize(_png(), 30)
    assert result.text == "\n".join([*texts[:4], "metformin 500"]) and result.handwritten


def test_a_mostly_handwritten_page_ignores_the_printed_reader(monkeypatch):
    result = _engine(_Found(["confident misread", "scrawl"], [0.99, 0.5]), monkeypatch).recognize(_png(), 30)
    assert result.text == "metformin 500\nmetformin 500"


def test_printed_page_is_not_flagged_as_handwriting(monkeypatch):
    result = _engine(_Found(["Patient: Test"], [0.99]), monkeypatch).recognize(_png(), 30)
    assert not result.handwritten


def test_two_column_rows_read_left_to_right():
    box = lambda x, y: np.array([[x, y], [x + 100, y], [x + 100, y + 30], [x, y + 30]], dtype=np.float32)  # noqa: E731
    assert _reading_order([box(500, 12), box(10, 10), box(10, 80)]) == [1, 0, 2]


def test_blank_page_reads_nothing(monkeypatch):
    assert _engine(_Found([], []), monkeypatch).recognize(_png(), 30).words == []


def test_running_out_of_time_stops_the_page(monkeypatch):
    engine = _engine(_Found(["scrawl"], [0.5]), monkeypatch)
    monkeypatch.setattr("app.documents.handwriting.time.monotonic", iter([0.0, 100.0]).__next__)
    with pytest.raises(OcrTimeoutError):
        engine.recognize(_png(), 30)


def test_a_missing_model_is_reported_as_unavailable():
    engine = LocalOcr("no/such/folder", 0.97)
    assert not engine.available()
    with pytest.raises(OcrUnavailableError):
        engine.recognize(_png(), 30)


class _Scripted:
    name = "scripted"

    def __init__(self, result: OcrResult) -> None:
        self.result = result

    def available(self) -> bool:
        return True

    def recognize(self, png: bytes, timeout: float) -> OcrResult:
        return self.result


def _page(result: OcrResult):
    return extract_pages(_png(), "image/png", get_settings(), _Scripted(result), time.monotonic() + 30)[0]


def test_confident_handwriting_still_needs_a_check():
    page = _page(OcrResult([[OcrWord("metformin", 95)]], handwritten=True))
    assert page.status == OK and page.warning == "OCR_HANDWRITING_NEEDS_CHECK" and page.handwritten


def test_unclear_handwriting_is_low_quality():
    page = _page(OcrResult([[OcrWord("metformin", 30)]], handwritten=True))
    assert page.status == LOW_QUALITY and "metformin" in page.low_confidence_words


def test_unclear_words_are_marked_not_stated_as_fact():
    assert mark_unclear("Take Metformin 500 mg\ndaily", ["metformin"]) == "Take Metformin [?] 500 mg\ndaily"
