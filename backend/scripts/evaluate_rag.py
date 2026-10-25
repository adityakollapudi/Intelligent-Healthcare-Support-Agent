"""Runs the synthetic RAG evaluation against the ingested corpus with the configured embedding model
and answer generator. Read-only: nothing is persisted (tool calls run through the real executor and
services as a seeded user of each role, with audit and tool-invocation writes disabled and every
transaction rolled back). Run: python -m scripts.evaluate_rag

Retrieval is scored separately from answers. Fact checks are deterministic substring checks; they do
not prove an answer is fully correct, and citation *support* still needs human review."""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.authz.dependencies import Principal
from app.authz.permissions import Permission
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import KnowledgeDocument, Plan
from app.rag import pipeline
from app.rag.embeddings import get_embedder
from app.rag.generation import get_generator
from app.rag.retrieval import ROLE_AUDIENCES, RetrievalScope, search
from app.repositories import user_repository
from app.services.audit_service import AuditService
from app.tools.executor import ToolContext, ToolExecutor

DATASET = Path("data/evaluation/rag_eval_v1.jsonl")
RESULTS = Path("data/evaluation/results")
LABEL = {
    ("DOCUMENT_GROUNDED", "SUPPORTED"): "ANSWER",
    ("DOCUMENT_GROUNDED", "CONFLICTING"): "CONFLICT",
    ("INSUFFICIENT_EVIDENCE", "INSUFFICIENT"): "INSUFFICIENT",
    ("CLARIFICATION", "NOT_APPLICABLE"): "CLARIFY",
    ("UNSUPPORTED_REQUEST", "NOT_APPLICABLE"): "UNSUPPORTED",
}
# Tool turns are labeled by what the executor returned, not by the answer text.
TOOL_LABEL = {"SUCCEEDED": "TOOL", "CONFIRMATION_REQUIRED": "PROPOSE_CASE", "NOT_FOUND": "TOOL_NOT_FOUND"}
EVAL_USERS = {
    "MEMBER": "priya.member@example.test",
    "PROVIDER": "jordan.provider@example.test",
    "SUPPORT_AGENT": "sam.agent@example.test",
    "ADMIN": "alex.admin@example.test",
}


class _NoAudit(AuditService):
    def record(self, *args, **kwargs) -> None:
        return None

    def add_to_transaction(self, *args, **kwargs) -> None:
        return None


class _NoLogExecutor(ToolExecutor):
    def _log(self, *args, **kwargs) -> None:
        return None


def _principal(db, role: str) -> Principal:
    user, member = user_repository.get_with_member(db, user_repository.get_by_email(db, EVAL_USERS[role]).id)
    return Principal(
        user_id=user.id, role=user.role, email=user.email, display_name=user.display_name,
        organization_id=user.organization_id, organization_name=None,
        member_id=member.id if member else None, member_number=member.member_number if member else None,
        plan_id=member.plan_id if member else None, plan_code=member.plan.plan_code if member else None,
        token_jti=uuid4(), token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _label(result) -> str:
    if result.answer_type == "TOOL_RESULT" and result.tool_results:
        return TOOL_LABEL.get(result.tool_results[-1].status, "TOOL_OTHER")
    return LABEL.get((result.answer_type, result.evidence_status), "OTHER")


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}% ({n}/{d})" if d else "n/a"


