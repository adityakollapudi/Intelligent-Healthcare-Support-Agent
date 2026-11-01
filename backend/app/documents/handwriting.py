"""Reads printed and handwritten pages on this machine, so no page leaves it (doc 07 §5.2 step 3).

RapidOCR (PP-OCR, Apache-2.0) finds the text lines and reads them. On a page with handwriting, TrOCR
(microsoft/trocr-base-handwritten, MIT, run through ONNX Runtime) reads each line as well. RapidOCR
does better on neat writing, labels and numbers, and TrOCR on cursive, so each line keeps whichever
reading is more credible. A word the two readers disagree on is low confidence even if one of them
was sure, so a misread medicine name gets flagged rather than passing as fact."""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image

from app.documents.ocr import OcrFailedError, OcrResult, OcrTimeoutError, OcrUnavailableError, OcrWord

logger = logging.getLogger(__name__)

_ENCODER = "onnx/encoder_model.onnx"  # the quantized encoder raised character errors from 6% to 41% in our test
_DECODER = "onnx/decoder_model_merged_quantized.onnx"
_TOKENIZER = "tokenizer.json"
_INPUT_SIZE = 384
_END_TOKEN = 2  # TrOCR uses </s> both to start and to end a line
_MAX_TOKENS = 48
_WORD_START = "Ġ"
_LINE_PADDING = 6
_HANDWRITTEN_PAGE_SHARE = 0.25  # this share of unsure lines means the page has handwriting
_ROW_GAP = 1.5  # pieces on one row closer than this many line heights are one line
_MIN_TROCR_CHARS = 8  # TrOCR squashes each crop to a square, which ruins short labels
_MAX_TROCR_DIGIT_SHARE = 0.3  # and it reads dates and identifiers poorly
_TROCR_MARGIN = 0.05  # RapidOCR's scores run high, so TrOCR wins when it's within this of them
_DISAGREED_CONFIDENCE = 55.0  # below the default OCR_MIN_WORD_CONFIDENCE
_CERTAIN_SCORE = 0.995  # printed text scores this high, and TrOCR's garbled reading of it proves nothing
_STRAY_MARKS = {"'", '"'}  # TrOCR adds these around words that have none


def _load_image(png: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(png)) as image:
            return np.asarray(image.convert("RGB"))
    except Exception:  # noqa: BLE001 - any decoder failure means the page can't be read
        raise OcrFailedError("image decode") from None


def _pixels(line: np.ndarray) -> np.ndarray:
    resized = Image.fromarray(line).resize((_INPUT_SIZE, _INPUT_SIZE), Image.Resampling.BILINEAR)
    values = np.asarray(resized, dtype=np.float32) / 255.0
    return ((values - 0.5) / 0.5).transpose(2, 0, 1)[None]


