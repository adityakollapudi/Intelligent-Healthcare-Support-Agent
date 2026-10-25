"""Ingestion and permission-filtered retrieval against PostgreSQL (test embedder)."""

import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import DocumentChunk, KnowledgeDocument, Plan
from app.rag.embeddings import HashEmbedder
from app.rag.errors import IngestionError
from app.rag.ingest import ingest_corpus, load_manifest
from app.rag.retrieval import RetrievalScope, search

pytestmark = pytest.mark.postgres

EMB = HashEmbedder(384)


def _entry(file, key, version="1.0", audience=("MEMBER", "PROVIDER", "SUPPORT_INTERNAL"), **extra):
    return {
        "file": file,
        "document_key": key,
        "title": f"Test {key}",
        "version": version,
        "document_type": "FAQ",
        "audience": list(audience),
        "plan_code": None,
        "effective_date": None,
        **extra,
    }


def _write(directory: Path, entries: list[dict]):
    (directory / "manifest.json").write_text(json.dumps({"documents": entries}), encoding="utf-8")


@pytest.fixture
def tx(database):
    """Each test runs in a transaction that is rolled back, so the shared knowledge stays intact."""
    from sqlalchemy.orm import Session

    from app.db.session import get_engine

    conn = get_engine().connect()
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    conn.close()


def run(session, directory):
    return ingest_corpus(session, EMB, directory, chunk_words=160, overlap_words=30)


def test_ingest_idempotent_update_supersede_retire(tx, tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n## Topic\nAlpha parking rules for synthetic clinics.", encoding="utf-8")
    (tmp_path / "b1.md").write_text("# B\n\n## Rule\nBeta deadline is 10 days.", encoding="utf-8")
    _write(tmp_path, [_entry("a.md", "zz-alpha"), _entry("b1.md", "zz-beta")])
    first = run(tx, tmp_path)
    assert sorted(first.inserted) == ["zz-alpha@1.0", "zz-beta@1.0"] and not first.failed

    again = run(tx, tmp_path)
    assert sorted(again.skipped) == ["zz-alpha@1.0", "zz-beta@1.0"] and again.chunks_written == 0

    (tmp_path / "a.md").write_text("# A\n\n## Topic\nAlpha parking rules changed: parking costs $5.", encoding="utf-8")
    (tmp_path / "b2.md").write_text("# B\n\n## Rule\nBeta deadline is 20 days.", encoding="utf-8")
    _write(tmp_path, [_entry("a.md", "zz-alpha"), _entry("b1.md", "zz-beta"), _entry("b2.md", "zz-beta", "2.0")])
    third = run(tx, tmp_path)
    assert third.updated == ["zz-alpha@1.0"] and third.inserted == ["zz-beta@2.0"]
    assert third.superseded == ["zz-beta@1.0"]
    alpha = tx.scalars(select(KnowledgeDocument).where(KnowledgeDocument.document_key == "zz-alpha")).one()
    assert "$5" in alpha.chunks[0].content and len(alpha.chunks) == alpha.chunk_count  # no stale chunks left
    v1 = tx.scalars(
        select(KnowledgeDocument).where(KnowledgeDocument.document_key == "zz-beta", KnowledgeDocument.version == "1.0")
    ).one()
    assert v1.lifecycle_status == "SUPERSEDED" and v1.superseded_by_id is not None

    _write(tmp_path, [_entry("b2.md", "zz-beta", "2.0")])
    fourth = run(tx, tmp_path)
    assert "zz-alpha@1.0" in fourth.retired

    # Changing chunking parameters re-indexes unchanged files (no stale chunk layout is served).
    fifth = ingest_corpus(tx, EMB, tmp_path, chunk_words=80, overlap_words=10)
    assert fifth.updated == ["zz-beta@2.0"] and not fifth.skipped


def test_failures_are_reported_and_leave_no_chunks(tx, tmp_path):
    (tmp_path / "ok.md").write_text("# OK\n\nA perfectly fine synthetic document body.", encoding="utf-8")
    (tmp_path / "empty.md").write_text("  ", encoding="utf-8")
    (tmp_path / "broken.pdf").write_bytes(b"%PDF-1.4 not really")
    _write(
        tmp_path,
        [
            _entry("ok.md", "zz-ok"),
            _entry("empty.md", "zz-empty"),
            _entry("broken.pdf", "zz-pdf"),
            _entry("missing.md", "zz-missing"),
        ],
    )
    report = run(tx, tmp_path)
    assert report.failed == {
        "zz-empty@1.0": "EMPTY_DOCUMENT",
        "zz-pdf@1.0": "PDF_PARSE_ERROR",
        "zz-missing@1.0": "FILE_NOT_FOUND_IN_CORPUS",
    }
    failed_ids = select(KnowledgeDocument.id).where(KnowledgeDocument.ingestion_status == "INGESTION_FAILED")
    assert (
        tx.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id.in_(failed_ids))) == 0
    )


