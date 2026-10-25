"""Chat orchestration: route → (tool via executor | permission-filtered retrieval) → generate → validate.
No persistence or HTTP concerns here; app/services/chat_service.py owns those.

Two modes, one security path:
- extractive (no LLM): the deterministic router chooses the tool and its arguments;
- anthropic: Claude may request tools natively.
Either way every tool call goes through ToolExecutor (allowlist, schema, permission, audit), and answer
text about records is built from (or checked against) verified tool output. Nothing here writes data:
support cases are only *proposed*; creation requires the user's confirmed POST /support-cases."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import DocumentChunk, KnowledgeDocument
from app.rag import citations as citation_check
from app.rag.embeddings import Embedder
from app.rag.evidence import EvidenceState, assess, money_conflicts
from app.rag.generation import Generation, Generator
from app.rag.intent import CLAIM_NUMBER, PLAN_CODE, Intent, Route, benefit_category, is_follow_up, route
from app.rag.prompts import EvidenceItem
from app.rag.retrieval import Candidate, RetrievalScope, search
from app.services import requirements_service
from app.tools.executor import ToolExecutor, ToolResult

logger = logging.getLogger(__name__)

SYNTHETIC_NOTE = "Information comes from synthetic prototype documents and is not a coverage or authorization decision."
RECORD_NOTE = "Values marked as records come directly from the synthetic database."
STATUS_LABELS = {
    "RECEIVED": "Received",
    "UNDER_PROCESSING": "Under processing",
    "PENDING_INFORMATION": "Pending information",
    "PROCESSED_PAID": "Processed – paid",
    "PROCESSED_DENIED": "Processed – denied",
}


@dataclass
class Action:
    action_type: str
    label: str
    requires_confirmation: bool
    available: bool
    prefill: dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    intent: str
    answer_type: str
    evidence_status: str
    answer_text: str
    cited: list[EvidenceItem] = field(default_factory=list)
    citation_check: str = "NOT_APPLICABLE"
    escalation_reason: str | None = None
    actions: list[Action] = field(default_factory=list)
    disclaimers: list[str] = field(default_factory=list)
    gap_topic: str | None = None
    retrieved_document_ids: list[str] = field(default_factory=list)
    retrieval_ms: int = 0
    generation_ms: int = 0
    tool_results: list[ToolResult] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TurnContext:
    """Per-request facts the orchestrator needs; identity-related values come from the server."""

    question: str
    history: list[tuple[str, str]]
    scope: RetrievalScope
    executor: ToolExecutor
    session_id: UUID | None
    can_view_claims: bool
    can_create_cases: bool
    can_read_cases: bool
    can_check_readiness: bool = False


_ID_LIKE = re.compile(r"\b[A-Z]{2,}-[A-Z0-9-]{3,}\b|\d{4,}|\S+@\S+")
_FALSE_SUCCESS = re.compile(
    r"\b(case (has been|was|is now) (created|submitted|opened|filed)|i('ve| have) (created|submitted|opened|filed)|"
    r"(has|have) been approved|is approved|authorization (was|is) approved)\b|CASE-\d{4}-\d{6}",
    re.I,
)


def gap_topic(question: str) -> str:
    """Short, identifier-free topic label for knowledge-gap reporting (FR-033)."""
    words = [w for w in re.findall(r"[a-z]+", _ID_LIKE.sub(" ", question).lower()) if len(w) > 3][:6]
    return " ".join(words)[:120] or "unspecified"


def _case_category(intent: str, history: list[tuple[str, str]]) -> str:
    text = " ".join(t for r, t in history[-4:] if r == "user").lower()
    if intent == Intent.CLAIM_STATUS or "claim" in text:
        return "CLAIM_INQUIRY"
    if "benefit" in text or "cover" in text or "copay" in text:
        return "BENEFITS_QUESTION"
    if "document" in text or "authorization" in text:
        return "DOCUMENT_ISSUE"
    return "OTHER"


def _case_summary(question: str, history: list[tuple[str, str]]) -> str:
    previous = next((t for r, t in reversed(history) if r == "user" and len(t) > 15), None)
    base = previous if previous and len(question) < 60 else question
    summary = f"Support requested from the assistant. User's question: {base}".strip()
    return summary[:1000]


def case_offer(ctx: TurnContext, reason: str, category: str) -> Action:
    """Escalation offer built by the server (not a tool call). Creating it still needs the user's
    confirmed POST /support-cases with the server-issued idempotency key below."""
    return Action(
        "CREATE_SUPPORT_CASE",
        "Ask a support agent",
        requires_confirmation=True,
        available=ctx.can_create_cases,
        prefill={
            "category": category,
            "summary": _case_summary(ctx.question, ctx.history),
            "escalation_reason": reason,
            "related_session_id": str(ctx.session_id) if ctx.session_id else None,
            "idempotency_key": str(uuid4()),
        },
    )


def run(db: Session, settings: Settings, embedder: Embedder, generator: Generator, ctx: TurnContext) -> PipelineResult:
    intent, rt = route(ctx.question, has_history=bool(ctx.history))

    if rt is Route.PROMPT_DISCLOSURE:
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "I can't share my configuration, run queries or commands, change how I work, or provide "
            "other people's information. I can help with your own claims and plan, plan documents, "
            "document requirements and support.",
        )
    if rt is Route.MEDICAL:
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "I can't give medical advice, diagnoses or treatment recommendations. Please ask a doctor "
            "or other qualified clinician. I can help with administrative questions such as benefits, "
            "claims and required documents.",
            escalation_reason="OUT_OF_SCOPE",
        )
    if rt is Route.ACCOUNT_LOOKUP_UNAVAILABLE:
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "I can't see account-specific information such as payment dates, balances, spending toward "
            "your deductible, or authorization decisions; no tool for that exists in this prototype, "
            "and a document checklist is never an approval. I can show your claim records, your "
            "plan's stored benefits, or explain what the documents say.",
        )
    if rt is Route.CLARIFY:
        return PipelineResult(
            intent,
            "CLARIFICATION",
            "NOT_APPLICABLE",
            "Could you tell me a bit more about what you'd like to know? For example: \"What is the "
            'status of claim SYN-CLM-2026-000101?", "Show my plan benefits" or "What does a '
            'lumbar MRI prior authorization request need?"',
        )
    if rt is Route.CASE_TRACK:
        actions = [Action("VIEW_CASE", "Open Support cases", False, True)] if ctx.can_read_cases else []
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "You can see the current status and history of your support cases on the Support cases screen."
            if ctx.can_read_cases
            else "Your account doesn't have support cases to track.",
            actions=actions,
        )

    if generator.name == "anthropic":
        return _llm_turn(db, settings, embedder, generator, ctx, intent)

    if rt is Route.CLAIM_TOOL:
        return _claim_turn(db, settings, embedder, generator, ctx, intent)
    if rt is Route.BENEFITS_TOOL:
        return _benefits_turn(ctx, intent)
    if rt is Route.CASE_CREATE:
        return _case_turn(ctx, intent)
    if rt is Route.REQUIREMENTS:
        matches = requirements_service.match_procedures(db, ctx.question)
        if len(matches) > 1:
            names = "; ".join(f"{m.display_name} ({m.procedure_code})" for m in matches)
            return PipelineResult(
                intent,
                "CLARIFICATION",
                "NOT_APPLICABLE",
                f"Which procedure do you mean? Configured requirement sets: {names}.",
            )
        if matches:
            return _requirements_turn(db, ctx, intent, matches[0].procedure_code)
        # No configured set matches: answer from documents (grounded), never invent a checklist.
    return _rag_turn(db, settings, embedder, generator, ctx, intent)


# --- deterministic tool turns (extractive mode) ------------------------------------------------------


def _tool_failure(ctx: TurnContext, intent: str, result: ToolResult, what: str) -> PipelineResult:
    return PipelineResult(
        intent,
        "ERROR",
        "NOT_APPLICABLE",
        f"I couldn't complete the {what} right now, so I have no result to show. Please try again "
        "later, or ask a support agent.",
        escalation_reason="TOOL_FAILURE",
        actions=[case_offer(ctx, "TOOL_FAILURE", "TECHNICAL_ISSUE")],
        tool_results=[result],
    )


def _claim_turn(db, settings, embedder, generator, ctx: TurnContext, intent: str) -> PipelineResult:
    number = CLAIM_NUMBER.search(ctx.question)
    result = ctx.executor.execute("get_claim_status", {"claim_number": number.group(0).upper()} if number else {})
    view = [Action("VIEW_CLAIM", "Open My claims", False, True)] if ctx.can_view_claims else []
    if result.status == "PERMISSION_DENIED":
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "Your account can't look up member claims. Claim lookups are limited to the member the claim belongs to.",
            tool_results=[result],
        )
    if result.status == "INVALID_ARGUMENTS":
        return PipelineResult(
            intent,
            "CLARIFICATION",
            "NOT_APPLICABLE",
            "Which claim do you mean? Please give the claim number, for example SYN-CLM-2026-000101.",
            tool_results=[result],
        )
    if result.status == "NOT_FOUND":
        return PipelineResult(
            intent,
            "TOOL_RESULT",
            "NOT_APPLICABLE",
            "I couldn't find a claim with that number on your account. Please check the number."
            + (" Your claims are listed on the My claims screen." if ctx.can_view_claims else ""),
            actions=view,
            tool_results=[result],
        )
    if result.status != "SUCCEEDED":
        return _tool_failure(ctx, intent, result, "claim lookup")

    claims = result.data["claims"]
    if not claims:
        return PipelineResult(
            intent,
            "TOOL_RESULT",
            "VERIFIED_RECORD",
            "You have no claims on record.",
            tool_results=[result],
            records=[{"kind": "claims", "data": result.data}],
            actions=view,
            disclaimers=[RECORD_NOTE],
        )
    lines = [
        f"- {c['claim_number']}: {STATUS_LABELS.get(c['status'], c['status'])} (submitted "
        f"{c['submission_date']}, last updated {c['last_status_change_at'][:10]})"
        for c in claims
    ]
    heading = "From your claim record:" if number else f"Your {len(claims)} most recent claims (from your records):"
    text = heading + "\n" + "\n".join(lines)
    cited: list[EvidenceItem] = []
    check = "NOT_APPLICABLE"
    if number and claims:
        # Explanation of the status comes from the claims guide, cited separately from the record.
        label = STATUS_LABELS.get(claims[0]["status"], claims[0]["status"])
        explain = _rag_turn(
            db, settings, embedder, generator, _with_question(ctx, f"What does the claim status {label} mean?"), intent
        )
        if explain.answer_type == "DOCUMENT_GROUNDED":
            # Keep only sentences about this status (the guide lists every status) and their sources.
            body = [ln.replace("**", "") for ln in explain.answer_text.split("\n")[1:] if ln.strip()]
            body = [ln for ln in body if label.lower() in ln.lower()] or body
            used = set(re.findall(r"\[(C\d+)\]", "\n".join(body)))
            text += "\n\nWhat this status means (claims guide):\n" + "\n".join(body)
            cited, check = [e for e in explain.cited if e.marker in used], explain.citation_check
    return PipelineResult(
        intent,
        "TOOL_RESULT",
        "VERIFIED_RECORD",
        text,
        cited=cited,
        citation_check=check,
        tool_results=[result],
        records=[{"kind": "claims", "data": result.data}],
        actions=view,
        disclaimers=[RECORD_NOTE] + ([SYNTHETIC_NOTE] if cited else []),
    )


def _benefits_turn(ctx: TurnContext, intent: str) -> PipelineResult:
    code = PLAN_CODE.search(ctx.question)
    args: dict[str, Any] = {}
    if code:
        args["plan_code"] = code.group(0).upper()
    if (category := benefit_category(ctx.question)) is not None:
        args["benefit_category"] = category
    result = ctx.executor.execute("get_plan_benefits", args)
    if result.status == "INVALID_ARGUMENTS":
        return PipelineResult(
            intent,
            "CLARIFICATION",
            "NOT_APPLICABLE",
            "Which plan do you mean? Please give the plan code, for example SYN-PLAN-GOLD-01.",
            tool_results=[result],
        )
    if result.status == "NOT_FOUND":
        return PipelineResult(
            intent,
            "TOOL_RESULT",
            "NOT_APPLICABLE",
            "No active plan with that code is available to you.",
            tool_results=[result],
        )
    if result.status == "PERMISSION_DENIED":
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "Your account can't look up plan benefits.",
            tool_results=[result],
        )
    if result.status != "SUCCEEDED":
        return _tool_failure(ctx, intent, result, "benefits lookup")
    plan = result.data
    if not plan["benefits"]:
        text = f"The {plan['plan_name']} record has no stored benefit entries for that category."
    else:
        lines = []
        for b in plan["benefits"]:
            parts = [
                f"in network {b['in_network_cost_share'] or 'not listed'}",
                f"out of network {b['out_of_network_cost_share'] or 'not listed'}",
            ]
            if b["visit_limit"]:
                parts.append(b["visit_limit"])
            if b["prior_auth_required"]:
                parts.append("prior authorization listed")
            lines.append(f"- {b['service_name']}: " + "; ".join(parts))
        text = (
            f"Stored benefits for {plan['plan_name']} ({plan['plan_code']}, plan year {plan['plan_year']}):\n"
            + "\n".join(lines)
            + '\n"Not listed" means the record has no value; it isn\'t a coverage decision.'
        )
    return PipelineResult(
        intent,
        "TOOL_RESULT",
        "VERIFIED_RECORD",
        text,
        tool_results=[result],
        records=[{"kind": "plan_benefits", "data": plan}],
        disclaimers=[RECORD_NOTE, SYNTHETIC_NOTE],
    )


def _requirements_turn(db: Session, ctx: TurnContext, intent: str, procedure_code: str) -> PipelineResult:
    result = ctx.executor.execute("get_required_documents", {"procedure_code": procedure_code})
    if result.status == "NOT_FOUND":
        return PipelineResult(
            intent,
            "INSUFFICIENT_EVIDENCE",
            "INSUFFICIENT",
            "No configured documentation requirements are available for that procedure, so I can't "
            "list them. A support agent can help.",
            escalation_reason="NO_ADEQUATE_ANSWER",
            actions=[case_offer(ctx, "NO_ADEQUATE_ANSWER", "DOCUMENT_ISSUE")],
            gap_topic=gap_topic(ctx.question),
            tool_results=[result],
        )
    if result.status == "PERMISSION_DENIED":
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "Your account can't look up documentation requirements.",
            tool_results=[result],
        )
    if result.status != "SUCCEEDED":
        return _tool_failure(ctx, intent, result, "requirements lookup")

    data = result.data
    cited: list[EvidenceItem] = []
    marker_of: dict[str, str] = {}
    for req in data["requirements"]:
        src = req["source"]
        if src and src["chunk_id"] not in marker_of:
            candidate = _candidate_for_chunk(db, UUID(src["chunk_id"]))
            if candidate is not None:
                marker_of[src["chunk_id"]] = f"C{len(cited) + 1}"
                cited.append(EvidenceItem(marker_of[src["chunk_id"]], candidate))
    lines = []
    for req in data["requirements"]:
        marker = marker_of.get(req["source"]["chunk_id"]) if req["source"] else None
        suffix = f" [{marker}]" if marker else " (source passage not verified)"
        lines.append(
            f"- {req['requirement_code']}: {req['description']}"
            + ("" if req["is_mandatory"] else " (optional)")
            + suffix
        )
    text = (
        f"Configured documentation requirements for {data['display_name']} ({data['procedure_code']}, "
        f"requirement set v{data['version']}):\n" + "\n".join(lines) + f"\n{data['disclaimer']}"
    )
    return PipelineResult(
        intent,
        "TOOL_RESULT",
        "SUPPORTED" if data["evidence_status"] == "SUPPORTED" else "INSUFFICIENT",
        text,
        cited=cited,
        citation_check="PASSED" if cited else "NOT_APPLICABLE",
        tool_results=[result],
        records=[{"kind": "requirements", "data": data}],
        actions=[
            Action(
                "START_READINESS_CHECK",
                "Check my documents against these",
                False,
                ctx.can_check_readiness,
                {"procedure_code": data["procedure_code"]},
            )
        ],
        disclaimers=[SYNTHETIC_NOTE],
    )


def _case_turn(ctx: TurnContext, intent: str) -> PipelineResult:
    result = ctx.executor.execute(
        "create_support_case",
        {
            "category": _case_category(intent, ctx.history),
            "summary": _case_summary(ctx.question, ctx.history),
            "escalation_reason": "USER_REQUESTED_HUMAN",
        },
    )
    return _case_result(intent, result)


def _case_result(intent: str, result: ToolResult) -> PipelineResult:
    if result.status == "PERMISSION_DENIED":
        return PipelineResult(
            intent,
            "UNSUPPORTED_REQUEST",
            "NOT_APPLICABLE",
            "Your account can't create support cases from the assistant.",
            tool_results=[result],
        )
    if result.status != "CONFIRMATION_REQUIRED":
        return PipelineResult(
            intent,
            "ERROR",
            "NOT_APPLICABLE",
            "I couldn't prepare a support case. Nothing was created. You can create one from the Support cases screen.",
            tool_results=[result],
        )
    proposal = result.data
    action = Action(
        "CREATE_SUPPORT_CASE",
        "Create support case",
        requires_confirmation=True,
        available=True,
        prefill={
            k: proposal[k]
            for k in ("category", "summary", "escalation_reason", "related_session_id", "idempotency_key")
        },
    )
    return PipelineResult(
        intent,
        "TOOL_RESULT",
        "NOT_APPLICABLE",
        "I've prepared a support case for a support agent. It has not been created yet: review the "
        'details and choose "Create support case" to submit it.',
        escalation_reason=proposal["escalation_reason"],
        actions=[action],
        tool_results=[result],
        records=[{"kind": "support_case_proposal", "data": proposal}],
    )


def _with_question(ctx: TurnContext, question: str) -> TurnContext:
    return TurnContext(
        question,
        ctx.history,
        ctx.scope,
        ctx.executor,
        ctx.session_id,
        ctx.can_view_claims,
        ctx.can_create_cases,
        ctx.can_read_cases,
        ctx.can_check_readiness,
    )


def _candidate_for_chunk(db: Session, chunk_id: UUID) -> Candidate | None:
    row = db.execute(
        select(DocumentChunk, KnowledgeDocument).join(KnowledgeDocument).where(DocumentChunk.id == chunk_id)
    ).first()
    if row is None:
        return None
    chunk, doc = row
    return Candidate(
        chunk_id=chunk.id,
        document_id=doc.id,
        document_key=doc.document_key,
        title=doc.title,
        version=doc.version,
        document_type=doc.document_type,
        effective_date=doc.effective_date,
        plan_id=doc.plan_id,
        lifecycle_status=doc.lifecycle_status,
        section_heading=chunk.section_heading,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        content=chunk.content,
        similarity=1.0,
        keyword_rank=0.0,
        fused=1.0,
    )


# --- retrieval-grounded answers --------------------------------------------------------------------


def _retrieve(db, settings, embedder, ctx: TurnContext):
    query = ctx.question
    if ctx.history and is_follow_up(ctx.question):
        last_user = next((text for role, text in reversed(ctx.history) if role == "user"), "")
        query = f"{last_user} {ctx.question}".strip()
    started = time.perf_counter()
    vector = embedder.embed_query(query)
    candidates = search(db, query_text=query, query_vector=vector, model_id=embedder.model_id, scope=ctx.scope)
    assessment = assess(
        candidates,
        min_relevance=settings.rag_min_relevance,
        top_k=settings.rag_top_k,
        char_budget=settings.rag_context_char_budget,
    )
    return assessment, int((time.perf_counter() - started) * 1000)


def _rag_turn(db, settings, embedder, generator, ctx: TurnContext, intent: str) -> PipelineResult:
    assessment, retrieval_ms = _retrieve(db, settings, embedder, ctx)
    if assessment.state is not EvidenceState.SUPPORTED:
        return _insufficient(ctx, intent, assessment.state, retrieval_ms)
    items = [EvidenceItem(f"C{i + 1}", c) for i, c in enumerate(assessment.evidence)]
    started = time.perf_counter()
    generation = generator.generate(ctx.question, items, ctx.history)
    result = _finish(ctx, intent, generation, items, [], retrieval_ms, int((time.perf_counter() - started) * 1000))
    return result


def _finish(
    ctx: TurnContext,
    intent: str,
    generation: Generation,
    items: list[EvidenceItem],
    tool_results: list[ToolResult],
    retrieval_ms: int,
    generation_ms: int,
) -> PipelineResult:
    disclaimers = [SYNTHETIC_NOTE] + ([generation.disclaimer] if generation.disclaimer else [])
    records = _records_from(tool_results)
    succeeded = [r for r in tool_results if r.status == "SUCCEEDED"]
    proposals = [r for r in tool_results if r.status == "CONFIRMATION_REQUIRED"]

    if proposals:  # a case was proposed: the server writes the user-facing wording, not the model
        result = _case_result(intent, proposals[-1])
        result.tool_results = tool_results
        return result
    if not generation.evidence_sufficient and not succeeded:
        res = _insufficient(ctx, intent, EvidenceState.LOW_RELEVANCE, retrieval_ms)
        res.generation_ms, res.tool_results = generation_ms, tool_results
        return res

    check = citation_check.validate(generation.answer_text, generation.citations_used, {i.marker for i in items})
    if check.status == "ALL_INVALID_DOWNGRADED" and not succeeded:
        res = _insufficient(ctx, intent, EvidenceState.LOW_RELEVANCE, retrieval_ms)
        res.citation_check, res.generation_ms, res.tool_results = check.status, generation_ms, tool_results
        return res

    text = check.text
    if _FALSE_SUCCESS.search(text):
        # The model may never claim a case was created or something approved: chat never does either.
        logger.warning("model_claimed_unperformed_action")
        text = "I can't confirm any submitted request or approval from this conversation. " + (
            "Here is what the records show:\n" + _record_lines(records) if records else ""
        )
    by_marker = {i.marker: i for i in items}
    cited_markers = [m for m in check.valid_markers if m in by_marker]
    llm_conflict = (
        generation.conflict_detected
        and len({by_marker[m].candidate.document_key for m in generation.conflict_markers if m in by_marker}) >= 2
    )
    pairs = money_conflicts([(i.marker, i.candidate.document_key, i.candidate.content) for i in items])

    def different_plans(m_a: str, m_b: str) -> bool:
        # Two plans' guides legitimately state different amounts; that is not a contradiction.
        pa, pb = by_marker[m_a].candidate.plan_id, by_marker[m_b].candidate.plan_id
        return pa is not None and pb is not None and pa != pb

    pairs = [p for p in pairs if (p[0] in cited_markers or p[2] in cited_markers) and not different_plans(p[0], p[2])]
    conflict = llm_conflict or bool(pairs)
    for m_a, s_a, m_b, s_b in pairs[:1]:
        for marker, sentence in ((m_a, s_a), (m_b, s_b)):
            if marker not in cited_markers:
                text += f"\n- Another source says: {sentence} [{marker}]"
                cited_markers.append(marker)
    if conflict:
        text += (
            "\n\nThese sources disagree, so I can't tell you which one applies. A support agent can confirm "
            "the correct information."
        )
    answer_type = "TOOL_RESULT" if succeeded else "DOCUMENT_GROUNDED"
    evidence = "CONFLICTING" if conflict else ("VERIFIED_RECORD" if succeeded and not cited_markers else "SUPPORTED")
    return PipelineResult(
        intent=intent,
        answer_type=answer_type,
        evidence_status=evidence,
        answer_text=text,
        cited=[by_marker[m] for m in cited_markers],
        citation_check=check.status if cited_markers else "NOT_APPLICABLE",
        escalation_reason="CONFLICTING_INFORMATION" if conflict else None,
        actions=[case_offer(ctx, "CONFLICTING_INFORMATION", "KNOWLEDGE_GAP")] if conflict else [],
        disclaimers=disclaimers + ([RECORD_NOTE] if succeeded else []),
        gap_topic=gap_topic(ctx.question) if conflict else None,
        retrieved_document_ids=sorted({str(i.candidate.document_id) for i in items}),
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        tool_results=tool_results,
        records=records,
    )


def _llm_turn(db, settings, embedder, generator, ctx: TurnContext, intent: str) -> PipelineResult:
    """Claude chooses between answering from evidence and requesting tools (executed via ctx.executor)."""
    assessment, retrieval_ms = _retrieve(db, settings, embedder, ctx)
    items = [EvidenceItem(f"C{i + 1}", c) for i, c in enumerate(assessment.evidence)]
    started = time.perf_counter()
    generation = generator.generate_with_tools(ctx.question, items, ctx.history, ctx.executor)
    return _finish(
        ctx,
        intent,
        generation,
        items,
        list(ctx.executor.results),
        retrieval_ms,
        int((time.perf_counter() - started) * 1000),
    )


def _records_from(results: list[ToolResult]) -> list[dict[str, Any]]:
    kinds = {
        "get_claim_status": "claims",
        "get_plan_benefits": "plan_benefits",
        "get_required_documents": "requirements",
    }
    return [
        {"kind": kinds[r.tool_name], "data": r.data}
        for r in results
        if r.status == "SUCCEEDED" and r.tool_name in kinds and r.data is not None
    ]


def _record_lines(records: list[dict[str, Any]]) -> str:
    lines = []
    for rec in records:
        if rec["kind"] == "claims":
            lines += [
                f"- {c['claim_number']}: {STATUS_LABELS.get(c['status'], c['status'])}" for c in rec["data"]["claims"]
            ]
    return "\n".join(lines)


def _insufficient(ctx: TurnContext, intent: str, state: EvidenceState, retrieval_ms: int) -> PipelineResult:
    if state is EvidenceState.OUTDATED_ONLY:
        text = (
            "The only matching information I found is in a document version that has been replaced, so I "
            "can't rely on it. A support agent can confirm the current rules."
        )
    else:
        text = (
            "I couldn't find information about this in the documents available to me, so I can't give a "
            "verified answer. A support agent can look into it."
        )
    return PipelineResult(
        intent=intent,
        answer_type="INSUFFICIENT_EVIDENCE",
        evidence_status="INSUFFICIENT",
        answer_text=text,
        escalation_reason="NO_ADEQUATE_ANSWER",
        actions=[case_offer(ctx, "NO_ADEQUATE_ANSWER", "KNOWLEDGE_GAP")],
        gap_topic=gap_topic(ctx.question),
        retrieval_ms=retrieval_ms,
    )


def excerpt(candidate: Candidate, limit: int = 400) -> str:
    text = " ".join(candidate.content.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut + "…"
