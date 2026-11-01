"""Handwriting OCR without the 600 MB model: routing, confidence and the checks that protect users."""

from __future__ import annotations

import io
import time

import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.documents.extraction import LOW_QUALITY, OK, extract_pages
from app.documents.handwriting import LocalOcr, _choose, _rows, _words
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
    texts = ["Patient: Test", "Plan: Gold", "Date: today", "Doctor: Rao", "scrawled line"]
    result = _engine(_Found(texts, [0.99, 0.99, 0.99, 0.99, 0.5]), monkeypatch).recognize(_png(), 30)
    assert result.text == "\n".join([*texts[:4], "metformin 500"]) and result.handwritten


def test_a_handwritten_page_is_read_by_both_and_keeps_the_better_line(monkeypatch):
    tokens = (("\u0120metformin", 0.99), ("\u0120daily", 0.99))
    engine = _engine(_Found(["metf0rmin daily", "scrawled line"], [0.98, 0.5]), monkeypatch, tokens)
    result = engine.recognize(_png(), 30)
    assert result.text == "metformin daily\nmetformin daily" and result.handwritten


def test_short_labels_and_numbers_stay_with_the_printed_reader():
    assert _choose("C/C:", 0.9, [("\u0120clc", 0.99)])[0].text == "C/C:"
    assert [w.text for w in _choose("21/10/2026", 0.9, [("\u01202", 0.99), ("(", 0.99)])] == ["21/10/2026"]


def test_certain_printed_text_is_not_flagged_by_a_garbled_second_reading():
    assert _choose("City Care Clinic", 1.0, [("\u0120Lawrence", 0.2)])[0].confidence == 100


def test_stray_quotes_from_the_handwriting_model_are_removed():
    tokens = [("\u0120'", 0.95), ("\u0120low", 0.95), ("\u0120back", 0.95), ("\u0120pain", 0.95)]
    assert [w.text for w in _choose("low back pain", 0.97, tokens)] == ["low", "back", "pain"]


def test_a_much_less_certain_reading_loses():
    tokens = [("\u0120something", 0.7), ("\u0120else", 0.7)]
    assert [w.text for w in _choose("Tab. Naproxen daily", 0.98, tokens)] == ["Tab.", "Naproxen", "daily"]


def test_words_the_readers_disagree_on_are_unclear_and_agreed_words_are_not():
    tokens = [("\u0120Tab", 0.8), (".", 0.3), ("\u0120parac", 0.7), ("tonid", 0.7)]
    words = _choose("Tab. Paracetamd", 0.98, tokens)
    assert {w.text: w.confidence < 60 for w in words} == {"Tab.": False, "Paracetamd": True}


def test_printed_page_is_not_flagged_as_handwriting(monkeypatch):
    result = _engine(_Found(["Patient: Test"], [0.99]), monkeypatch).recognize(_png(), 30)
    assert not result.handwritten


def test_two_column_rows_read_left_to_right():
    box = lambda x, y: np.array([[x, y], [x + 100, y], [x + 100, y + 30], [x, y + 30]], dtype=np.float32)  # noqa: E731
    assert _rows([box(500, 12), box(10, 10), box(10, 80)]) == [[1, 0], [2]]


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
