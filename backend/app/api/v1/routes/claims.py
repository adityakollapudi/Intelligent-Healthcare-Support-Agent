from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.authz.dependencies import Principal, require_any_permission
from app.authz.permissions import Permission
from app.db.session import get_db
from app.models.enums import ClaimStatus
from app.schemas.claim import ClaimDetail, ClaimPage
from app.schemas.common import CLAIM_NUMBER_PATTERN, ErrorResponse
from app.services import claim_service
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/claims", tags=["claims"])

Db = Annotated[Session, Depends(get_db)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_ERRORS = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


@router.get("", response_model=ClaimPage, summary="List my claims (members)", responses=_ERRORS)
def list_claims(
    db: Db,
    audit: Audit,
    principal: Annotated[Principal, Depends(require_any_permission(Permission.CLAIMS_READ_OWN))],
    status: Annotated[list[ClaimStatus] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ClaimPage:
    statuses = [s.value for s in status] if status else None
    return claim_service.list_claims(db, audit, principal, statuses=statuses, limit=limit, cursor=cursor)


@router.get(
    "/{claim_number}",
    response_model=ClaimDetail,
    summary="Get one claim the caller is permitted to see",
    responses={**_ERRORS, 404: {"model": ErrorResponse, "description": "Not found or not permitted"}},
)
def get_claim(
    db: Db,
    audit: Audit,
    principal: Annotated[Principal, Depends(require_any_permission(
        Permission.CLAIMS_READ_OWN, Permission.CLAIMS_READ_CASE_LINKED))],
    claim_number: Annotated[str, Path(pattern=CLAIM_NUMBER_PATTERN, examples=["SYN-CLM-2026-000101"])],
) -> ClaimDetail:
    return claim_service.get_claim(db, audit, principal, claim_number)