def _crop(image: np.ndarray, box: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    left, top = np.maximum(box.min(axis=0).astype(int) - _LINE_PADDING, 0)
    right = min(int(box[:, 0].max()) + _LINE_PADDING, width)
    bottom = min(int(box[:, 1].max()) + _LINE_PADDING, height)
    return image[top:bottom, left:right]


def _rows(boxes: list[np.ndarray]) -> list[list[int]]:
    """Top to bottom, then left to right among lines sitting on the same row."""
    rows: list[list[int]] = []
    for index in sorted(range(len(boxes)), key=lambda i: boxes[i][:, 1].mean()):
        height = boxes[index][:, 1].max() - boxes[index][:, 1].min()
        if rows and abs(boxes[index][:, 1].mean() - boxes[rows[-1][0]][:, 1].mean()) < height / 2:
            rows[-1].append(index)
        else:
            rows.append([index])
    return [sorted(row, key=lambda i: boxes[i][:, 0].min()) for row in rows]


def _words(tokens: list[tuple[str, float]]) -> list[OcrWord]:
    """Joins tokens into words; a word is as trustworthy as its least likely token."""
    words: list[OcrWord] = []
    for token, probability in tokens:
        starts = token.startswith(_WORD_START) or not words
        text = token.removeprefix(_WORD_START)
        if starts:
            words.append(OcrWord(text, probability * 100))
        else:
            words[-1].text += text
            words[-1].confidence = min(words[-1].confidence, probability * 100)
    return [w for w in words if w.text]


def _key(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalnum())


def _choose(printed: str, score: float, tokens: list[tuple[str, float]]) -> list[OcrWord]:
    """Picks RapidOCR's or TrOCR's reading of one line and sets confidence from whether they agree."""
    first = [OcrWord(w, score * 100) for w in printed.split()]
    second = _words(tokens)
    mean = sum(p for _, p in tokens) / len(tokens) if tokens else 0.0
    digits = sum(c.isdigit() for c in printed) / max(len(printed), 1)
    keep_first = len(printed) < _MIN_TROCR_CHARS or digits >= _MAX_TROCR_DIGIT_SHARE or mean < score - _TROCR_MARGIN
    chosen, other = (first, second) if keep_first else (second, first)
    others = {_key(w.text) for w in other}
    if keep_first and score >= _CERTAIN_SCORE:
        return chosen
    chosen = [w for w in chosen if w.text not in _STRAY_MARKS]
    for word in chosen:
        key = _key(word.text)
        if key in others:
            word.confidence = max(word.confidence, score * 100)
        elif key:
            word.confidence = min(word.confidence, _DISAGREED_CONFIDENCE)
    return chosen


class LocalOcr:
    name = "local"

    def __init__(self, model_dir: str, printed_min_score: float) -> None:
        self._dir = Path(model_dir)
        self._printed_min_score = printed_min_score
        self._lock = Lock()
        self._loaded: tuple | None = None

    def available(self) -> bool:
        return all((self._dir / name).is_file() for name in (_ENCODER, _DECODER, _TOKENIZER))

    def _models(self) -> tuple:
        with self._lock:
            if self._loaded is None:
                if not self.available():
                    raise OcrUnavailableError(f"Handwriting model not found in {self._dir}")
                import onnxruntime
                from rapidocr import RapidOCR
                from tokenizers import Tokenizer

                options = onnxruntime.SessionOptions()
                options.log_severity_level = 3
                providers = ["CPUExecutionProvider"]
                self._loaded = (
                    RapidOCR(params={"Global.log_level": "error"}),
                    onnxruntime.InferenceSession(self._dir / _ENCODER, options, providers=providers),
                    onnxruntime.InferenceSession(self._dir / _DECODER, options, providers=providers),
                    Tokenizer.from_file(str(self._dir / _TOKENIZER)),
                )
            return self._loaded

    def recognize(self, png: bytes, timeout: float) -> OcrResult:
        give_up = time.monotonic() + timeout
        reader, encoder, decoder, tokenizer = self._models()
        image = _load_image(png)
        try:
            found = reader(image[:, :, ::-1])  # RapidOCR expects BGR
        except Exception as exc:  # noqa: BLE001 - engine crash is a page failure, not a job crash
            logger.error("ocr_failed", extra={"error_type": type(exc).__name__})
            raise OcrFailedError(type(exc).__name__) from None
        if found.boxes is None or found.txts is None or found.scores is None:
            return OcrResult()

        scores = [float(score) for score in found.scores]
        boxes = list(found.boxes)
        unsure = sum(score < self._printed_min_score for score in scores)
        handwritten = unsure >= len(scores) * _HANDWRITTEN_PAGE_SHARE
        lines: list[list[OcrWord]] = []
        for row in _rows(boxes):
            line: list[OcrWord] = []
            previous = None
            for index in row:
                box = boxes[index]
                height = box[:, 1].max() - box[:, 1].min()
                if previous is not None and box[:, 0].min() - previous > height * _ROW_GAP:
                    lines.append(line)
                    line = []
                previous = box[:, 0].max()
                printed = found.txts[index].replace("\uff1a", ":")
                if scores[index] >= self._printed_min_score and not handwritten:
                    line += [OcrWord(w, scores[index] * 100) for w in printed.split()]
                    continue
                if time.monotonic() > give_up:
                    raise OcrTimeoutError()
                handwritten = True
                tokens = self._read_line(_crop(image, box), encoder, decoder, tokenizer)
                line += _choose(printed, scores[index], tokens)
            lines.append(line)
        return OcrResult([line for line in lines if line], handwritten=handwritten)

    @staticmethod
    def _read_line(line: np.ndarray, encoder, decoder, tokenizer) -> list[tuple[str, float]]:
        hidden = encoder.run(None, {"pixel_values": _pixels(line)})[0]
        cache_inputs = [i for i in decoder.get_inputs() if i.name.startswith("past_key_values")]
        cache_outputs = [o.name for o in decoder.get_outputs() if o.name.startswith("present")]
        past = {i.name: np.zeros((1, i.shape[1] if isinstance(i.shape[1], int) else 12, 0,
                                  i.shape[3] if isinstance(i.shape[3], int) else 64), np.float32)
                for i in cache_inputs}
        next_id, cached = _END_TOKEN, False
        tokens: list[tuple[str, float]] = []
        for _ in range(_MAX_TOKENS):
            outputs = decoder.run(None, {
                "input_ids": np.array([[next_id]], np.int64),
                "encoder_hidden_states": hidden,
                "use_cache_branch": np.array([cached]),
                **past,
            })
            logits = outputs[0][0, -1]
            probabilities = np.exp(logits - logits.max())
            probabilities /= probabilities.sum()
            next_id = int(logits.argmax())
            if next_id == _END_TOKEN:
                break
            token = tokenizer.id_to_token(next_id) or ""
            tokens.append((token, float(probabilities[next_id])))
            for name, value in zip(cache_outputs, outputs[1:], strict=True):
                key = name.replace("present", "past_key_values")
                if cached and ".encoder." in key:
                    continue  # the encoder half of the cache only comes from the first step
                past[key] = value
            cached = True
        return tokens
