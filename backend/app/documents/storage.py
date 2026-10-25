"""Private file storage behind a small interface (ADR-09).

Keys are generated here (`uploads/{uuid}`) and validated on every access, so no user input ever
becomes part of a path. Files live outside any publicly served directory and are never returned by
URL: the API exposes metadata and extracted fields only (doc 07 §5.5)."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.core.config import get_settings

_KEY = re.compile(r"^uploads/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class StorageError(Exception):
    """Storage failure; the message is internal (never shown to users)."""


class FileStorage(Protocol):
    def new_key(self) -> str: ...
    def save(self, key: str, data: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalFileStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def new_key(self) -> str:
        return f"uploads/{uuid4()}"

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise StorageError("invalid storage key")
        path = (self.root / key).resolve()
        if self.root not in path.parents:  # defense in depth; the regex already forbids traversal
            raise StorageError("storage key escapes the storage root")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".partial")
        try:
            # O_EXCL: never overwrite an existing file (keys are random UUIDs, so a clash is a bug).
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, path)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise StorageError(type(exc).__name__) from None

    def read(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except OSError as exc:
            raise StorageError(type(exc).__name__) from None

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(type(exc).__name__) from None


@lru_cache
def get_storage() -> FileStorage:
    return LocalFileStorage(get_settings().document_storage_dir)
