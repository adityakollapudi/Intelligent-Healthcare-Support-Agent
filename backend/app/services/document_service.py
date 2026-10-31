"""Document intake, retrieval and analysis requests (doc 02 Workflow C, doc 06 §3.6).

Ownership is always the authenticated principal. Other users' documents (and expired or deleted
ones) are reported as not found, with an ACCESS_DENIED audit event, so IDs can't be probed."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError, RateLimitedError
from app.documents import pipeline
from app.documents.extraction import JobTimeoutError, PdfParseError, extract_pages
from app.documents.ocr import OcrEngine, get_ocr_engine
from app.documents.storage import FileStorage, StorageError, get_storage
from app.documents.validation import validate_upload
from app.models import DocumentProcessingJob, UploadedDocument
from app.models.document import TERMINAL_JOB_STATUSES
from app.models.enums import AuditOutcome
from app.schemas.document import (
    AnalyzeResponse,
    DocumentDetail,
    DocumentField,
    DocumentPage,
    DocumentSummary,
    JobDetail,
    JobSummary,
    PageDetail,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class JobAlreadyRunningError(AppError):
    status_code = 409
    code = "JOB_ALREADY_RUNNING"
    message = "This document is already being analyzed."


class UploadFailedError(AppError):
    status_code = 500
    code = "UPLOAD_FAILED"
    message = "The document couldn't be stored. Nothing was saved; please try again."


# --- mapping --------------------------------------------------------------------------------------


def _job_summary(job: DocumentProcessingJob) -> JobSummary:
    return JobSummary(
        job_id=job.id,
        status=job.status,
        detected_document_type=job.detected_document_type,
        pages_text_layer=job.pages_text_layer,
        pages_ocr=job.pages_ocr,
        ocr_mean_confidence=float(job.ocr_mean_confidence) if job.ocr_mean_confidence is not None else None,
        warning_count=job.warning_count,
        error_code=job.error_code,
        error_detail=job.error_detail,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _job_detail(job: DocumentProcessingJob) -> JobDetail:
    return JobDetail(
        **_job_summary(job).model_dump(),
        extraction_schema_version=job.extraction_schema_version,
        pipeline_version=job.pipeline_version,
        warnings=list(job.warnings or []),
        pages=[PageDetail(**p) for p in job.page_details or []],
        fields=[
            DocumentField(
                field_id=f.id,
                field_name=f.field_name,
                raw_value=f.raw_value,
                normalized_value=f.normalized_value,
                validation_status=f.validation_status,
                validation_message=f.validation_message,
                source_page=f.source_page,
                extraction_method=f.extraction_method,
                confidence=float(f.confidence) if f.confidence is not None else None,
            )
            for f in job.fields
        ],
    )


def latest_job(db: Session, document_id: UUID) -> DocumentProcessingJob | None:
    return db.scalars(
        select(DocumentProcessingJob)
        .where(DocumentProcessingJob.uploaded_document_id == document_id)
        .order_by(DocumentProcessingJob.created_at.desc(), DocumentProcessingJob.id.desc())
        .limit(1)
    ).first()


def _summary(db: Session, doc: UploadedDocument) -> DocumentSummary:
    job = latest_job(db, doc.id)
    return DocumentSummary(
        document_id=doc.id,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        page_count=doc.page_count,
        declared_purpose=doc.declared_purpose,
        created_at=doc.created_at,
        expires_at=doc.expires_at,
        latest_job=_job_summary(job) if job else None,
    )


def detail(db: Session, doc: UploadedDocument) -> DocumentDetail:
    job = latest_job(db, doc.id)
    summary = _summary(db, doc).model_dump(exclude={"latest_job"})
    return DocumentDetail(**summary, latest_job=_job_detail(job) if job else None)


# --- operations -----------------------------------------------------------------------------------


def _usable(doc: UploadedDocument | None, now: datetime) -> bool:
    return doc is not None and doc.deleted_at is None and doc.expires_at > now


def owned_document(db: Session, audit: AuditService, principal: Principal, document_id: UUID,
                   *, for_update: bool = False) -> UploadedDocument:
    query = select(UploadedDocument).where(UploadedDocument.id == document_id)
    if for_update:
        query = query.with_for_update()
    doc = db.scalars(query).first()
    if not _usable(doc, datetime.now(UTC)) or doc.owner_user_id != principal.user_id:
        reason = "NOT_EXISTS" if doc is None else ("NOT_OWNER" if doc.owner_user_id != principal.user_id
                                                   else "NOT_EXISTS")
        audit.record("ACCESS_DENIED", AuditOutcome.DENIED, actor=principal, resource_type="uploaded_document",
                     resource_ref=str(document_id), reason_code=reason)
        raise NotFoundError()
    return doc


def read_own_documents(db: Session, principal: Principal, filename_contains: str | None = None,
                       *, document_ids: list[UUID] | None = None, storage: FileStorage | None = None,
                       ocr: OcrEngine | None = None) -> list[dict]:
    """Page text of the caller's usable uploads, newest first, for one chat answer. The text is read
    from the private file each time and held in memory only (no extracted text is ever persisted)."""
    settings = get_settings()
    query = (select(UploadedDocument)
             .where(UploadedDocument.owner_user_id == principal.user_id, UploadedDocument.deleted_at.is_(None),
                    UploadedDocument.expires_at > datetime.now(UTC))
             .order_by(UploadedDocument.created_at.desc())
             .limit(settings.chat_max_documents_read))
    wanted = (filename_contains or "").lower()
    files = storage or get_storage()
    engine = ocr or get_ocr_engine()
    documents = []
    for doc in db.scalars(query):
        if (wanted and wanted not in doc.original_filename.lower()) or (document_ids and doc.id not in document_ids):
            continue
        deadline = time.monotonic() + settings.job_timeout_seconds
        try:
            pages = extract_pages(files.read(doc.storage_key), doc.mime_type, settings, engine, deadline)
        except (StorageError, PdfParseError, JobTimeoutError):
            pages = []
        documents.append({
            "document_id": doc.id,
            "filename": doc.original_filename,
            "pages": [{"page_number": p.page_number, "readable": p.readable, "text": p.text} for p in pages],
        })
    return documents


def upload(
    db: Session,
    audit: AuditService,
    settings: Settings,
    storage: FileStorage,
    principal: Principal,
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    declared_purpose: str | None,
) -> tuple[DocumentSummary, bool]:
    """Returns (document, created). created=False: the caller already uploaded this exact file."""
    since = datetime.now(UTC) - timedelta(hours=1)
    recent = db.scalar(
        select(func.count()).select_from(UploadedDocument)
        .where(UploadedDocument.owner_user_id == principal.user_id, UploadedDocument.created_at >= since)
    )
    if recent >= settings.document_uploads_per_hour:
        raise RateLimitedError("Too many uploads. Please try again later.", headers={"Retry-After": "600"})

    try:
        checked = validate_upload(filename, content_type, data, settings)
    except AppError as exc:
        issue = exc.details[0]["issue"] if exc.details else exc.code
        audit.record("DOCUMENT_UPLOAD_REJECTED", AuditOutcome.FAILURE, actor=principal,
                     resource_type="uploaded_document", reason_code=str(issue)[:50],
                     metadata={"mime_type": (content_type or "")[:60], "size_bytes": len(data)})
        raise

    digest = hashlib.sha256(data).hexdigest()
    now = datetime.now(UTC)
    existing = db.scalars(
        select(UploadedDocument).where(
            UploadedDocument.owner_user_id == principal.user_id,
            UploadedDocument.content_sha256 == digest,
            UploadedDocument.deleted_at.is_(None),
            UploadedDocument.expires_at > now,
        )
    ).first()
    if existing is not None:
        return _summary(db, existing), False

    key = storage.new_key()
    try:
        storage.save(key, data)
    except StorageError as exc:
        logger.error("document_store_failed", extra={"error_type": str(exc)})
        raise UploadFailedError() from None
    doc = UploadedDocument(
        owner_user_id=principal.user_id,
        original_filename=checked.display_name,
        storage_key=key,
        mime_type=checked.mime_type,
        size_bytes=len(data),
        page_count=checked.page_count,
        content_sha256=digest,
        declared_purpose=declared_purpose,
        expires_at=now + timedelta(days=settings.document_retention_days),
    )
    try:
        db.add(doc)
        db.flush()
        audit.add_to_transaction(db, "DOCUMENT_UPLOADED", AuditOutcome.SUCCESS, actor=principal,
                                 resource_type="uploaded_document", resource_ref=str(doc.id),
                                 metadata={"mime_type": checked.mime_type, "size_bytes": len(data)})
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        storage.delete(key)  # no orphan file without its row
        logger.error("document_row_failed", extra={"error_type": type(exc).__name__})
        raise UploadFailedError() from None
    db.refresh(doc)
    return _summary(db, doc), True


def list_documents(db: Session, principal: Principal, limit: int = 50) -> DocumentPage:
    now = datetime.now(UTC)
    docs = db.scalars(
        select(UploadedDocument)
        .where(UploadedDocument.owner_user_id == principal.user_id, UploadedDocument.deleted_at.is_(None),
               UploadedDocument.expires_at > now)
        .order_by(UploadedDocument.created_at.desc())
        .limit(limit)
    ).all()
    return DocumentPage(items=[_summary(db, d) for d in docs])


def get_document(db: Session, audit: AuditService, principal: Principal, document_id: UUID) -> DocumentDetail:
    from app.services import support_case_service  # local import: avoids a service import cycle

    doc = db.get(UploadedDocument, document_id)
    if (doc is not None and doc.owner_user_id != principal.user_id and _usable(doc, datetime.now(UTC))
            and support_case_service.case_linked(db, principal, document_id=document_id)):
        # The assigned agent of a case linking this document (documents:read:case_linked, doc 06 §3.6).
        audit.record("DOCUMENT_VIEWED", AuditOutcome.SUCCESS, actor=principal, resource_type="uploaded_document",
                     resource_ref=str(document_id))
        return detail(db, doc)
    return detail(db, owned_document(db, audit, principal, document_id))


def request_analysis(db: Session, audit: AuditService, settings: Settings, principal: Principal,
                     document_id: UUID) -> AnalyzeResponse:
    """Creates a QUEUED job; the caller schedules pipeline.run_job. The document row is locked so
    concurrent requests can't both create a job."""
    doc = owned_document(db, audit, principal, document_id, for_update=True)
    job = latest_job(db, doc.id)
    now = datetime.now(UTC)
    if job is not None and job.status not in TERMINAL_JOB_STATUSES:
        stale_after = timedelta(seconds=2 * settings.job_timeout_seconds)
        if now - job.created_at < stale_after:
            db.rollback()
            raise JobAlreadyRunningError(details=[{"field": "job_id", "issue": str(job.id)}])
        # The process that owned this job stopped (e.g. a restart): close it honestly, then re-run.
        pipeline.transition(job, "FAILED")
        job.error_code, job.error_detail, job.completed_at = "TIMEOUT", "Processing was interrupted.", now

    since = now - timedelta(hours=1)
    recent = db.scalar(
        select(func.count()).select_from(DocumentProcessingJob)
        .where(DocumentProcessingJob.requested_by_user_id == principal.user_id,
               DocumentProcessingJob.created_at >= since)
    )
    if recent >= settings.document_analyses_per_hour:
        db.rollback()
        raise RateLimitedError("Too many analysis requests. Please try again later.", headers={"Retry-After": "600"})

    new = DocumentProcessingJob(uploaded_document_id=doc.id, requested_by_user_id=principal.user_id, status="QUEUED")
    db.add(new)
    db.flush()
    audit.add_to_transaction(db, "DOCUMENT_ANALYSIS_REQUESTED", AuditOutcome.SUCCESS, actor=principal,
                             resource_type="uploaded_document", resource_ref=str(doc.id))
    db.commit()
    db.refresh(new)
    return AnalyzeResponse(job_id=new.id, status=new.status, created_at=new.created_at)
