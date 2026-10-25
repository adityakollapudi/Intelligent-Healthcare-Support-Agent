"""Documentation-readiness checklists (doc 02 Workflow D, doc 06 §3.7, doc 07 §6).

Requirements come from requirements_service.load_verified_set (the same source as the Phase 5 tool),
fields from the exact analysis job of each submitted document, and statuses from the deterministic
rules in readiness_rules. The reviewer summary is the doc 07 §6.5 template filled from the persisted
items; no model is involved, so its counts can't drift from the checklist."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.cases import escalation
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.documents import readiness_rules as rules
from app.models import (
    AuthorizationChecklist,
    AuthorizationChecklistItem,
    ChecklistDocument,
    DocumentProcessingJob,
    ExtractedField,
    KnowledgeDocument,
    PaRequirement,
    PaRequirementSet,
    UploadedDocument,
)
from app.models.enums import AuditOutcome
from app.schemas.readiness import (
    DISCLAIMER,
    DISCLAIMER_VERSION,
    ChecklistDetail,
    ChecklistDocumentRef,
    ChecklistItem,
    ChecklistPage,
    ChecklistSummary,
    Counts,
    EscalationOffer,
    ItemEvidence,
    ReadinessRequest,
    RequirementSetSummary,
)
from app.services import document_service, requirements_service
from app.services.audit_service import AuditService

_USABLE_JOBS = ("COMPLETED", "COMPLETED_WITH_WARNINGS")


class DocumentNotAnalyzedError(AppError):
    status_code = 409
    code = "DOCUMENT_NOT_ANALYZED"
    message = "Every document must have a finished analysis before a checklist can be created."


class NoApplicableRequirementsError(AppError):
    status_code = 422
    code = "NO_APPLICABLE_REQUIREMENTS"
    message = "The requirement set has no requirements to evaluate."


def list_requirement_sets(db: Session) -> list[RequirementSetSummary]:
    return [RequirementSetSummary(procedure_code=s.procedure_code, display_name=s.display_name, version=s.version)
            for s in requirements_service.active_sets(db)]


def create_checklist(db: Session, audit: AuditService, principal: Principal, body: ReadinessRequest) -> ChecklistDetail:
    if principal.organization_id is None:
        raise ForbiddenError()
    docs = [document_service.owned_document(db, audit, principal, doc_id) for doc_id in body.document_ids]
    jobs: dict[UUID, DocumentProcessingJob] = {}
    not_ready = []
    for doc in docs:
        job = document_service.latest_job(db, doc.id)
        if job is None or job.status not in _USABLE_JOBS:
            not_ready.append({"field": "document_ids", "issue": f"{doc.id}: {job.status if job else 'NOT_ANALYZED'}"})
        else:
            jobs[doc.id] = job
    if not_ready:
        raise DocumentNotAnalyzedError(details=not_ready)

    verified = requirements_service.load_verified_set(db, audit, principal, body.procedure_code)
    if not verified.items:
        raise NoApplicableRequirementsError()

    evidence_docs = [_evidence(doc, jobs[doc.id]) for doc in docs]
    results = [
        (req, rules.evaluate(rules.Requirement(req.requirement_code, req.rule_type, req.rule_params,
                                               source_verified=source is not None), evidence_docs))
        for req, source in verified.items
    ]
    statuses = [r.item_status for _, r in results]
    counts = {s: statuses.count(s) for s in (rules.SATISFIED, rules.MISSING, rules.UNREADABLE, rules.MANUAL)}
    warnings = _warnings(body.procedure_code, evidence_docs, jobs, verified)

    checklist = AuthorizationChecklist(
        created_by_user_id=principal.user_id,
        organization_id=principal.organization_id,
        requirement_set_id=verified.req_set.id,
        requirement_source_document_id=verified.source_doc.id,
        readiness_status=rules.overall(statuses),
        review_state="NOT_SUBMITTED",
        satisfied_count=counts[rules.SATISFIED],
        missing_count=counts[rules.MISSING],
        unreadable_count=counts[rules.UNREADABLE],
        manual_review_count=counts[rules.MANUAL],
        provider_note=body.provider_note,
        disclaimer_version=DISCLAIMER_VERSION,
        warnings=warnings,
        rules_version=rules.RULES_VERSION,
    )
    checklist.items = [
        AuthorizationChecklistItem(requirement_id=req.id, item_status=r.item_status,
                                   evidence_field_ids=r.evidence_field_ids, explanation=r.explanation[:500])
        for req, r in results
    ]
    checklist.documents = [
        ChecklistDocument(uploaded_document_id=doc.id, job_id=jobs[doc.id].id) for doc in docs
    ]
    db.add(checklist)
    db.flush()
    detail = _detail(db, checklist)  # built from the rows just written, so summary == persisted items
    checklist.reviewer_summary = detail.reviewer_summary
    audit.add_to_transaction(
        db, "READINESS_CHECKLIST_CREATED", AuditOutcome.SUCCESS, actor=principal,
        resource_type="authorization_checklist", resource_ref=str(checklist.id),
        metadata={"procedure_code": verified.req_set.procedure_code, "readiness_status": checklist.readiness_status,
                  "satisfied_count": checklist.satisfied_count, "missing_count": checklist.missing_count,
                  "unreadable_count": checklist.unreadable_count,
                  "manual_review_count": checklist.manual_review_count, "document_count": len(docs)},
    )
    db.commit()
    return detail


def _evidence(doc: UploadedDocument, job: DocumentProcessingJob) -> rules.DocumentEvidence:
    return rules.DocumentEvidence(
        document_id=doc.id,
        filename=doc.original_filename,
        detected_type=job.detected_document_type or "UNRECOGNIZED",
        fields={
            f.field_name: rules.FieldEvidence(f.id, doc.id, doc.original_filename, f.field_name, f.validation_status,
                                              f.normalized_value, f.raw_value, f.source_page)
            for f in job.fields
        },
    )


def _warnings(code: str, docs: list[rules.DocumentEvidence], jobs: dict[UUID, DocumentProcessingJob],
              verified: requirements_service.VerifiedSet) -> list[str]:
    out = []
    for d in docs:
        stated = d.fields.get("procedure_code")
        if stated and stated.validation_status == "VALID" and stated.normalized_value != code:
            out.append(f"PROCEDURE_CODE_MISMATCH: {d.filename} states {stated.normalized_value}")
        job = jobs[d.document_id]
        if job.status == "COMPLETED_WITH_WARNINGS":
            out.append(f"DOCUMENT_HAS_WARNINGS: {d.filename} ({job.warning_count})")
    if any(source is None for _, source in verified.items):
        out.append("REQUIREMENT_SOURCE_PARTIALLY_VERIFIED")
    return out


def _counts(c: AuthorizationChecklist) -> Counts:
    return Counts(SATISFIED=c.satisfied_count, MISSING=c.missing_count, UNREADABLE=c.unreadable_count,
                  NEEDS_MANUAL_REVIEW=c.manual_review_count)


def _detail(db: Session, c: AuthorizationChecklist) -> ChecklistDetail:
    req_set = db.get(PaRequirementSet, c.requirement_set_id)
    source_doc = db.get(KnowledgeDocument, c.requirement_source_document_id) if c.requirement_source_document_id \
        else None
    reqs = {r.id: r for r in db.scalars(select(PaRequirement).where(
        PaRequirement.requirement_set_id == c.requirement_set_id))}
    field_ids = [fid for item in c.items for fid in item.evidence_field_ids]
    fields = {f.id: f for f in db.scalars(select(ExtractedField).where(ExtractedField.id.in_(field_ids)))} \
        if field_ids else {}
    job_doc = {cd.job_id: cd.uploaded_document_id for cd in c.documents}
    jobs = {j.id: j for j in db.scalars(select(DocumentProcessingJob).where(
        DocumentProcessingJob.id.in_(list(job_doc))))}
    docs = {d.id: d for d in db.scalars(select(UploadedDocument).where(
        UploadedDocument.id.in_(list(job_doc.values()))))}

    items = []
    for item in sorted(c.items, key=lambda i: reqs[i.requirement_id].display_order):
        req = reqs[item.requirement_id]
        items.append(ChecklistItem(
            requirement_code=req.requirement_code,
            description=req.description,
            rule_type=req.rule_type,
            is_mandatory=req.is_mandatory,
            item_status=item.item_status,
            explanation=item.explanation,
            evidence=[
                ItemEvidence(field_id=f.id, document_id=job_doc[f.job_id], field_name=f.field_name,
                             validation_status=f.validation_status, normalized_value=f.normalized_value,
                             source_page=f.source_page)
                for fid in item.evidence_field_ids if (f := fields.get(fid)) is not None and f.job_id in job_doc
            ],
            # Located in the exact source-document version recorded when the checklist was created.
            requirement_source=requirements_service.locate(db, source_doc, req.source_phrase) if source_doc else None,
        ))
    documents = [
        ChecklistDocumentRef(document_id=cd.uploaded_document_id, original_filename=docs[cd.uploaded_document_id]
                             .original_filename, job_id=cd.job_id,
                             detected_document_type=jobs[cd.job_id].detected_document_type)
        for cd in c.documents
    ]
    detail = ChecklistDetail(
        checklist_id=c.id,
        procedure_code=req_set.procedure_code,
        display_name=req_set.display_name,
        requirement_set_version=req_set.version,
        requirement_source_document=f"{source_doc.title} v{source_doc.version}" if source_doc else None,
        rules_version=c.rules_version,
        readiness_status=c.readiness_status,
        review_state=c.review_state,
        counts=_counts(c),
        documents=documents,
        items=items,
        warnings=list(c.warnings or []),
        provider_note=c.provider_note,
        reviewer_summary=c.reviewer_summary or "",
        created_at=c.created_at,
    )
    if not c.reviewer_summary:
        detail.reviewer_summary = reviewer_summary(detail, source_doc.effective_date if source_doc else None)
    decision = escalation.readiness_decision(c.readiness_status)
    if decision is not None and c.review_state == "NOT_SUBMITTED":
        attention = [f"{i.requirement_code} {i.item_status}" for i in items if i.item_status != "SATISFIED"]
        detail.escalation_offer = EscalationOffer(
            category=decision.category, escalation_reason=decision.escalation_reason,
            summary=escalation.readiness_summary(req_set.procedure_code, c.readiness_status,
                                                 detail.counts.model_dump(), attention),
            related_checklist_id=c.id, document_ids=[d.document_id for d in documents],
        )
    return detail


def reviewer_summary(d: ChecklistDetail, effective: date | None) -> str:
    """doc 07 §6.5 template. Counts are recomputed from the items (they must match the stored counts)."""
    tally = {s: sum(i.item_status == s for i in d.items) for s in ("SATISFIED", "MISSING", "UNREADABLE",
                                                                   "NEEDS_MANUAL_REVIEW")}
    attention = [i for i in d.items if i.item_status != "SATISFIED"]
    lines = [
        "DRAFT — Documentation readiness summary (prepared by IHSA prototype; synthetic data)",
        f"Procedure: {d.display_name} ({d.procedure_code}), requirement set v{d.requirement_set_version}",
        "Documents reviewed: " + ", ".join(
            f"{doc.original_filename} ({doc.detected_document_type or 'UNRECOGNIZED'})" for doc in d.documents),
        f"Result: {d.readiness_status} — {tally['SATISFIED']} satisfied, {tally['MISSING']} missing, "
        f"{tally['UNREADABLE']} unreadable, {tally['NEEDS_MANUAL_REVIEW']} need manual review",
    ]
    if attention:
        lines.append("Items needing attention:")
        lines += [f" - {i.requirement_code} {i.description}: {i.item_status} — {i.explanation}" for i in attention]
    if d.warnings:
        lines.append("Warnings: " + "; ".join(d.warnings))
    lines.append(f"Requirement source: {d.requirement_source_document or 'not available'}, effective "
                 f"{effective.isoformat() if effective else 'not stated'}")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def list_checklists(db: Session, principal: Principal, limit: int = 50) -> ChecklistPage:
    rows = db.scalars(
        select(AuthorizationChecklist)
        .where(AuthorizationChecklist.created_by_user_id == principal.user_id)
        .order_by(AuthorizationChecklist.created_at.desc())
        .limit(limit)
    ).all()
    codes = {s.id: s.procedure_code for s in db.scalars(select(PaRequirementSet).where(
        PaRequirementSet.id.in_({r.requirement_set_id for r in rows})))} if rows else {}
    return ChecklistPage(items=[
        ChecklistSummary(checklist_id=r.id, procedure_code=codes[r.requirement_set_id],
                         readiness_status=r.readiness_status, review_state=r.review_state, counts=_counts(r),
                         created_at=r.created_at)
        for r in rows
    ])


def get_checklist(db: Session, audit: AuditService, principal: Principal, checklist_id: UUID) -> ChecklistDetail:
    c = db.get(AuthorizationChecklist, checklist_id)
    from app.services import support_case_service  # local import: avoids a service import cycle

    if c is not None and c.created_by_user_id != principal.user_id and support_case_service.case_linked(
            db, principal, checklist_id=checklist_id):
        audit.record("READINESS_CHECKLIST_VIEWED", AuditOutcome.SUCCESS, actor=principal,
                     resource_type="authorization_checklist", resource_ref=str(checklist_id))
        return _detail(db, c)
    if c is None or c.created_by_user_id != principal.user_id:
        audit.record("ACCESS_DENIED", AuditOutcome.DENIED, actor=principal, resource_type="authorization_checklist",
                     resource_ref=str(checklist_id), reason_code="NOT_EXISTS" if c is None else "NOT_OWNER")
        raise NotFoundError()
    return _detail(db, c)
