"""Reads printed and handwritten pages on this machine, so no page leaves it (doc 07 §5.2 step 3).

RapidOCR (PP-OCR, Apache-2.0) finds the text lines and reads the printed ones. A line it isn't sure of
goes to TrOCR (microsoft/trocr-base-handwritten, MIT), run through ONNX Runtime. TrOCR reads one line
at a time and reports how likely each token was; a word's confidence is its least likely token, so a
guessed medicine name can't hide behind the words around it."""

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
_HANDWRITTEN_PAGE_SHARE = 0.25  # this share of unsure lines means the whole page is treated as handwriting


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


def _reading_order(boxes: list[np.ndarray]) -> list[int]:
    """Top to bottom, then left to right among lines sitting on the same row (such as two-column headers)."""
    rows: list[list[int]] = []
    for index in sorted(range(len(boxes)), key=lambda i: boxes[i][:, 1].mean()):
        height = boxes[index][:, 1].max() - boxes[index][:, 1].min()
        if rows and abs(boxes[index][:, 1].mean() - boxes[rows[-1][0]][:, 1].mean()) < height / 2:
            rows[-1].append(index)
        else:
            rows.append([index])
    return [i for row in rows for i in sorted(row, key=lambda i: boxes[i][:, 0].min())]


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

        lines: list[list[OcrWord]] = []
        handwritten = False
        # RapidOCR can be confident and wrong on handwriting, so a mostly handwritten page skips it entirely.
        unsure = sum(float(s) < self._printed_min_score for s in found.scores)
        all_handwritten = unsure >= len(found.scores) * _HANDWRITTEN_PAGE_SHARE
        for index in _reading_order(list(found.boxes)):
            score = float(found.scores[index])
            if score >= self._printed_min_score and not all_handwritten:
                lines.append([OcrWord(w, score * 100) for w in found.txts[index].split()])
                continue
            if time.monotonic() > give_up:
                raise OcrTimeoutError()
            handwritten = True
            tokens = self._read_line(_crop(image, found.boxes[index]), encoder, decoder, tokenizer)
            lines.append(_words(tokens))
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
