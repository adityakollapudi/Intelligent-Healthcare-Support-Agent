"""Embedding adapters. Documents and queries must use the same model (and its query prefix)."""

from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import Settings, get_settings
from app.rag.errors import AIServiceUnavailableError

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    model_id: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    """Local ONNX model via fastembed (CPU). The model downloads once into EMBEDDING_CACHE_DIR."""

    def __init__(self, model_name: str, dim: int, cache_dir: str) -> None:
        self.model_id = model_name
        self.dim = dim
        self._cache_dir = str(Path(cache_dir).resolve())
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding  # heavy import, deferred

                self._model = TextEmbedding(self.model_id, cache_dir=self._cache_dir)
        return self._model

    def _check(self, vectors: list[list[float]]) -> list[list[float]]:
        for vec in vectors:
            if len(vec) != self.dim:
                raise AIServiceUnavailableError(f"embedding dimension {len(vec)} != configured {self.dim}")
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._check([v.tolist() for v in self._load().embed(texts, batch_size=32)])
        except AIServiceUnavailableError:
            raise
        except Exception as exc:  # model load/download/runtime failures
            logger.error("embedding_failed", extra={"error_type": type(exc).__name__})
            raise AIServiceUnavailableError("embedding_failed") from None

    def embed_query(self, text: str) -> list[float]:
        try:
            # query_embed applies the model's retrieval query instruction (bge models).
            return self._check([v.tolist() for v in self._load().query_embed([text])])[0]
        except AIServiceUnavailableError:
            raise
        except Exception as exc:
            logger.error("embedding_failed", extra={"error_type": type(exc).__name__})
            raise AIServiceUnavailableError("embedding_failed") from None


_TOKEN = re.compile(r"[a-z0-9$]+")


class HashEmbedder:
    """TEST DOUBLE: deterministic hashed bag-of-words vectors. It captures word overlap only and
    says nothing about semantic retrieval quality. Allowed only with APP_ENV=test."""

    def __init__(self, dim: int = 384) -> None:
        self.model_id = f"hash-bow-{dim}"
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN.findall(text.lower()):
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim  # noqa: S324 - not security
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def build_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "hash":
        return HashEmbedder(settings.embedding_dim)
    return FastEmbedEmbedder(settings.embedding_model, settings.embedding_dim, settings.embedding_cache_dir)


@lru_cache
def get_embedder() -> Embedder:
    return build_embedder(get_settings())
