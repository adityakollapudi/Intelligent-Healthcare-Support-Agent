"""Uploaded-document and processing-job schemas (doc 06 §3.6). Storage keys, hashes and file
contents are never part of any response."""

from typing import Literal
from uuid import UUID

from app.schemas.common import DATA_ENVIRONMENT, ApiModel, DataEnvironment, UtcDatetime

JobStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"]
FieldStatus = Literal["VALID", "ABSENT", "ILLEGIBLE", "INVALID_FORMAT", "INCONSISTENT", "LOW_CONFIDENCE"]
DeclaredPurpose = Literal["PA_REQUEST", "SUPPORTING_DOCUMENT", "OTHER"]


class PageDetail(ApiModel):
    page_number: int
    method: Literal["TEXT_LAYER", "OCR"] | None
    status: Literal["OK", "EMPTY", "PARTIAL", "LOW_QUALITY", "UNREADABLE"]
    char_count: int
    ocr_confidence: float | None
    warning: str | None


class DocumentField(ApiModel):
    field_id: UUID
    field_name: str
    raw_value: str | None
    normalized_value: str | None
    validation_status: FieldStatus
    validation_message: str | None
    source_page: int | None
    extraction_method: Literal["TEXT_LAYER", "OCR"] | None
    # OCR word confidence (0–1) for OCR'd values; not a calibrated probability. None for text-layer values.
    confidence: float | None


class JobSummary(ApiModel):
    job_id: UUID
    status: JobStatus
    detected_document_type: str | None
    pages_text_layer: int
    pages_ocr: int
    ocr_mean_confidence: float | None
    warning_count: int
    error_code: str | None
    error_detail: str | None
    created_at: UtcDatetime
    started_at: UtcDatetime | None
    completed_at: UtcDatetime | None


class JobDetail(JobSummary):
    extraction_schema_version: str | None
    pipeline_version: str | None
    warnings: list[str]
    pages: list[PageDetail]
    fields: list[DocumentField]


class DocumentSummary(ApiModel):
    document_id: UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    page_count: int
    declared_purpose: DeclaredPurpose | None
    created_at: UtcDatetime
    expires_at: UtcDatetime
    latest_job: JobSummary | None
    data_environment: DataEnvironment = DATA_ENVIRONMENT


class DocumentDetail(DocumentSummary):
    latest_job: JobDetail | None


class DocumentPage(ApiModel):
    items: list[DocumentSummary]
    next_cursor: str | None = None


class AnalyzeResponse(ApiModel):
    job_id: UUID
    status: JobStatus
    created_at: UtcDatetime