def main() -> int:
    settings = get_settings()
    embedder, generator = get_embedder(), get_generator()
    items = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    with get_session_factory()() as db:
        gold = db.scalars(select(Plan).where(Plan.plan_code == "SYN-PLAN-GOLD-01")).one()
        docs = {d.document_key + "@" + d.version: d for d in db.scalars(select(KnowledgeDocument))}
        audience_of = {d.document_key: set(d.audience) for d in docs.values()}
        plan_of = {d.document_key: d.plan_id for d in docs.values()}
        for item in items:
            role = item["role"]
            scope = RetrievalScope.for_user(role, gold.id if role == "MEMBER" else None)
            principal = _principal(db, role)
            executor = _NoLogExecutor(
                ToolContext(db, _NoAudit(), principal, session_id=None),
                max_calls=settings.tool_max_calls_per_message,
                requested_by="router",
            )
            ctx = pipeline.TurnContext(
                question=item["question"],
                history=[],
                scope=scope,
                executor=executor,
                session_id=None,
                can_view_claims=principal.has(Permission.CLAIMS_READ_OWN),
                can_create_cases=principal.has(Permission.CASES_CREATE),
                can_read_cases=principal.has(Permission.CASES_READ_OWN),
            )
            started = time.perf_counter()
            result = pipeline.run(db, settings, embedder, generator, ctx)
            latency = (time.perf_counter() - started) * 1000
            db.rollback()
            # Retrieval measured independently of the threshold and the generator.
            vec = embedder.embed_query(item["question"])
            cands = search(db, query_text=item["question"], query_vector=vec, model_id=embedder.model_id, scope=scope)
            active = [c for c in cands if c.lifecycle_status == "ACTIVE"]
            top_keys = [c.document_key for c in active[: settings.rag_top_k]]
            expected = set(item["expected_source_ids"])
            rank = next((i + 1 for i, k in enumerate(top_keys) if k in expected), None)
            unauthorized = [
                c.document_key
                for c in cands
                if not (audience_of[c.document_key] & set(ROLE_AUDIENCES[role]))
                or (role == "MEMBER" and plan_of[c.document_key] not in (None, gold.id))
            ]
            cited_keys = [i.candidate.document_key for i in result.cited]
            cited_versions = [(i.candidate.document_key, i.candidate.lifecycle_status) for i in result.cited]
            text = result.answer_text.lower()
            facts = item["expected_answer_facts"]
            actual = _label(result)
            rows.append(
                {
                    "test_id": item["test_id"],
                    "category": item["category"],
                    "role": role,
                    "expected": item["expected_behavior"],
                    "actual": actual,
                    "behavior_ok": actual in item["expected_behavior"],
                    "retrieval_rank": rank,
                    "best_similarity": round(max((c.similarity for c in active), default=0.0), 4),
                    "best_expected_similarity": round(
                        max((c.similarity for c in active if c.document_key in expected), default=0.0), 4
                    ),
                    "cited_keys": cited_keys,
                    "cited_expected": bool(expected & set(cited_keys)) if expected else None,
                    "cited_superseded": any(s != "ACTIVE" for _, s in cited_versions),
                    "cited_forbidden": sorted(set(cited_keys) & set(item["forbidden_source_ids"])),
                    "facts_found": sum(f.lower() in text for f in facts),
                    "facts_total": len(facts),
                    "unauthorized_candidates": unauthorized,
                    "latency_ms": round(latency, 1),
                }
            )

    report = summarize(rows, settings, embedder.model_id, generator.name, len(items))
    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = f"rag_eval_v1_{generator.name}"
    (RESULTS / f"{stem}.json").write_text(
        json.dumps({"summary": report["summary"], "rows": rows}, indent=2), encoding="utf-8"
    )
    (RESULTS / f"{stem}.md").write_text(report["markdown"], encoding="utf-8")
    print(report["markdown"])
    return 0


