"""The plan documents a customer may read, so they can check the assistant's answers themselves.

Uses the same access rule as retrieval (audience, plus own plan for members), and only current versions.
The text comes from the indexed passages, so it's exactly what the assistant answers from."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.authz.dependencies import Principal
from app.core.exceptions import NotFoundError
from app.models import KnowledgeDocument, Plan
from app.models.enums import AuditOutcome
from app.rag.retrieval import RetrievalScope
from app.schemas.knowledge import PlanDocumentDetail, PlanDocumentSection, PlanDocumentSummary
from app.services.audit_service import AuditService

_MIN_OVERLAP = 20  # shortest repeated text treated as chunk overlap


def _permitted(principal: Principal):
    scope = RetrievalScope.for_user(principal.role, principal.plan_id)
    query = select(KnowledgeDocument).where(
        KnowledgeDocument.lifecycle_status == "ACTIVE",
        KnowledgeDocument.ingestion_status == "INGESTED",
        KnowledgeDocument.audience.overlap(scope.audiences),
    )
    if scope.restrict_plan:
        query = query.where(or_(KnowledgeDocument.plan_id.is_(None), KnowledgeDocument.plan_id == scope.plan_id))
    return query


def _summary(doc: KnowledgeDocument, plans: dict[UUID, str], principal: Principal) -> PlanDocumentSummary:
    return PlanDocumentSummary(
        document_id=doc.id, title=doc.title, version=doc.version, document_type=doc.document_type,
        effective_date=doc.effective_date, plan_name=plans.get(doc.plan_id) if doc.plan_id else None,
        is_my_plan=doc.plan_id is not None and doc.plan_id == principal.plan_id,
    )


def _plan_names(db: Session) -> dict[UUID, str]:
    return {plan.id: plan.plan_name for plan in db.scalars(select(Plan))}


def list_documents(db: Session, principal: Principal) -> list[PlanDocumentSummary]:
    plans = _plan_names(db)
    items = [_summary(d, plans, principal) for d in db.scalars(_permitted(principal))]
    return sorted(items, key=lambda d: (not d.is_my_plan, d.title))  # the customer's own plan first


def _append(text: str, chunk: str) -> str:
    """Joins neighbouring passages, dropping the words they share (chunks overlap)."""
    for size in range(min(len(text), len(chunk)), _MIN_OVERLAP - 1, -1):
        if text.endswith(chunk[:size]):
            return text + chunk[size:]
    return f"{text}\n\n{chunk}"


def get_document(db: Session, audit: AuditService, principal: Principal, document_id: UUID) -> PlanDocumentDetail:
    doc = db.scalars(_permitted(principal).where(KnowledgeDocument.id == document_id)
                     .options(selectinload(KnowledgeDocument.chunks))).first()
    if doc is None:  # same answer for "doesn't exist" and "not yours"
        audit.record("ACCESS_DENIED", AuditOutcome.DENIED, actor=principal, resource_type="knowledge_document",
                     resource_ref=str(document_id), reason_code="NOT_PERMITTED")
        raise NotFoundError()
    sections: list[PlanDocumentSection] = []
    for chunk in sorted(doc.chunks, key=lambda c: c.chunk_index):
        last = sections[-1] if sections else None
        if last and last.heading == chunk.section_heading and last.page == chunk.page_start:
            last.text = _append(last.text, chunk.content)
            last.chunk_ids.append(chunk.id)
        else:
            sections.append(PlanDocumentSection(heading=chunk.section_heading, page=chunk.page_start,
                                                text=chunk.content, chunk_ids=[chunk.id]))
    audit.record("PLAN_DOCUMENT_VIEWED", AuditOutcome.SUCCESS, actor=principal, resource_type="knowledge_document",
                 resource_ref=str(doc.id))
    summary = _summary(doc, _plan_names(db), principal)
    return PlanDocumentDetail(**summary.model_dump(), sections=sections, retrieved_at=datetime.now(UTC))
