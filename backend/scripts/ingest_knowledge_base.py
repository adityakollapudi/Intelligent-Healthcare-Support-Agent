"""Ingests the trusted synthetic knowledge corpus. Run: python -m scripts.ingest_knowledge_base

Reads only files listed in RAG_KNOWLEDGE_DIR/manifest.json. Safe to re-run: unchanged documents
are skipped, changed ones are re-indexed, older versions are superseded. Prints counts only."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from app.core.config import ConfigurationError, get_settings
from app.db.session import get_session_factory
from app.models.enums import AuditOutcome
from app.rag.embeddings import get_embedder
from app.rag.errors import IngestionError
from app.rag.ingest import ingest_corpus
from app.services.audit_service import AuditService


def main() -> int:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 2
    directory = Path(settings.rag_knowledge_dir)
    if not (directory / "manifest.json").is_file():
        print(f"No manifest.json in {directory}", file=sys.stderr)
        return 2

    embedder = get_embedder()
    print(f"Embedding model: {embedder.model_id} (dim {embedder.dim}); corpus: {directory}")
    started = time.perf_counter()
    try:
        with get_session_factory()() as session, session.begin():
            report = ingest_corpus(
                session,
                embedder,
                directory,
                chunk_words=settings.rag_chunk_words,
                overlap_words=settings.rag_chunk_overlap_words,
            )
    except IngestionError as exc:
        print(f"Ingestion aborted: {exc.code}", file=sys.stderr)
        return 1
    for line in report.lines():
        print(line)
    AuditService().record(
        "KNOWLEDGE_INGESTION_RUN",
        AuditOutcome.FAILURE if report.failed else AuditOutcome.SUCCESS,
        resource_type="knowledge_corpus",
        metadata={
            "result_count": len(report.inserted) + len(report.updated),
            "chunk_count": report.chunks_written,
            "failed_count": len(report.failed),
        },
    )
    print(f"Done in {time.perf_counter() - started:.1f}s")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