@pytest.mark.parametrize("bad_file", ["../secrets.md", "sub/dir.md", "..\\x.md"])
def test_manifest_rejects_paths_outside_the_corpus(tmp_path, bad_file):
    _write(tmp_path, [_entry(bad_file, "zz-bad")])
    with pytest.raises(IngestionError, match="INVALID_MANIFEST"):
        load_manifest(tmp_path)


def test_real_corpus_is_ingested(knowledge, db_session):
    docs = db_session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.ingestion_status == "INGESTED")).all()
    assert len(docs) == 15  # 14 corpus documents + 1 adversarial test document
    pdf = next(d for d in docs if d.source_type == "pdf")
    assert pdf.page_count == 2 and {c.page_start for c in pdf.chunks} == {1, 2}
    assert all(c.embedding_dim == 384 for d in docs for c in d.chunks)
    gold = db_session.scalars(select(Plan).where(Plan.plan_code == "SYN-PLAN-GOLD-01")).one()
    assert gold.source_document_id is not None


def _keys(session, scope, q="support agent escalation queue supervisor"):
    return {
        c.document_key
        for c in search(session, query_text=q, query_vector=EMB.embed_query(q), model_id=EMB.model_id, scope=scope)
    }


def test_retrieval_applies_audience_and_plan_filters(knowledge, db_session):
    gold = db_session.scalars(select(Plan).where(Plan.plan_code == "SYN-PLAN-GOLD-01")).one()
    member = _keys(db_session, RetrievalScope.for_user("MEMBER", gold.id), "plan copay deductible visits")
    assert "support-agent-procedures" not in member and "provider-admin-faq" not in member
    assert "gold-plan-benefit-guide" in member and "bronze-plan-benefit-guide" not in member
    agent = _keys(db_session, RetrievalScope.for_user("SUPPORT_AGENT", None))
    assert "support-agent-procedures" in agent
    provider = _keys(db_session, RetrievalScope.for_user("PROVIDER", None))
    assert "support-agent-procedures" not in provider and "provider-admin-faq" in provider


def test_superseded_versions_are_marked_for_exclusion(knowledge, db_session):
    q = "lumbar MRI conservative therapy weeks"
    results = search(
        db_session,
        query_text=q,
        query_vector=EMB.embed_query(q),
        model_id=EMB.model_id,
        scope=RetrievalScope.for_user("PROVIDER", None),
    )
    statuses = {(c.version, c.lifecycle_status) for c in results if c.document_key == "pa-imaging-guide"}
    assert ("1.0", "SUPERSEDED") in statuses and ("2.0", "ACTIVE") in statuses


def test_vectors_from_another_model_are_never_compared(knowledge, db_session):
    q = "physical therapy"
    assert (
        search(
            db_session,
            query_text=q,
            query_vector=EMB.embed_query(q),
            model_id="other-model",
            scope=RetrievalScope.for_user("ADMIN", None),
        )
        == []
    )


@pytest.mark.skipif(
    not (Path(".local/models").exists() and any(Path(".local/models").iterdir())),
    reason="real embedding model not downloaded (run the ingestion script once)",
)
def test_real_model_ranks_the_right_document_first(tmp_path):
    """Uses the real bge-small model on two documents (no database)."""
    from app.rag.embeddings import FastEmbedEmbedder

    real = FastEmbedEmbedder("BAAI/bge-small-en-v1.5", 384, ".local/models")
    docs = real.embed_documents(
        [
            "Outpatient physical therapy is limited to 20 visits per plan year.",
            "An appeal must be filed within 180 days.",
        ]
    )
    q = real.embed_query("how many PT sessions do I get each year")
    sims = [sum(a * b for a, b in zip(q, d, strict=True)) for d in docs]
    assert sims[0] > sims[1]
    shutil.rmtree(tmp_path, ignore_errors=True)
