from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.knowledge import PlanDocumentDetail, PlanDocumentSummary
from app.services import knowledge_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

Reader = Annotated[Principal, Depends(require_any_permission(Permission.KNOWLEDGE_READ))]
Db = Annotated[Session, Depends(get_db)]
_ERRORS = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


@router.get("/documents", response_model=list[PlanDocumentSummary], responses=_ERRORS,
            summary="Plan documents I may read (members: general documents and my own plan)")
def list_documents(db: Db, principal: Reader) -> list[PlanDocumentSummary]:
    return knowledge_service.list_documents(db, principal)


@router.get("/documents/{document_id}", response_model=PlanDocumentDetail, responses=_ERRORS,
            summary="Read one plan document, by section")
def get_document(document_id: UUID, db: Db, principal: Reader,
                 audit: Annotated[AuditService, Depends(get_audit_service)]) -> PlanDocumentDetail:
    return knowledge_service.get_document(db, audit, principal, document_id)
