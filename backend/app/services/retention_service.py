"""Retention cleanup (NFR-021, SEC-13). Run as a scheduled maintenance job:
`python -m scripts.cleanup_expired [--dry-run]`.

- Conversation sessions (messages, citations, feedback by cascade): deleted once `expires_at` passes.
- Uploaded documents past `expires_at`: file deleted from private storage, extracted field values
  deleted, row soft-deleted (`deleted_at`). Kept while linked to a non-terminal support case, or to a
  case closed/cancelled less than 30 days ago (SEC-13).
- Revoked tokens past `expires_at` (the token can't be used any more anyway).
- Audit events are NOT purged here: audit_logs is append-only for the application role (DB trigger);
  the 365-day purge needs a separate maintenance role (SEC-17), not provisioned in this prototype.
Job metadata (status, page counts, warning codes) and checklists stay: they contain no document text."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.orm import Session

from app.documents.storage import FileStorage, StorageError
from app.models import (
    ConversationSession,
    DocumentProcessingJob,
    ExtractedField,
    RevokedToken,
    SupportCase,
    SupportCaseDocument,
    UploadedDocument,
)

logger = logging.getLogger(__name__)
CASE_GRACE = timedelta(days=30)


@dataclass
class CleanupReport:
    sessions_deleted: int = 0
    documents_expired: int = 0
    documents_kept_for_open_cases: int = 0
    fields_deleted: int = 0
    files_deleted: int = 0
    file_errors: int = 0
    revoked_tokens_deleted: int = 0
    dry_run: bool = False


def _protected(now: datetime):
    """Documents linked to a case that is still open, or closed/cancelled less than 30 days ago."""
    return exists().where(
        SupportCaseDocument.uploaded_document_id == UploadedDocument.id,
        SupportCaseDocument.case_id == SupportCase.id,
        or_(SupportCase.status.not_in(("CLOSED", "CANCELLED")),
            SupportCase.updated_at > now - CASE_GRACE),
    )


def run(db: Session, storage: FileStorage, *, now: datetime | None = None, dry_run: bool = False) -> CleanupReport:
    now = now or datetime.now(UTC)
    report = CleanupReport(dry_run=dry_run)
    expired_doc = and_(UploadedDocument.deleted_at.is_(None), UploadedDocument.expires_at <= now)

    session_ids = list(db.scalars(select(ConversationSession.id).where(ConversationSession.expires_at <= now)))
    report.sessions_deleted = len(session_ids)
    report.documents_kept_for_open_cases = db.scalar(
        select(func.count()).select_from(UploadedDocument).where(expired_doc, _protected(now))
    )
    docs = list(db.scalars(select(UploadedDocument).where(expired_doc, ~_protected(now))))
    report.documents_expired = len(docs)
    token_ids = list(db.scalars(select(RevokedToken.jti).where(RevokedToken.expires_at <= now)))
    report.revoked_tokens_deleted = len(token_ids)
    if dry_run:
        return report

    if session_ids:
        db.execute(delete(ConversationSession).where(ConversationSession.id.in_(session_ids)))
    for doc in docs:
        job_ids = select(DocumentProcessingJob.id).where(DocumentProcessingJob.uploaded_document_id == doc.id)
        report.fields_deleted += db.execute(delete(ExtractedField).where(ExtractedField.job_id.in_(job_ids))).rowcount
        doc.deleted_at = now
    if token_ids:
        db.execute(delete(RevokedToken).where(RevokedToken.jti.in_(token_ids)))
    db.commit()
    # Files go after the commit: a crash here leaves an orphan file (logged), never a row without its file.
    for doc in docs:
        try:
            storage.delete(doc.storage_key)
            report.files_deleted += 1
        except StorageError:
            report.file_errors += 1
            logger.error("retention_file_delete_failed", extra={"document_id": str(doc.id)})
    return report
