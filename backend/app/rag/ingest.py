"""Controlled ingestion of the trusted, admin-managed knowledge corpus (FR-008).

Only files listed in <knowledge dir>/manifest.json are read, and only from inside that directory.
Each document is processed in its own savepoint: a failure marks it INGESTION_FAILED with no
chunks, and never affects other documents. Re-running is idempotent (content hash + model id).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentChunk, KnowledgeDocument, Plan
from app.models.knowledge import AUDIENCES, DOCUMENT_TYPES
from app.rag.chunking import chunk_pages, chunking_fingerprint
from app.rag.embeddings import Embedder
from app.rag.errors import AIServiceUnavailableError, IngestionError
from app.rag.extract import extract, source_type_for

logger = logging.getLogger(__name__)


class ManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")  # bare file name: no paths
    document_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    title: str = Field(min_length=3, max_length=250)
    version: str = Field(pattern=r"^\d+(\.\d+){0,3}$")
    document_type: str
    audience: list[str] = Field(min_length=1)
    plan_code: str | None = None
    effective_date: date | None = None

    @field_validator("document_type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError(f"must be one of {DOCUMENT_TYPES}")
        return v

    @field_validator("audience")
    @classmethod
    def _aud(cls, v: list[str]) -> list[str]:
        if set(v) - set(AUDIENCES):
            raise ValueError(f"values must be in {AUDIENCES}")
        return sorted(set(v))


@dataclass
class IngestReport:
    inserted: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    superseded: list[str] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    chunks_written: int = 0

    def lines(self) -> list[str]:
        return [
            f"inserted={len(self.inserted)} updated={len(self.updated)} skipped={len(self.skipped)} "
            f"failed={len(self.failed)} superseded={len(self.superseded)} retired={len(self.retired)} "
            f"chunks_written={self.chunks_written}",
            *[f"  FAILED {name}: {code}" for name, code in self.failed.items()],
            *[f"  superseded: {name}" for name in self.superseded],
            *[f"  retired: {name}" for name in self.retired],
        ]


def load_manifest(directory: Path) -> list[ManifestEntry]:
    path = directory / "manifest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = [ManifestEntry(**item) for item in raw["documents"]]
    except (OSError, KeyError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise IngestionError("INVALID_MANIFEST", type(exc).__name__) from None
    keys = [(e.document_key, e.version) for e in entries]
    if len(keys) != len(set(keys)):
        raise IngestionError("INVALID_MANIFEST", "duplicate document_key/version")
    return entries


def _resolve(directory: Path, name: str) -> Path:
    root = directory.resolve()
    path = (root / name).resolve()
    if path.parent != root or not path.is_file():
        raise IngestionError("FILE_NOT_FOUND_IN_CORPUS", name)
    return path


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def _embedding_text(title: str, heading: str | None, content: str) -> str:
    # Title/section context improves retrieval of short chunks; stored content stays verbatim.
    return f"{title}{' — ' + heading if heading else ''}\n{content}"


def ingest_corpus(
    session: Session, embedder: Embedder, directory: Path, *, chunk_words: int, overlap_words: int
) -> IngestReport:
    report = IngestReport()
    fingerprint = chunking_fingerprint(chunk_words, overlap_words)
    entries = load_manifest(directory)
    plans = {p.plan_code: p for p in session.scalars(select(Plan))}

    for entry in entries:
        label = f"{entry.document_key}@{entry.version}"
        existing = session.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.document_key == entry.document_key, KnowledgeDocument.version == entry.version
            )
        ).first()
        try:
            path = _resolve(directory, entry.file)
            source_type = source_type_for(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if (
                existing
                and existing.content_sha256 == digest
                and existing.ingestion_status == "INGESTED"
                and existing.embedding_model == embedder.model_id
                and existing.chunking_config == fingerprint
                and _metadata_matches(existing, entry, plans)
            ):
                report.skipped.append(label)
                continue
            if entry.plan_code and entry.plan_code not in plans:
                raise IngestionError("UNKNOWN_PLAN_CODE", entry.plan_code)
            pages = extract(path)
            chunks = chunk_pages(
                pages, markdown=source_type == "markdown", chunk_words=chunk_words, overlap_words=overlap_words
            )
            if not chunks:
                raise IngestionError("NO_CHUNKS")
            vectors = embedder.embed_documents(
                [_embedding_text(entry.title, c.section_heading, c.content) for c in chunks]
            )
        except (IngestionError, AIServiceUnavailableError) as exc:
            code = exc.code if isinstance(exc, IngestionError) else "EMBEDDING_FAILED"
            report.failed[label] = code
            _record_failure(session, existing, entry, plans, code)
            continue

        with session.begin_nested():
            if existing is not None:
                existing.chunks.clear()  # delete stale chunks before inserting new ones (unique index)
                session.flush()
            doc = existing or KnowledgeDocument(
                document_key=entry.document_key, version=entry.version, lifecycle_status="RETIRED"
            )  # lifecycle pass decides below
            doc.title = entry.title
            doc.document_type = entry.document_type
            doc.audience = entry.audience
            doc.plan_id = plans[entry.plan_code].id if entry.plan_code else None
            doc.effective_date = entry.effective_date
            doc.source_filename = entry.file
            doc.source_type = source_type
            doc.content_sha256 = digest
            doc.page_count = len(pages) if source_type == "pdf" else None
            doc.embedding_model = embedder.model_id
            doc.chunking_config = fingerprint
            doc.ingestion_status = "INGESTED"
            doc.ingestion_error_code = None
            doc.ingested_at = datetime.now(UTC)
            doc.chunk_count = len(chunks)
            doc.is_synthetic = True
            doc.chunks = [
                DocumentChunk(
                    chunk_index=i,
                    section_heading=(c.section_heading or "")[:300] or None,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    content=c.content,
                    token_count=c.word_count,
                    embedding=vec,
                    embedding_dim=len(vec),
                    embedding_model=embedder.model_id,
                )
                for i, (c, vec) in enumerate(zip(chunks, vectors, strict=True))
            ]
            session.add(doc)
            session.flush()
        (report.updated if existing else report.inserted).append(label)
        report.chunks_written += len(chunks)

    _apply_lifecycle(session, entries, report)
    _link_plans(session, plans)
    return report


def _metadata_matches(doc: KnowledgeDocument, entry: ManifestEntry, plans: dict[str, Plan]) -> bool:
    plan_id = plans[entry.plan_code].id if entry.plan_code in plans else None
    return (
        doc.title == entry.title
        and doc.document_type == entry.document_type
        and sorted(doc.audience) == entry.audience
        and doc.plan_id == plan_id
        and doc.effective_date == entry.effective_date
        and doc.source_filename == entry.file
    )


def _record_failure(
    session: Session, existing: KnowledgeDocument | None, entry: ManifestEntry, plans: dict[str, Plan], code: str
) -> None:
    logger.warning("ingestion_failed", extra={"document_key": entry.document_key, "error_code": code})
    with session.begin_nested():
        doc = existing or KnowledgeDocument(
            document_key=entry.document_key,
            version=entry.version,
            title=entry.title,
            document_type=entry.document_type,
            audience=entry.audience,
            source_filename=entry.file,
            source_type="unknown",
            content_sha256="",
            lifecycle_status="RETIRED",
        )
        doc.ingestion_status = "INGESTION_FAILED"
        doc.ingestion_error_code = code
        doc.chunks.clear()  # a failed document never keeps searchable (possibly stale) chunks
        doc.chunk_count = 0
        doc.lifecycle_status = "RETIRED"
        session.add(doc)
        session.flush()


def _apply_lifecycle(session: Session, entries: list[ManifestEntry], report: IngestReport) -> None:
    """Per document_key the highest successfully ingested version is ACTIVE; older ones are
    SUPERSEDED (kept for historical citations, never retrieved as current evidence). Documents no
    longer in the manifest are RETIRED."""
    listed = {(e.document_key, e.version) for e in entries}
    docs = list(session.scalars(select(KnowledgeDocument)))
    by_key: dict[str, list[KnowledgeDocument]] = defaultdict(list)
    for doc in docs:
        if (doc.document_key, doc.version) in listed and doc.ingestion_status == "INGESTED":
            by_key[doc.document_key].append(doc)
        elif doc.lifecycle_status != "RETIRED":
            doc.lifecycle_status = "RETIRED"
            report.retired.append(f"{doc.document_key}@{doc.version}")

    winners: dict[str, KnowledgeDocument] = {}
    for key, versions in by_key.items():
        versions.sort(key=lambda d: _version_key(d.version))
        winners[key] = versions[-1]
        for old in versions[:-1]:
            if old.lifecycle_status != "SUPERSEDED":
                report.superseded.append(f"{old.document_key}@{old.version}")
            old.lifecycle_status = "SUPERSEDED"
            old.superseded_by_id = versions[-1].id
    session.flush()  # demotions first, so the one-ACTIVE-per-key index never sees two
    for doc in winners.values():
        doc.lifecycle_status = "ACTIVE"
        doc.superseded_by_id = None
    session.flush()


def _link_plans(session: Session, plans: dict[str, Plan]) -> None:
    for plan in plans.values():
        guide = session.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.plan_id == plan.id,
                KnowledgeDocument.document_type == "BENEFIT_GUIDE",
                KnowledgeDocument.lifecycle_status == "ACTIVE",
            )
        ).first()
        plan.source_document_id = guide.id if guide else None
    session.flush()
