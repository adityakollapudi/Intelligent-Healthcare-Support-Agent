"""Permission-aware hybrid retrieval (FR-009, doc 07 §2.5).

Access filters (audience, plan scope, ingestion status) are applied in SQL before any scoring, so
an unpermitted chunk is never a candidate. Vector similarity is computed in Python over REAL[]
embeddings (deviation D4-01) and fused with PostgreSQL full-text rank by Reciprocal Rank Fusion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

ROLE_AUDIENCES: dict[str, list[str]] = {
    "MEMBER": ["MEMBER"],
    "PROVIDER": ["MEMBER", "PROVIDER"],
    "SUPPORT_AGENT": ["MEMBER", "PROVIDER", "SUPPORT_INTERNAL"],
    "ADMIN": ["MEMBER", "PROVIDER", "SUPPORT_INTERNAL"],
}
RRF_K = 60


@dataclass(frozen=True)
class RetrievalScope:
    audiences: list[str]
    plan_id: UUID | None  # members: their plan only; None means "no plan restriction" (staff)
    restrict_plan: bool

    @classmethod
    def for_user(cls, role: str, plan_id: UUID | None) -> RetrievalScope:
        return cls(audiences=ROLE_AUDIENCES.get(role, []), plan_id=plan_id, restrict_plan=role == "MEMBER")


@dataclass(frozen=True)
class Candidate:
    chunk_id: UUID
    document_id: UUID
    document_key: str
    title: str
    version: str
    document_type: str
    effective_date: date | None
    plan_id: UUID | None
    lifecycle_status: str
    section_heading: str | None
    page_start: int | None
    page_end: int | None
    content: str
    similarity: float
    keyword_rank: float
    fused: float


_SQL = text(
    """
    SELECT c.id AS chunk_id, d.id AS document_id, d.document_key, d.title, d.version, d.document_type,
           d.effective_date, d.plan_id, d.lifecycle_status, c.section_heading, c.page_start, c.page_end, c.content,
           c.embedding, c.embedding_model,
           ts_rank_cd(c.content_tsv, websearch_to_tsquery('english', :q)) AS keyword_rank
    FROM document_chunks c
    JOIN knowledge_documents d ON d.id = c.document_id
    WHERE d.ingestion_status = 'INGESTED'
      AND d.lifecycle_status IN ('ACTIVE', 'SUPERSEDED')
      AND d.audience && CAST(:audiences AS text[])
      AND (NOT :restrict_plan OR d.plan_id IS NULL OR d.plan_id = :plan_id)
    """
)


def search(
    session: Session, *, query_text: str, query_vector: list[float], model_id: str, scope: RetrievalScope
) -> list[Candidate]:
    """All permitted candidates, best first (ACTIVE and SUPERSEDED; callers decide what counts)."""
    if not scope.audiences:
        return []
    rows = (
        session.execute(
            _SQL,
            {
                "q": query_text,
                "audiences": scope.audiences,
                "restrict_plan": scope.restrict_plan,
                "plan_id": scope.plan_id,
            },
        )
        .mappings()
        .all()
    )
    rows = [r for r in rows if r["embedding_model"] == model_id]  # never compare across vector spaces
    if not rows:
        return []
    matrix = np.asarray([r["embedding"] for r in rows], dtype=np.float32)
    q = np.asarray(query_vector, dtype=np.float32)
    sims = matrix @ q / (np.linalg.norm(matrix, axis=1) * (np.linalg.norm(q) or 1.0) + 1e-9)

    vector_rank = {i: r for r, i in enumerate(np.argsort(-sims))}
    keyword_order = sorted(range(len(rows)), key=lambda i: -rows[i]["keyword_rank"])
    keyword_rank = {i: r for r, i in enumerate(keyword_order) if rows[i]["keyword_rank"] > 0}

    out = []
    for i, row in enumerate(rows):
        fused = 1 / (RRF_K + vector_rank[i] + 1) + (1 / (RRF_K + keyword_rank[i] + 1) if i in keyword_rank else 0.0)
        out.append(
            Candidate(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_key=row["document_key"],
                title=row["title"],
                version=row["version"],
                document_type=row["document_type"],
                effective_date=row["effective_date"],
                plan_id=row["plan_id"],
                lifecycle_status=row["lifecycle_status"],
                section_heading=row["section_heading"],
                page_start=row["page_start"],
                page_end=row["page_end"],
                content=row["content"],
                similarity=float(sims[i]) if math.isfinite(float(sims[i])) else 0.0,
                keyword_rank=float(row["keyword_rank"]),
                fused=fused,
            )
        )
    out.sort(key=lambda c: (-c.fused, -c.similarity))
    return out
