"""Documentation-requirement lookups (FR-016). The structured requirement set is the source of truth;
each requirement is linked to the passage of the ACTIVE source document that states it, and that link
is verified (the stored phrase must appear in the passage) every time it is served."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.authz.dependencies import Principal
from app.core.exceptions import AppError, NotFoundError
from app.models import DocumentChunk, KnowledgeDocument, PaRequirementSet
from app.models.enums import AuditOutcome
from app.rag.retrieval import ROLE_AUDIENCES
from app.schemas.requirements import RequirementItem, RequirementSetResponse, RequirementSource
from app.services.audit_service import AuditService

PROCEDURE_CODE = re.compile(r"\bSYN-PROC-[A-Z0-9-]{2,30}\b", re.I)


class AmbiguousProcedureError(AppError):
    status_code = 422
    code = "AMBIGUOUS_PROCEDURE"
    message = "More than one configured procedure matches. Please choose one."

    def __init__(self, candidates: list[str]) -> None:
        super().__init__(details=[{"field": "procedure", "issue": "ambiguous", "allowed": candidates}])
        self.candidates = candidates


@dataclass(frozen=True)
class Match:
    procedure_code: str
    display_name: str


def _active_sets(db: Session) -> list[PaRequirementSet]:
    return list(db.scalars(select(PaRequirementSet).where(PaRequirementSet.is_active)))


def match_procedures(db: Session, text: str) -> list[Match]:
    """Deterministic matching: an explicit procedure code, else configured aliases contained in the
    text (case-insensitive, longest alias wins per set). Never guesses beyond the configured aliases."""
    sets = _active_sets(db)
    code = PROCEDURE_CODE.search(text)
    if code:
        wanted = code.group(0).upper()
        return [Match(s.procedure_code, s.display_name) for s in sets if s.procedure_code == wanted]
    lowered = " ".join(text.lower().split())
    return [Match(s.procedure_code, s.display_name) for s in sets if any(alias in lowered for alias in s.aliases)]


def get_requirements(
    db: Session, audit: AuditService, principal: Principal, *, procedure_code: str | None, procedure_text: str | None
) -> RequirementSetResponse:
    if procedure_code:
        matches = [m for m in match_procedures(db, procedure_code) if m.procedure_code == procedure_code.upper()]
    else:
        matches = match_procedures(db, procedure_text or "")
    if len(matches) > 1:
        raise AmbiguousProcedureError([m.procedure_code for m in matches])
    if not matches:
        audit.record(
            "REQUIREMENTS_LOOKUP",
            AuditOutcome.FAILURE,
            actor=principal,
            resource_type="requirement_set",
            resource_ref=(procedure_code or "")[:80] or None,
            reason_code="NOT_FOUND",
        )
        raise NotFoundError("No configured documentation requirements were found for that procedure.")

    req_set = db.scalars(
        select(PaRequirementSet)
        .options(selectinload(PaRequirementSet.requirements))
        .where(PaRequirementSet.procedure_code == matches[0].procedure_code, PaRequirementSet.is_active)
    ).one()
    source_doc = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.document_key == req_set.source_document_key,
            KnowledgeDocument.lifecycle_status == "ACTIVE",
            KnowledgeDocument.ingestion_status == "INGESTED",
            KnowledgeDocument.audience.overlap(ROLE_AUDIENCES.get(principal.role, [])),
        )
    ).first()
    if source_doc is None:
        # Doc 05 §2.12: a set whose source document isn't available (or permitted) is not served.
        audit.record(
            "REQUIREMENTS_LOOKUP",
            AuditOutcome.FAILURE,
            actor=principal,
            resource_type="requirement_set",
            resource_ref=req_set.procedure_code,
            reason_code="SOURCE_UNAVAILABLE",
        )
        raise NotFoundError("No configured documentation requirements were found for that procedure.")

    items = [
        RequirementItem(
            requirement_code=r.requirement_code,
            description=r.description,
            is_mandatory=r.is_mandatory,
            rule_type=r.rule_type,
            source=_locate(db, source_doc, r.source_phrase),
        )
        for r in req_set.requirements
    ]
    verified = all(i.source is not None for i in items)
    audit.record(
        "REQUIREMENTS_LOOKUP",
        AuditOutcome.SUCCESS,
        actor=principal,
        resource_type="requirement_set",
        resource_ref=req_set.procedure_code,
        metadata={"result_count": len(items)},
    )
    return RequirementSetResponse(
        procedure_code=req_set.procedure_code,
        display_name=req_set.display_name,
        version=req_set.version,
        source_document_title=source_doc.title,
        source_document_version=source_doc.version,
        evidence_status="SUPPORTED" if verified else "PARTIALLY_SUPPORTED",
        requirements=items,
    )


def _locate(db: Session, doc: KnowledgeDocument, phrase: str) -> RequirementSource | None:
    """The chunk of `doc` that literally contains `phrase`, or None (never a nearest guess)."""
    chunk = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id, func.strpos(func.lower(DocumentChunk.content), phrase.lower()) > 0)
        .order_by(DocumentChunk.chunk_index)
        .limit(1)
    ).first()
    if chunk is None:
        return None
    return RequirementSource(
        document_id=doc.id,
        document_title=doc.title,
        document_version=doc.version,
        effective_date=doc.effective_date,
        section_heading=chunk.section_heading,
        page_start=chunk.page_start,
        chunk_id=chunk.id,
        excerpt=phrase,
    )
