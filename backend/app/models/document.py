"""Uploaded documents, their processing jobs and extracted fields, and documentation-readiness
checklists (doc 05 §2.9–2.16). Status values come from doc 02 §3.2–3.6.

Separation of concerns: an uploaded document is untrusted user input and never becomes a knowledge
document. Each analysis run is its own job; its fields belong to that job, so re-analysis never
overwrites earlier results. Checklists record the exact job whose fields they evaluated."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAt, Synthetic, Timestamps, UUIDPrimaryKey

MIME_TYPES = ("application/pdf", "image/png", "image/jpeg")
DECLARED_PURPOSES = ("PA_REQUEST", "SUPPORTING_DOCUMENT", "OTHER")
JOB_STATUSES = ("QUEUED", "RUNNING", "COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED")
TERMINAL_JOB_STATUSES = ("COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED")
DOCUMENT_TYPES = ("PA_REQUEST_FORM", "CLINICAL_NOTE_SUMMARY", "REFERRAL_LETTER", "CLAIM_SUPPORT_LETTER", "UNRECOGNIZED")
JOB_ERROR_CODES = ("PDF_PARSE_ERROR", "OCR_FAILED", "PAGE_LIMIT_EXCEEDED", "TIMEOUT", "INTERNAL_ERROR")
FIELD_STATUSES = ("VALID", "ABSENT", "ILLEGIBLE", "INVALID_FORMAT", "INCONSISTENT", "LOW_CONFIDENCE")
EXTRACTION_METHODS = ("TEXT_LAYER", "OCR")
ITEM_STATUSES = ("SATISFIED", "MISSING", "UNREADABLE", "NEEDS_MANUAL_REVIEW")
READINESS_STATUSES = ("DOCUMENTATION_APPEARS_COMPLETE", "DOCUMENTATION_INCOMPLETE", "MANUAL_REVIEW_REQUIRED")
REVIEW_STATES = ("NOT_SUBMITTED", "AWAITING_REVIEW", "UNDER_REVIEW", "REVIEW_COMPLETED")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class UploadedDocument(UUIDPrimaryKey, Synthetic, CreatedAt, Base):
    __tablename__ = "uploaded_documents"
    __table_args__ = (
        CheckConstraint(f"mime_type IN ({_in(MIME_TYPES)})", name="mime_type_valid"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("page_count >= 1", name="page_count_positive"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        CheckConstraint("storage_key ~ '^uploads/[0-9a-f-]{36}$'", name="storage_key_format"),
        CheckConstraint(
            f"declared_purpose IS NULL OR declared_purpose IN ({_in(DECLARED_PURPOSES)})", name="purpose_valid"
        ),
        Index("ix_uploaded_documents_owner_created", "owner_user_id", text("created_at DESC")),
        Index("ix_uploaded_documents_expires_at", "expires_at"),
    )

    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(255))  # sanitized display name, never a path
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(String(64))
    declared_purpose: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    jobs: Mapped[list["DocumentProcessingJob"]] = relationship(
        back_populates="document", order_by="DocumentProcessingJob.created_at.desc()"
    )


class DocumentProcessingJob(UUIDPrimaryKey, CreatedAt, Base):
    """One analysis run. Terminal states are immutable; re-analysis creates a new job (doc 02 §3.2)."""

    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        CheckConstraint(f"status IN ({_in(JOB_STATUSES)})", name="status_valid"),
        CheckConstraint(
            f"detected_document_type IS NULL OR detected_document_type IN ({_in(DOCUMENT_TYPES)})",
            name="document_type_valid",
        ),
        CheckConstraint(f"error_code IS NULL OR error_code IN ({_in(JOB_ERROR_CODES)})", name="error_code_valid"),
        CheckConstraint("(status = 'FAILED') = (error_code IS NOT NULL)", name="error_code_iff_failed"),
        CheckConstraint(
            "ocr_mean_confidence IS NULL OR (ocr_mean_confidence >= 0 AND ocr_mean_confidence <= 100)",
            name="ocr_confidence_range",
        ),
        Index("ix_document_processing_jobs_document_created", "uploaded_document_id", text("created_at DESC")),
        Index("ix_document_processing_jobs_status", "status"),
    )

    uploaded_document_id: Mapped[UUID] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="CASCADE"))
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'QUEUED'"))
    detected_document_type: Mapped[str | None] = mapped_column(Text)
    pages_text_layer: Mapped[int] = mapped_column(server_default=text("0"))
    pages_ocr: Mapped[int] = mapped_column(server_default=text("0"))
    ocr_mean_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    extraction_schema_version: Mapped[str | None] = mapped_column(String(20))
    pipeline_version: Mapped[str | None] = mapped_column(String(20))  # D6-02: extractor code version
    warning_count: Mapped[int] = mapped_column(server_default=text("0"))
    # D6-01: per-page method/length/status and job-level warning codes; never document text.
    page_details: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    warnings: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_detail: Mapped[str | None] = mapped_column(String(200))  # D6-03: safe, user-presentable
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[UploadedDocument] = relationship(back_populates="jobs")
    fields: Mapped[list["ExtractedField"]] = relationship(
        cascade="all, delete-orphan", order_by="ExtractedField.field_name"
    )


class ExtractedField(UUIDPrimaryKey, CreatedAt, Base):
    """raw_value is exactly what the document contains; normalized_value is set only for VALID or
    LOW_CONFIDENCE values. Model inferences not found in the text are never stored (doc 05 §2.11)."""

    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("job_id", "field_name"),
        CheckConstraint(f"validation_status IN ({_in(FIELD_STATUSES)})", name="validation_status_valid"),
        CheckConstraint(
            f"extraction_method IS NULL OR extraction_method IN ({_in(EXTRACTION_METHODS)})", name="method_valid"
        ),
        # ABSENT never has a value; ILLEGIBLE may lack one (field not found because pages were unreadable).
        CheckConstraint("validation_status <> 'ABSENT' OR raw_value IS NULL", name="absent_has_no_raw_value"),
        CheckConstraint(
            "raw_value IS NOT NULL OR validation_status IN ('ABSENT', 'ILLEGIBLE')", name="raw_value_required"
        ),
        CheckConstraint(
            "normalized_value IS NULL OR validation_status IN ('VALID', 'LOW_CONFIDENCE')",
            name="normalized_only_when_usable",
        ),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_range"),
        CheckConstraint("source_page IS NULL OR source_page >= 1", name="source_page_positive"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("document_processing_jobs.id", ondelete="CASCADE"))
    field_name: Mapped[str] = mapped_column(String(60))
    raw_value: Mapped[str | None] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(Text)
    validation_message: Mapped[str | None] = mapped_column(String(300))
    source_page: Mapped[int | None]
    extraction_method: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))


class AuthorizationChecklist(UUIDPrimaryKey, Timestamps, Base):
    """A documentation-readiness checklist. Nothing here represents an approval or denial (doc 07 §6.6)."""

    __tablename__ = "authorization_checklists"
    __table_args__ = (
        CheckConstraint(f"readiness_status IN ({_in(READINESS_STATUSES)})", name="readiness_status_valid"),
        CheckConstraint(f"review_state IN ({_in(REVIEW_STATES)})", name="review_state_valid"),
        CheckConstraint(
            "satisfied_count >= 0 AND missing_count >= 0 AND unreadable_count >= 0 AND manual_review_count >= 0",
            name="counts_non_negative",
        ),
        Index("ix_authorization_checklists_creator_created", "created_by_user_id", text("created_at DESC")),
    )

    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    requirement_set_id: Mapped[UUID] = mapped_column(ForeignKey("pa_requirement_sets.id"))
    # D6-04: the exact knowledge-document version the requirements were verified against.
    requirement_source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_documents.id"))
    readiness_status: Mapped[str] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(Text, server_default=text("'NOT_SUBMITTED'"))
    satisfied_count: Mapped[int] = mapped_column(server_default=text("0"))
    missing_count: Mapped[int] = mapped_column(server_default=text("0"))
    unreadable_count: Mapped[int] = mapped_column(server_default=text("0"))
    manual_review_count: Mapped[int] = mapped_column(server_default=text("0"))
    reviewer_summary: Mapped[str | None] = mapped_column(Text)
    provider_note: Mapped[str | None] = mapped_column(String(2000))
    disclaimer_version: Mapped[str] = mapped_column(String(10))
    warnings: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))  # D6-05
    rules_version: Mapped[str] = mapped_column(String(20))  # D6-02: evaluator version

    items: Mapped[list["AuthorizationChecklistItem"]] = relationship(cascade="all, delete-orphan")
    documents: Mapped[list["ChecklistDocument"]] = relationship(cascade="all, delete-orphan")


class AuthorizationChecklistItem(UUIDPrimaryKey, Base):
    """Immutable once created; a re-run creates a new checklist (doc 02 §3.4)."""

    __tablename__ = "authorization_checklist_items"
    __table_args__ = (
        UniqueConstraint("checklist_id", "requirement_id"),
        CheckConstraint(f"item_status IN ({_in(ITEM_STATUSES)})", name="item_status_valid"),
    )

    checklist_id: Mapped[UUID] = mapped_column(ForeignKey("authorization_checklists.id", ondelete="CASCADE"))
    requirement_id: Mapped[UUID] = mapped_column(ForeignKey("pa_requirements.id"))
    item_status: Mapped[str] = mapped_column(Text)
    # extracted_fields.id values the rule used; validated in the service (arrays can't carry FKs).
    evidence_field_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid), server_default=text("'{}'"))
    explanation: Mapped[str] = mapped_column(String(500))


class ChecklistDocument(Base):
    __tablename__ = "checklist_documents"

    checklist_id: Mapped[UUID] = mapped_column(
        ForeignKey("authorization_checklists.id", ondelete="CASCADE"), primary_key=True
    )
    uploaded_document_id: Mapped[UUID] = mapped_column(ForeignKey("uploaded_documents.id"), primary_key=True)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("document_processing_jobs.id"))
