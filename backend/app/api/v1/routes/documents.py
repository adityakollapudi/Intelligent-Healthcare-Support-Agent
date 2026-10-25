from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.documents import pipeline
from app.documents.ocr import OcrEngine, get_ocr_engine
from app.documents.storage import FileStorage, get_storage
from app.schemas.common import ErrorResponse
from app.schemas.document import AnalyzeResponse, DeclaredPurpose, DocumentDetail, DocumentPage, DocumentSummary
from app.services import document_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/documents", tags=["documents"])

Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Config = Annotated[Settings, Depends(get_settings)]
Storage = Annotated[FileStorage, Depends(get_storage)]
Uploader = Annotated[Principal, Depends(require_any_permission(Permission.DOCUMENTS_UPLOAD))]
Reader = Annotated[Principal, Depends(require_any_permission(Permission.DOCUMENTS_READ_OWN))]
_ERRORS = {s: {"model": ErrorResponse} for s in (401, 403, 404, 409, 411, 413, 415, 422, 429, 500)}


@router.post(
    "",
    response_model=DocumentSummary,
    status_code=201,
    responses={**_ERRORS, 200: {"model": DocumentSummary}},
    summary="Upload a synthetic PDF/PNG/JPEG document (stored privately; not analyzed yet)",
)
def upload_document(
    response: Response,
    db: Db,
    audit: Audit,
    settings: Config,
    storage: Storage,
    principal: Uploader,
    file: Annotated[UploadFile, File()],
    declared_purpose: Annotated[DeclaredPurpose | None, Form()] = None,
) -> DocumentSummary:
    data = file.file.read(settings.max_upload_bytes + 1)  # bounded: one byte over the limit is enough
    doc, created = document_service.upload(
        db, audit, settings, storage, principal,
        filename=file.filename, content_type=file.content_type, data=data, declared_purpose=declared_purpose,
    )
    if not created:
        response.status_code = 200  # the same file was already uploaded by this user; nothing new stored
    return doc


@router.get("", response_model=DocumentPage, responses=_ERRORS, summary="My uploaded documents")
def list_documents(db: Db, principal: Reader) -> DocumentPage:
    return document_service.list_documents(db, principal)


@router.get(
    "/{document_id}", response_model=DocumentDetail, responses=_ERRORS,
    summary="One of my documents, with its latest analysis job, page details and extracted fields",
)
def get_document(document_id: UUID, db: Db, audit: Audit, principal: Reader) -> DocumentDetail:
    return document_service.get_document(db, audit, principal, document_id)


@router.post(
    "/{document_id}/analyze",
    response_model=AnalyzeResponse,
    status_code=202,
    responses=_ERRORS,
    summary="Start text extraction/OCR and field extraction; poll GET /documents/{id} for the result",
)
def analyze_document(
    document_id: UUID,
    background: BackgroundTasks,
    db: Db,
    audit: Audit,
    settings: Config,
    storage: Storage,
    ocr: Annotated[OcrEngine, Depends(get_ocr_engine)],
    principal: Uploader,
) -> AnalyzeResponse:
    job = document_service.request_analysis(db, audit, settings, principal, document_id)
    background.add_task(pipeline.run_job, job.job_id, storage=storage, ocr=ocr, settings=settings)
    return job