def summarize(rows, settings, model_id, generator_name, n):
    rag_answerable = [
        r
        for r in rows
        if r["expected"] in (["ANSWER"], ["CONFLICT"])
        and r["category"] != "injection"
        or (r["category"] == "injection" and r["expected"] == ["ANSWER"])
    ]
    rag_answerable = [
        r
        for r in rag_answerable
        if r["best_expected_similarity"]
        or r["retrieval_rank"] is not None
        or r["expected"] in (["ANSWER"], ["CONFLICT"])
    ]
    with_sources = [r for r in rows if r["expected"] in (["ANSWER"], ["CONFLICT"])]
    hits = [r for r in with_sources if r["retrieval_rank"] is not None]
    mrr = (
        statistics.mean(1 / r["retrieval_rank"] if r["retrieval_rank"] else 0 for r in with_sources)
        if with_sources
        else 0
    )
    answered = [r for r in rows if r["actual"] in ("ANSWER", "CONFLICT")]
    fact_rows = [r for r in rows if "ANSWER" in r["expected"] and r["actual"] in ("ANSWER", "TOOL") and r["facts_total"]]
    facts_found = sum(r["facts_found"] for r in fact_rows)
    facts_total = sum(r["facts_total"] for r in fact_rows)
    all_facts = [r for r in fact_rows if r["facts_found"] == r["facts_total"]]
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    latencies = sorted(r["latency_ms"] for r in rows)
    p95 = latencies[int(0.95 * (len(latencies) - 1))]

    # Threshold sweep on the pre-generation similarity gate (answerable vs. should-not-answer RAG items).
    answerable = [r for r in rows if r["expected"] == ["ANSWER"]]
    unanswerable = [r for r in rows if r["category"] in ("partial", "no-support")]
    sweep = []
    for t in [x / 100 for x in range(60, 82, 2)]:
        sweep.append(
            (
                t,
                sum(r["best_similarity"] >= t for r in answerable),
                sum(r["best_similarity"] >= t for r in unanswerable),
            )
        )

    summary = {
        "dataset": "rag_eval_v1",
        "items": n,
        "embedding_model": model_id,
        "generator": generator_name,
        "chunking": f"{settings.rag_chunk_words} words / {settings.rag_chunk_overlap_words} overlap",
        "top_k": settings.rag_top_k,
        "min_relevance": settings.rag_min_relevance,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "behavior_accuracy": sum(r["behavior_ok"] for r in rows) / n,
        "recall_at_k": len(hits) / len(with_sources) if with_sources else None,
        "mrr_at_k": mrr,
        "fact_recall": facts_found / facts_total if facts_total else None,
        "citation_source_correct": sum(bool(r["cited_expected"]) for r in answered if r["cited_expected"] is not None),
        "cited_superseded": sum(r["cited_superseded"] for r in rows),
        "cited_forbidden": sum(bool(r["cited_forbidden"]) for r in rows),
        "unauthorized_candidates": sum(bool(r["unauthorized_candidates"]) for r in rows),
        "latency_ms_p50": statistics.median(latencies),
        "latency_ms_p95": p95,
    }
    answered_with_expected = [r for r in answered if r["cited_expected"] is not None]
    md = [
        f"# RAG evaluation — rag_eval_v1 ({generator_name})",
        "",
        f"- Run: {summary['run_at']} · items: {n} · embedding: `{model_id}` · generator: `{generator_name}`",
        f"- Chunking: {summary['chunking']} · top_k: {settings.rag_top_k} · RAG_MIN_RELEVANCE: {settings.rag_min_relevance}",
        "",
        "## Headline metrics",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Expected behavior matched (all items) | {pct(sum(r['behavior_ok'] for r in rows), n)} |",
        f"| Retrieval recall@{settings.rag_top_k} (expected source in top {settings.rag_top_k}, answerable items) | {pct(len(hits), len(with_sources))} |",
        f"| MRR@{settings.rag_top_k} | {mrr:.3f} |",
        f"| Required facts present (answered, answerable items) | {pct(facts_found, facts_total)} |",
        f"| Answers with all required facts | {pct(len(all_facts), len(fact_rows))} |",
        f"| Answers citing an expected source | {pct(summary['citation_source_correct'], len(answered_with_expected))} |",
        f"| Answers citing a superseded version | {summary['cited_superseded']} |",
        f"| Answers citing a forbidden (out-of-scope) source | {summary['cited_forbidden']} |",
        f"| Items where an unauthorized document was even a candidate | {summary['unauthorized_candidates']} |",
        f"| Pipeline latency p50 / p95 (local CPU, includes embedding) | {summary['latency_ms_p50']:.0f} ms / {p95:.0f} ms |",
        "",
        "## Behavior by category",
        "",
        "| Category | Matched |",
        "|---|---|",
        *[f"| {c} | {pct(sum(r['behavior_ok'] for r in rs), len(rs))} |" for c, rs in by_cat.items()],
        "",
        "## Similarity-threshold sweep (pre-generation gate)",
        "",
        f"Answerable items: {len(answerable)}; partial/no-support items: {len(unanswerable)}.",
        "",
        "| Threshold | Answerable kept | Unanswerable passing the gate |",
        "|---|---|---|",
        *[f"| {t:.2f} | {pct(a, len(answerable))} | {pct(u, len(unanswerable))} |" for t, a, u in sweep],
        "",
        "## Mismatches",
        "",
        "| Test | Category | Expected | Actual | Best sim | Facts | Cited |",
        "|---|---|---|---|---|---|---|",
        *[
            f"| {r['test_id']} | {r['category']} | {'/'.join(r['expected'])} | {r['actual']} | {r['best_similarity']} | "
            f"{r['facts_found']}/{r['facts_total']} | {', '.join(r['cited_keys'])} |"
            for r in rows
            if not r["behavior_ok"] or r["facts_found"] < r["facts_total"] and r["actual"] == "ANSWER"
        ],
    ]
    return {"summary": summary, "markdown": "\n".join(md) + "\n"}


if __name__ == "__main__":
    sys.exit(main())
