"""Runs one document-processing job (doc 02 Workflow C, doc 07 §5.2). Executed in-process through
FastAPI BackgroundTasks (doc 04: MVP background work), at most MAX_CONCURRENT_DOCUMENT_JOBS at a time.

Status transitions are enforced here: QUEUED → RUNNING → {COMPLETED | COMPLETED_WITH_WARNINGS | FAILED}
and QUEUED → FAILED. Terminal jobs are never modified; re-analysis creates a new job. Extracted text
exists only in memory during the run; only fields, page metadata and warning codes are stored."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.documents import fields as field_rules
from app.documents.extraction import JobTimeoutError, PdfParseError, extract_pages
from app.documents.llm_extraction import AnthropicFieldExtractor, LlmUnavailableError
from app.documents.ocr import OcrEngine, get_ocr_engine
from app.documents.storage import FileStorage, StorageError, get_storage
from app.models import DocumentProcessingJob, ExtractedField, PaRequirementSet, UploadedDocument, User
from app.models.document import TERMINAL_JOB_STATUSES
from app.models.enums import AuditOutcome
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ALLOWED = {"QUEUED": {"RUNNING", "FAILED"}, "RUNNING": {"COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"}}
_SAFE_DETAIL = {
    "PDF_PARSE_ERROR": "The PDF could not be read.",
    "TIMEOUT": "Processing took longer than the time limit.",
    "INTERNAL_ERROR": "Processing failed unexpectedly. Please try again.",
}
_slots: threading.BoundedSemaphore | None = None
_slots_lock = threading.Lock()


class InvalidTransitionError(Exception):
    pass


def transition(job: DocumentProcessingJob, new_status: str) -> None:
    if job.status in TERMINAL_JOB_STATUSES or new_status not in _ALLOWED.get(job.status, set()):
        raise InvalidTransitionError(f"{job.status} -> {new_status}")
    job.status = new_status


def _semaphore(settings: Settings) -> threading.BoundedSemaphore:
    global _slots
    with _slots_lock:
        if _slots is None:
            _slots = threading.BoundedSemaphore(settings.max_concurrent_document_jobs)
        return _slots


@dataclass
class _Actor:
    user_id: UUID
    role: str


def run_job(job_id: UUID, *, storage: FileStorage | None = None, ocr: OcrEngine | None = None,
            settings: Settings | None = None, llm_client=None) -> None:
    """Entry point for BackgroundTasks. Never raises: every outcome is recorded on the job."""
    settings = settings or get_settings()
    slots = _semaphore(settings)
    if not slots.acquire(timeout=settings.job_timeout_seconds):
        _fail(job_id, "TIMEOUT", "Processing could not start in time; please try again.")
        return
    try:
        _run(job_id, storage or get_storage(), ocr or get_ocr_engine(), settings, llm_client)
    except Exception as exc:  # noqa: BLE001 - last-resort guard; details stay in the log
        logger.error("document_job_crashed", extra={"error_type": type(exc).__name__})
        _fail(job_id, "INTERNAL_ERROR", _SAFE_DETAIL["INTERNAL_ERROR"])
    finally:
        slots.release()


def _fail(job_id: UUID, code: str, detail: str) -> None:
    with get_session_factory()() as db:
        job = db.get(DocumentProcessingJob, job_id)
        if job is None or job.status in TERMINAL_JOB_STATUSES:
            return
        transition(job, "FAILED")
        job.error_code, job.error_detail, job.completed_at = code, detail, datetime.now(UTC)
        _audit(db, job, "DOCUMENT_ANALYSIS_FAILED", AuditOutcome.FAILURE, error_code=code)
        db.commit()


def _audit(db: Session, job: DocumentProcessingJob, action: str, outcome: AuditOutcome, **meta) -> None:
    owner = db.get(User, job.requested_by_user_id)
    AuditService().add_to_transaction(
        db,
        action,
        outcome,
        actor=_Actor(owner.id, owner.role) if owner else None,
        resource_type="uploaded_document",
        resource_ref=str(job.uploaded_document_id),
        reason_code=meta.pop("error_code", None),
        metadata=meta,
    )


def _run(job_id: UUID, storage: FileStorage, ocr: OcrEngine, settings: Settings, llm_client) -> None:
    deadline = time.monotonic() + settings.job_timeout_seconds
    with get_session_factory()() as db:
        job = db.get(DocumentProcessingJob, job_id)
        if job is None or job.status != "QUEUED":
            return  # already handled (e.g. duplicate scheduling): never re-run a job
        doc = db.get(UploadedDocument, job.uploaded_document_id)
        transition(job, "RUNNING")
        job.started_at = datetime.now(UTC)
        db.commit()

        try:
            data = storage.read(doc.storage_key)
            pages = extract_pages(data, doc.mime_type, settings, ocr, deadline)
        except StorageError:
            db.rollback()
            return _finish_failed(db, job, "INTERNAL_ERROR", _SAFE_DETAIL["INTERNAL_ERROR"])
        except PdfParseError:
            return _finish_failed(db, job, "PDF_PARSE_ERROR", _SAFE_DETAIL["PDF_PARSE_ERROR"])
        except JobTimeoutError:
            return _finish_failed(db, job, "TIMEOUT", _SAFE_DETAIL["TIMEOUT"])

        ocr_warnings = {p.warning for p in pages if p.warning and p.warning.startswith("OCR_")}
        if not any(p.text for p in pages) and ocr_warnings & {"OCR_UNAVAILABLE", "OCR_FAILED", "OCR_TIMEOUT"}:
            detail = (
                "No text could be read: this file needs OCR, and the OCR engine is not available."
                if "OCR_UNAVAILABLE" in ocr_warnings
                else "No text could be read: OCR did not succeed for this file."
            )
            job.page_details = [p.detail() for p in pages]
            return _finish_failed(db, job, "OCR_FAILED", detail)

        doc_type = field_rules.classify(pages)
        active = set(db.scalars(select(PaRequirementSet.procedure_code).where(PaRequirementSet.is_active)))
        warnings: list[str] = []
        llm_spans: dict[str, tuple[str, int]] | None = None
        if settings.llm_provider == "anthropic" and doc_type != "UNRECOGNIZED":
            specs = field_rules.missing_specs(doc_type, pages)
            if specs:
                try:
                    found = AnthropicFieldExtractor(settings, llm_client).extract(specs, pages)
                    llm_spans = found.spans
                    if found.discarded:
                        warnings.append(f"UNGROUNDED_EXTRACTION_DISCARDED:{found.discarded}")
                except LlmUnavailableError:
                    warnings.append("LLM_EXTRACTION_UNAVAILABLE")
        if time.monotonic() > deadline:
            return _finish_failed(db, job, "TIMEOUT", _SAFE_DETAIL["TIMEOUT"])

        results = field_rules.extract_fields(doc_type, pages, active, settings.extraction_low_confidence, llm_spans)
        if doc_type == "UNRECOGNIZED":
            warnings.append("DOCUMENT_TYPE_UNRECOGNIZED")
        if not any(p.text for p in pages):
            warnings.append("DOCUMENT_EMPTY")
        warnings += [f"PAGE_{p.page_number}_{p.warning}" for p in pages if p.warning]
        warnings += [f"FIELD_{r.field_name}_{r.validation_status}" for r in results if r.validation_status != "VALID"]

        ocr_confs = [p.ocr_confidence for p in pages if p.method == "OCR" and p.ocr_confidence is not None]
        job.detected_document_type = doc_type
        job.pages_text_layer = sum(p.method == "TEXT_LAYER" for p in pages)
        job.pages_ocr = sum(p.method == "OCR" for p in pages)
        job.ocr_mean_confidence = round(sum(ocr_confs) / len(ocr_confs), 2) if ocr_confs else None
        job.extraction_schema_version = field_rules.SCHEMA_VERSION
        job.pipeline_version = field_rules.PIPELINE_VERSION
        job.page_details = [p.detail() for p in pages]
        job.warnings = warnings
        job.warning_count = len(warnings)
        job.fields = [
            ExtractedField(
                field_name=r.field_name,
                raw_value=r.raw_value,
                normalized_value=r.normalized_value,
                validation_status=r.validation_status,
                validation_message=r.validation_message,
                source_page=r.source_page,
                extraction_method=r.extraction_method,
                confidence=r.confidence,
            )
            for r in results
        ]
        transition(job, "COMPLETED_WITH_WARNINGS" if warnings else "COMPLETED")
        job.completed_at = datetime.now(UTC)
        _audit(db, job, "DOCUMENT_ANALYSIS_COMPLETED", AuditOutcome.SUCCESS, job_status=job.status,
               document_type=doc_type, result_count=len(results))
        db.commit()


def _finish_failed(db: Session, job: DocumentProcessingJob, code: str, detail: str) -> None:
    transition(job, "FAILED")
    job.error_code, job.error_detail, job.completed_at = code, detail, datetime.now(UTC)
    _audit(db, job, "DOCUMENT_ANALYSIS_FAILED", AuditOutcome.FAILURE, error_code=code)
    db.commit()
